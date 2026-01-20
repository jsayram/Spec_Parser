"""Config package for extraction settings.

This package combines:
- ExtractionConfig: New unified configuration for extraction pipeline
- Settings: Legacy pydantic-settings configuration (re-exported for compatibility)
"""

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

# Re-export from parent config.py for backwards compatibility
# Import the Settings class and settings instance from the parent module
import sys
from pathlib import Path

# Add parent directory to path temporarily to import config.py
_parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_parent_dir))
try:
    # Import from config.py (not config package)
    import importlib.util
    _spec = importlib.util.spec_from_file_location("config_module", _parent_dir / "config.py")
    _config_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_config_module)
    
    Settings = _config_module.Settings
    settings = _config_module.settings
    create_output_session = _config_module.create_output_session
finally:
    sys.path.pop(0)

# Aliases for clarity
SMALL_LLM_CONFIG = small_llm_config
LARGE_LLM_CONFIG = large_llm_config
DEFAULT_CONFIG = default_config

__all__ = [
    # New extraction config
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
    # Legacy settings (re-exported for compatibility)
    "Settings",
    "settings",
    "create_output_session",
]
