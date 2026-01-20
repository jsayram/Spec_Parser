"""Ollama provider for local LLM inference (Qwen2-Coder-7B, etc.)."""

import json
from typing import Optional

import requests
import tenacity
from loguru import logger

from spec_parser.llm.providers import BaseLLMProvider


def log_retry_attempt(retry_state: tenacity.RetryCallState) -> None:
    """Log retry attempts with context."""
    attempt = retry_state.attempt_number
    if retry_state.outcome and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        logger.warning(
            f"Ollama retry attempt {attempt}: {type(exception).__name__}: {exception}"
        )
    else:
        logger.info(f"Ollama retry attempt {attempt}")


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local LLM models.
    
    Supports Qwen2-Coder-7B, Llama, and other Ollama-compatible models.
    Includes automatic retry with exponential backoff for reliability.
    """

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        max_tokens: int = 4000,
        timeout: int = 180,
        max_retries: int = 5,
        retry_min_wait: float = 2.0,
        retry_max_wait: float = 60.0,
        retry_multiplier: float = 2.0,
        retry_jitter: float = 5.0
    ):
        """Initialize Ollama provider with retry configuration.
        
        Args:
            model: Ollama model name (e.g., "qwen2.5-coder:7b", "llama3:8b")
            base_url: Ollama API base URL
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
            retry_min_wait: Initial wait between retries (seconds)
            retry_max_wait: Maximum wait between retries (seconds)
            retry_multiplier: Exponential multiplier for wait time
            retry_jitter: Random jitter added to wait time (seconds)
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Retry configuration
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.retry_multiplier = retry_multiplier
        self.retry_jitter = retry_jitter
        
        # Create retry decorator dynamically
        self._setup_retry()
        
        logger.info(
            f"Initialized Ollama provider: {model} at {base_url} "
            f"(max_retries={max_retries}, timeout={timeout}s)"
        )
    
    def _setup_retry(self):
        """Configure tenacity retry decorator."""
        self._retry_decorator = tenacity.retry(
            wait=tenacity.wait_exponential_jitter(
                initial=self.retry_min_wait,
                max=self.retry_max_wait,
                exp_base=self.retry_multiplier,
                jitter=self.retry_jitter
            ),
            stop=tenacity.stop_after_attempt(self.max_retries),
            retry=tenacity.retry_if_exception_type((
                requests.ConnectionError,
                requests.Timeout,
                requests.HTTPError,
            )),
            before_sleep=log_retry_attempt,
            reraise=True
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate completion using Ollama API with automatic retry.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Ollama parameters
            
        Returns:
            Generated text completion
            
        Raises:
            RuntimeError: If Ollama is not running or all retries exhausted
        """
        return self._generate_with_retry(prompt, system_prompt, **kwargs)
    
    def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Internal generate with tenacity retry wrapper."""
        
        @self._retry_decorator
        def _call_ollama():
            return self._make_request(prompt, system_prompt, **kwargs)
        
        try:
            return _call_ollama()
        except tenacity.RetryError as e:
            logger.error(
                f"Ollama exhausted {self.max_retries} retries. "
                f"Last error: {e.last_attempt.exception()}"
            )
            raise RuntimeError(
                f"Ollama failed after {self.max_retries} attempts. "
                f"Check if Ollama is running: ollama serve"
            ) from e
    
    def _make_request(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Make a single Ollama API request."""
        # Acquire rate limit token (no-op for local)
        with self.rate_limiter:
            url = f"{self.base_url}/api/generate"
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            }
            
            # Add system prompt if provided
            if system_prompt:
                payload["system"] = system_prompt
            
            # Merge additional kwargs
            if kwargs:
                payload["options"].update(kwargs)
            
            logger.debug(f"Ollama request: {len(prompt)} chars, temp={self.temperature}")
            
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                completion = result.get("response", "")
                
                logger.debug(
                    f"Ollama response: {len(completion)} chars, "
                    f"took {result.get('total_duration', 0) / 1e9:.2f}s"
                )
                
                return completion
                
            except requests.ConnectionError as e:
                logger.error(f"Ollama connection failed at {self.base_url}: {e}")
                raise  # Will be retried
            
            except requests.Timeout as e:
                logger.error(f"Ollama request timed out after {self.timeout}s: {e}")
                raise  # Will be retried
            
            except requests.HTTPError as e:
                # Check if it's a retryable error
                if e.response.status_code in {408, 429, 500, 502, 503, 504}:
                    logger.warning(
                        f"Ollama retryable error {e.response.status_code}: {e}"
                    )
                    raise  # Will be retried
                else:
                    logger.error(f"Ollama API error: {e.response.text}")
                    raise RuntimeError(f"Ollama API error: {e}") from e

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available.
        
        Returns:
            True if Ollama is accessible and model exists
        """
        try:
            # Check if Ollama is running
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            
            # Check if model is available
            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]
            
            if self.model not in model_names:
                logger.warning(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Available: {model_names}. Pull with: ollama pull {self.model}"
                )
                return False
            
            logger.debug(f"Ollama provider available: {self.model}")
            return True
            
        except requests.RequestException as e:
            logger.warning(f"Ollama not available at {self.base_url}: {e}")
            return False

