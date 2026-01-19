"""Base LLM provider interface and factory."""

from abc import ABC, abstractmethod
from typing import Optional

from spec_parser.llm.rate_limiter import NoOpRateLimiter, TokenBucketRateLimiter


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        rate_limiter: Optional[TokenBucketRateLimiter] = None
    ):
        """Initialize LLM provider.
        
        Args:
            model: Model identifier (e.g., "qwen2.5-coder:7b", "claude-3.5-sonnet")
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            rate_limiter: Optional rate limiter for API calls
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.rate_limiter = rate_limiter or NoOpRateLimiter()

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate completion from prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Provider-specific parameters
            
        Returns:
            Generated text completion
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured.
        
        Returns:
            True if provider can be used
        """
        pass

    @property
    def provider_name(self) -> str:
        """Get provider name for logging.
        
        Returns:
            Provider name string
        """
        return self.__class__.__name__
