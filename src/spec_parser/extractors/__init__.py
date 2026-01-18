"""
Entity extraction modules for Phase 2.5.

Deterministic extraction of structured entities from PDF specs.
"""

from .base_extractor import BaseExtractor
from .message_extractor import MessageExtractor

__all__ = [
    "BaseExtractor",
    "MessageExtractor",
]
