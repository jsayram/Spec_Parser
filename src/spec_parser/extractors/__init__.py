"""
Entity extraction modules for Phase 2.5.

Deterministic extraction of structured entities from PDF specs.
"""

from .base_extractor import BaseExtractor
from .message_parser import MessageParser
from .message_extractor import MessageExtractor  # Legacy alias for compatibility

__all__ = [
    "BaseExtractor",
    "MessageParser",
    "MessageExtractor",  # Legacy alias
]
