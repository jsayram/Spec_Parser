"""
Entity extraction modules for Phase 2.5.

Deterministic extraction of structured entities from PDF specs.
"""

from .base_extractor import BaseExtractor
from .message_parser import MessageParser

__all__ = [
    "BaseExtractor",
    "MessageParser",
]
