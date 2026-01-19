"""LLM extraction module for POCT1-A specifications.

This module provides:
- SQLite-based correction cache for deterministic LLM outputs
- Multi-provider LLM interface (Ollama, Anthropic, OpenAI)
- BatchNode extraction pattern for message-by-message processing
- POCT1-A-specific prompt templates
- Rate limiting for external APIs

Example usage:
    from spec_parser.llm import LLMInterface, BlueprintFlow
    
    # Initialize with local Ollama (default)
    llm = LLMInterface()
    
    # Or use external API
    from spec_parser.llm.llm_interface import create_llm_provider
    provider = create_llm_provider(provider_name="anthropic", model="claude-3-5-sonnet-20241022")
    llm = LLMInterface(provider=provider)
    
    # Extract blueprint
    flow = BlueprintFlow(
        device_id="Roche_CobasLiat",
        device_name="Roche cobas Liat Analyzer",
        index_dir=Path("data/spec_output/.../index")
    )
    blueprint = flow.run()
"""

from spec_parser.llm.llm_interface import LLMInterface, create_llm_provider
from spec_parser.llm.nodes import BlueprintFlow
from spec_parser.llm.cache import CorrectionCache

__all__ = [
    "LLMInterface",
    "create_llm_provider",
    "BlueprintFlow",
    "CorrectionCache",
]
