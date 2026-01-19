"""Ollama provider for local LLM inference (Qwen2-Coder-7B, etc.)."""

from typing import Optional

import requests
from loguru import logger

from spec_parser.llm.providers import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local LLM models.
    
    Supports Qwen2-Coder-7B, Llama, and other Ollama-compatible models.
    No rate limiting needed for local inference.
    """

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        max_tokens: int = 4000,
        timeout: int = 120
    ):
        """Initialize Ollama provider.
        
        Args:
            model: Ollama model name (e.g., "qwen2.5-coder:7b", "llama3:8b")
            base_url: Ollama API base URL
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        logger.info(f"Initialized Ollama provider: {model} at {base_url}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate completion using Ollama API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Ollama parameters
            
        Returns:
            Generated text completion
            
        Raises:
            requests.HTTPError: If Ollama API returns error
            requests.ConnectionError: If Ollama is not running
        """
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
                raise RuntimeError(
                    f"Ollama not running at {self.base_url}. "
                    f"Start with: ollama serve"
                ) from e
            
            except requests.HTTPError as e:
                logger.error(f"Ollama API error: {e.response.text}")
                raise

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
