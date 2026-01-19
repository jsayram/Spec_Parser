"""LLM interface factory and high-level API."""

from pathlib import Path
from typing import Optional

from loguru import logger

from spec_parser.config import settings
from spec_parser.llm.cache import CorrectionCache
from spec_parser.llm.providers import BaseLLMProvider
from spec_parser.llm.providers.anthropic import AnthropicProvider
from spec_parser.llm.providers.huggingface import HuggingFaceProvider
from spec_parser.llm.providers.ollama import OllamaProvider
from spec_parser.llm.providers.openai import OpenAIProvider
from spec_parser.schemas.llm import LLMCorrectionRecord


class LLMInterface:
    """High-level LLM interface with caching and provider abstraction."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        cache_path: Optional[Path] = None
    ):
        """Initialize LLM interface.
        
        Args:
            provider: LLM provider instance (or None to use config default)
            cache_path: Path to correction cache DB (or None for default)
        """
        self.provider = provider or create_llm_provider()
        
        # Initialize correction cache
        if cache_path is None:
            cache_path = settings.llm_cache_dir / settings.llm_global_cache
        self.cache = CorrectionCache(db_path=cache_path)
        
        logger.info(f"Initialized LLM interface with {self.provider.provider_name}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_cache: bool = True,
        device_id: Optional[str] = None,
        message_type: Optional[str] = None
    ) -> str:
        """Generate completion with automatic caching.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            use_cache: If True, check cache before calling LLM
            device_id: Optional device scope for cache lookup
            message_type: Optional message type for cache lookup
            
        Returns:
            Generated text (from cache or LLM)
        """
        # Compute prompt hash
        prompt_hash = CorrectionCache.compute_hash(prompt, self.provider.model)
        
        # Check cache if enabled
        if use_cache:
            cached = self.cache.get(prompt_hash, increment_hit=True)
            if cached and cached.is_verified:
                # Use corrected response if available, otherwise original
                response = cached.corrected_response or cached.original_response
                logger.info(
                    f"Cache HIT: {prompt_hash[:8]}... "
                    f"(hit_count={cached.hit_count}, verified={cached.is_verified})"
                )
                return response
            elif cached:
                logger.debug(f"Cache hit but not verified: {prompt_hash[:8]}...")
        
        # Cache miss or disabled - call LLM
        logger.info(f"Cache MISS: {prompt_hash[:8]}... - calling {self.provider.provider_name}")
        response = self.provider.generate(prompt, system_prompt)
        
        # Store in cache for future review
        record = LLMCorrectionRecord(
            prompt_hash=prompt_hash,
            model=self.provider.model,
            prompt_text=prompt,
            original_response=response,
            corrected_response=None,
            is_verified=False,
            device_id=device_id,
            message_type=message_type
        )
        self.cache.put(record)
        
        return response

    def get_few_shot_examples(
        self,
        device_id: Optional[str] = None,
        message_type: Optional[str] = None,
        limit: int = 3
    ) -> list[LLMCorrectionRecord]:
        """Retrieve verified corrections as few-shot examples.
        
        Args:
            device_id: Filter by device
            message_type: Filter by message type
            limit: Maximum number of examples
            
        Returns:
            List of verified correction records
        """
        return self.cache.find_similar(
            device_id=device_id,
            message_type=message_type,
            verified_only=True,
            limit=limit
        )

    def cache_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        return self.cache.stats()


def create_llm_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> BaseLLMProvider:
    """Factory function to create LLM provider from config.
    
    Args:
        provider_name: Override config provider ("ollama", "anthropic", "openai")
        model: Override config model
        **kwargs: Additional provider-specific parameters
        
    Returns:
        Configured LLM provider instance
        
    Raises:
        ValueError: If provider is unknown or not available
    """
    provider_name = provider_name or settings.llm_provider
    model = model or settings.llm_model
    
    logger.info(f"Creating LLM provider: {provider_name} with model {model}")
    
    # Create provider based on name
    if provider_name == "huggingface":
        provider = HuggingFaceProvider(
            model=model,
            device="auto",  # Auto-detect best device (CUDA/MPS/CPU)
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            **kwargs
        )
    elif provider_name == "ollama":
        provider = OllamaProvider(
            model=model,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout,
            **kwargs
        )
    elif provider_name == "anthropic":
        provider = AnthropicProvider(
            model=model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            rate_limit=settings.llm_rate_limit,
            **kwargs
        )
    elif provider_name == "openai":
        provider = OpenAIProvider(
            model=model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            rate_limit=settings.llm_rate_limit,
            **kwargs
        )
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            "Supported: ollama, huggingface, anthropic, openai"
        )
    
    # Check if provider is available
    if not provider.is_available():
        raise RuntimeError(
            f"{provider_name} provider is not available. "
            f"Check configuration and dependencies."
        )
    
    return provider
