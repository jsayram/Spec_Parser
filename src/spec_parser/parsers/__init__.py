"""Parsers package exports"""

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.parsers.ocr_processor import OCRProcessor
from spec_parser.parsers.image_preprocessor import ImagePreprocessor
from spec_parser.parsers.markdown_pipeline import (
    MarkdownPipeline,
    MarkdownMerger,  # Legacy alias
    DocumentAssembler,  # Legacy alias
    build_markdown,  # Legacy function
)
from spec_parser.parsers.json_sidecar import JSONSidecarWriter

__all__ = [
    "PyMuPDFExtractor",
    "OCRProcessor",
    "ImagePreprocessor",
    "MarkdownPipeline",
    "MarkdownMerger",
    "DocumentAssembler",
    "build_markdown",
    "JSONSidecarWriter",
]
