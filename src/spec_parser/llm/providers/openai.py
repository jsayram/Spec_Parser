"""OpenAI provider for GPT-4o and other OpenAI models."""

import os
from typing import Optional

from loguru import logger

from spec_parser.llm.providers import BaseLLMProvider
from spec_parser.llm.rate_limiter import TokenBucketRateLimiter


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider for GPT-4o and other models.
    
    Supports GPT-4o with automatic rate limiting (60 req/min).
    Requires OPENAI_API_KEY environment variable.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        max_tokens: int = 4000,
        api_key: Optional[str] = None,
        rate_limit: float = 1.0  # 1 req/sec = 60 req/min
    ):
        """Initialize OpenAI provider.
        
        Args:
            model: OpenAI model name (e.g., "gpt-4o", "gpt-4-turbo")
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            rate_limit: Requests per second (default: 1.0 = 60/min)
        """
        # Initialize with rate limiter
        rate_limiter = TokenBucketRateLimiter(
            rate=rate_limit,
            capacity=int(rate_limit * 60),
            name="OpenAI"
        )
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            rate_limiter=rate_limiter
        )
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY not set. Provider will not be available."
            )
        else:
            logger.info(f"Initialized OpenAI provider: {model}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate completion using OpenAI API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional OpenAI parameters
            
        Returns:
            Generated text completion
            
        Raises:
            ImportError: If openai package not installed
            Exception: If API call fails
        """
        # Lazy import openai (optional dependency)
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai package not installed. "
                "Install with: pip install openai"
            ) from e
        
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. "
                "Set environment variable or pass api_key parameter."
            )
        
        # Acquire rate limit token
        with self.rate_limiter:
            client = OpenAI(api_key=self.api_key)
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            logger.debug(
                f"OpenAI request: {len(prompt)} chars, "
                f"temp={self.temperature}, max_tokens={self.max_tokens}"
            )
            
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    **kwargs
                )
                
                completion = response.choices[0].message.content
                
                logger.debug(
                    f"OpenAI response: {len(completion)} chars, "
                    f"prompt_tokens={response.usage.prompt_tokens}, "
                    f"completion_tokens={response.usage.completion_tokens}"
                )
                
                return completion
                
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                raise

    def is_available(self) -> bool:
        """Check if OpenAI provider is configured.
        
        Returns:
            True if API key is set
        """
        available = bool(self.api_key)
        if available:
            logger.debug(f"OpenAI provider available: {self.model}")
        else:
            logger.warning("OpenAI provider not available: missing API key")
        return available
