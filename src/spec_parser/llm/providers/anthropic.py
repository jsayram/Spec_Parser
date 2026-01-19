"""Anthropic Claude provider for production-grade extraction."""

import os
from typing import Optional

from loguru import logger

from spec_parser.llm.providers import BaseLLMProvider
from spec_parser.llm.rate_limiter import TokenBucketRateLimiter


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider for high-quality POCT1-A extraction.
    
    Supports Claude 3.5 Sonnet with automatic rate limiting (60 req/min).
    Requires ANTHROPIC_API_KEY environment variable.
    """

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.0,
        max_tokens: int = 4000,
        api_key: Optional[str] = None,
        rate_limit: float = 1.0  # 1 req/sec = 60 req/min
    ):
        """Initialize Anthropic provider.
        
        Args:
            model: Claude model name
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            rate_limit: Requests per second (default: 1.0 = 60/min)
        """
        # Initialize with rate limiter
        rate_limiter = TokenBucketRateLimiter(
            rate=rate_limit,
            capacity=int(rate_limit * 60),
            name="Anthropic"
        )
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            rate_limiter=rate_limiter
        )
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            logger.warning(
                "ANTHROPIC_API_KEY not set. Provider will not be available."
            )
        else:
            logger.info(f"Initialized Anthropic provider: {model}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate completion using Claude API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Anthropic parameters
            
        Returns:
            Generated text completion
            
        Raises:
            ImportError: If anthropic package not installed
            Exception: If API call fails
        """
        # Lazy import anthropic (optional dependency)
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            ) from e
        
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. "
                "Set environment variable or pass api_key parameter."
            )
        
        # Acquire rate limit token
        with self.rate_limiter:
            client = Anthropic(api_key=self.api_key)
            
            messages = [{"role": "user", "content": prompt}]
            
            logger.debug(
                f"Anthropic request: {len(prompt)} chars, "
                f"temp={self.temperature}, max_tokens={self.max_tokens}"
            )
            
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt or "",
                    messages=messages,
                    **kwargs
                )
                
                completion = response.content[0].text
                
                logger.debug(
                    f"Anthropic response: {len(completion)} chars, "
                    f"input_tokens={response.usage.input_tokens}, "
                    f"output_tokens={response.usage.output_tokens}"
                )
                
                return completion
                
            except Exception as e:
                logger.error(f"Anthropic API error: {e}")
                raise

    def is_available(self) -> bool:
        """Check if Anthropic provider is configured.
        
        Returns:
            True if API key is set
        """
        available = bool(self.api_key)
        if available:
            logger.debug(f"Anthropic provider available: {self.model}")
        else:
            logger.warning("Anthropic provider not available: missing API key")
        return available
