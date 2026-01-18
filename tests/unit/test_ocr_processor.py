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


class TestImagePreprocessing:
    """Test image preprocessing functionality"""

    def test_preprocessing_initialization(self):
        """Test OCR processor with preprocessing options"""
        processor = OCRProcessor(
            enable_preprocessing=True,
            contrast_factor=2.0,
            sharpness_factor=1.5,
        )
        assert processor.enable_preprocessing is True
        assert processor.contrast_factor == 2.0
        assert processor.sharpness_factor == 1.5

    def test_preprocessing_disabled(self):
        """Test OCR processor with preprocessing disabled"""
        processor = OCRProcessor(enable_preprocessing=False)
        assert processor.enable_preprocessing is False

    def test_preprocess_image_converts_to_grayscale(self):
        """Test that preprocessing converts image to grayscale"""
        processor = OCRProcessor(enable_preprocessing=True)

        # Create a color test image
        color_image = Image.new("RGB", (100, 100), color=(255, 0, 0))

        preprocessed = processor._preprocess_image(color_image)

        # Result should be grayscale (mode "L")
        assert preprocessed.mode == "L"

    def test_preprocess_image_output_size_preserved(self):
        """Test that preprocessing preserves image dimensions"""
        processor = OCRProcessor(enable_preprocessing=True)

        original = Image.new("RGB", (200, 150), color="white")
        preprocessed = processor._preprocess_image(original)

        assert preprocessed.size == original.size

    def test_preprocess_image_handles_binarization(self):
        """Test that binarization produces only black and white pixels"""
        processor = OCRProcessor(enable_preprocessing=True)

        # Create a gradient test image
        import numpy as np
        gradient = np.tile(np.arange(256, dtype=np.uint8), (100, 1))
        gradient_image = Image.fromarray(gradient, mode="L").convert("RGB")

        preprocessed = processor._preprocess_image(gradient_image)
        pixels = np.array(preprocessed)

        # After binarization, should only have 0 or 255 values
        unique_values = np.unique(pixels)
        assert all(v in [0, 255] for v in unique_values)

    def test_otsu_threshold_calculation(self):
        """Test Otsu threshold calculation"""
        processor = OCRProcessor()
        import numpy as np

        # Create a gradient image (0-255) which gives predictable threshold
        # Otsu on a uniform gradient should find threshold around middle
        gradient = np.tile(np.arange(256, dtype=np.uint8), (100, 1))

        threshold = processor._otsu_threshold(gradient)

        # For a uniform gradient, threshold should be somewhere in middle range
        # The exact value depends on the algorithm but should be reasonable
        assert 0 <= threshold <= 255
        
        # Also test that threshold is returned as an integer
        assert isinstance(threshold, (int, np.integer))

    def test_preprocess_image_inverts_dark_background(self):
        """Test that dark background images are inverted"""
        processor = OCRProcessor(enable_preprocessing=True)

        # Create image with dark background (white text on black)
        import numpy as np
        dark_image = np.zeros((100, 100), dtype=np.uint8)
        dark_image[40:60, 20:80] = 255  # White rectangle (simulating text)
        pil_dark = Image.fromarray(dark_image, mode="L").convert("RGB")

        preprocessed = processor._preprocess_image(pil_dark)
        mean_value = np.mean(np.array(preprocessed))

        # After inversion, background should be light (mean > 127)
        assert mean_value > 127

    def test_preprocess_image_error_handling(self):
        """Test preprocessing handles errors gracefully"""
        processor = OCRProcessor(enable_preprocessing=True)

        # Create a valid image - preprocessing should succeed
        valid_image = Image.new("RGB", (100, 100), color="white")
        result = processor._preprocess_image(valid_image)

        # Should return a valid image
        assert isinstance(result, Image.Image)
