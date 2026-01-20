"""
Config package for spec_parser.

Contains:
- Settings: Environment-based application settings (pydantic-settings)
- ExtractionConfig: Unified extraction pipeline configuration
"""

from spec_parser.config.settings import Settings, settings

from spec_parser.config.extraction_config import (
    ExtractionConfig,
    LLMConfig,
    ParallelConfig,
    ConfidenceConfig,
    SearchConfig,
    VisualizationConfig,
    GroundingConfig,
    default_config,
    small_llm_config,
    large_llm_config,
)

# Preset aliases
SMALL_LLM_CONFIG = small_llm_config
LARGE_LLM_CONFIG = large_llm_config
DEFAULT_CONFIG = default_config

__all__ = [
    # Application settings
    "Settings",
    "settings",
    # Extraction config
    "ExtractionConfig",
    "LLMConfig",
    "ParallelConfig",
    "ConfidenceConfig",
    "SearchConfig",
    "VisualizationConfig",
    "GroundingConfig",
    "default_config",
    "small_llm_config",
    "large_llm_config",
    "SMALL_LLM_CONFIG",
    "LARGE_LLM_CONFIG",
    "DEFAULT_CONFIG",
]
