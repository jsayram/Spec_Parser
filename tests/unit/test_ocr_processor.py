"""
Unit tests for OCRProcessor.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PIL import Image
import pymupdf

from spec_parser.parsers.ocr_processor import OCRProcessor
from spec_parser.schemas.page_bundle import PageBundle, PictureBlock, TextBlock
from spec_parser.exceptions import OCRError


class TestOCRProcessor:
    """Test OCRProcessor"""

    def test_processor_initialization(self):
        """Test OCR processor initialization"""
        processor = OCRProcessor(dpi=300, confidence_threshold=0.7)
        assert processor.dpi == 300
        assert processor.confidence_threshold == 0.7

    def test_has_selectable_text_with_text(self):
        """Test text-check detects selectable text"""
        processor = OCRProcessor()

        # Mock PDF page with text in bbox
        mock_page = Mock()
        mock_page.get_text.return_value = [
            (50.0, 50.0, 150.0, 75.0, "test word", 0, 0, 0),  # bbox overlaps
        ]

        bbox = (0.0, 0.0, 200.0, 100.0)
        assert processor._has_selectable_text(mock_page, bbox) is True

    def test_has_selectable_text_without_text(self):
        """Test text-check returns False when no text"""
        processor = OCRProcessor()

        # Mock PDF page without text in bbox
        mock_page = Mock()
        mock_page.get_text.return_value = [
            (500.0, 500.0, 600.0, 550.0, "far away", 0, 0, 0),  # no overlap
        ]

        bbox = (0.0, 0.0, 200.0, 100.0)
        assert processor._has_selectable_text(mock_page, bbox) is False

    @patch("spec_parser.parsers.ocr_processor.pytesseract.image_to_data")
    def test_run_ocr_success(self, mock_tesseract):
        """Test successful OCR extraction"""
        processor = OCRProcessor()

        # Mock Tesseract output
        mock_tesseract.return_value = {
            "text": ["Hello", "World", ""],
            "conf": [95, 90, -1],
        }

        # Create test image
        image = Image.new("RGB", (100, 100), color="white")

        text, confidence = processor._run_ocr(image)

        assert text == "Hello World"
        assert 0.90 <= confidence <= 0.95

    @patch("spec_parser.parsers.ocr_processor.pytesseract.image_to_data")
    def test_run_ocr_low_confidence(self, mock_tesseract):
        """Test OCR with low confidence"""
        processor = OCRProcessor()

        # Mock Tesseract output with low confidence
        mock_tesseract.return_value = {
            "text": ["blurry", "text"],
            "conf": [30, 25],
        }

        image = Image.new("RGB", (100, 100), color="white")
        text, confidence = processor._run_ocr(image)

        assert confidence < 0.5

    def test_find_nearest_caption_with_match(self):
        """Test finding nearest caption with figure pattern"""
        processor = OCRProcessor()

        # Create text blocks with caption
        caption_block = TextBlock(
            type="text",
            bbox=(100.0, 50.0, 200.0, 75.0),
            citation="p1_txt1",
            md_slice=(0, 10),
            content="Figure 1: Test diagram",
        )

        other_block = TextBlock(
            type="text",
            bbox=(100.0, 500.0, 200.0, 525.0),
            citation="p1_txt2",
            md_slice=(10, 20),
            content="Some other text",
        )

        text_blocks = [caption_block, other_block]
        bbox = (100.0, 100.0, 200.0, 200.0)

        nearest = processor._find_nearest_caption(bbox, text_blocks)

        assert nearest == caption_block

    def test_find_nearest_caption_no_match(self):
        """Test finding caption when none exists"""
        processor = OCRProcessor()

        # Create text blocks without captions
        text_blocks = [
            TextBlock(
                type="text",
                bbox=(100.0, 50.0, 200.0, 75.0),
                citation="p1_txt1",
                md_slice=(0, 10),
                content="Regular text here",
            )
        ]

        bbox = (100.0, 100.0, 200.0, 200.0)
        nearest = processor._find_nearest_caption(bbox, text_blocks)

        assert nearest is None
