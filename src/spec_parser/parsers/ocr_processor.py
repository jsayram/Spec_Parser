"""
Intelligent OCR processing with text-check to avoid duplication.

Only runs OCR on regions without selectable text.
Uses ImagePreprocessor module for improved accuracy.
"""

import pytesseract
from PIL import Image
import pymupdf
from typing import List, Optional, Tuple
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle, OCRResult, TextBlock
from spec_parser.parsers.image_preprocessor import ImagePreprocessor
from spec_parser.utils.bbox_utils import bbox_overlap, bbox_distance
from spec_parser.config import settings
from spec_parser.exceptions import OCRError


class OCRProcessor:
    """
    Intelligent OCR processing with text-check to avoid duplication.
    Only runs OCR on regions without selectable text.
    """

    def __init__(
        self,
        dpi: int = 300,
        confidence_threshold: float = 0.7,
        enable_preprocessing: bool = True,
        contrast_factor: float = 1.5,
        sharpness_factor: float = 2.0,
    ):
        """
        Initialize OCR processor.

        Args:
            dpi: Rendering DPI for quality
            confidence_threshold: Minimum confidence to accept OCR results
            enable_preprocessing: Enable image preprocessing for better OCR
            contrast_factor: Contrast enhancement multiplier (1.0 = no change)
            sharpness_factor: Sharpness enhancement multiplier (1.0 = no change)
        """
        self.dpi = dpi
        self.confidence_threshold = confidence_threshold
        self.enable_preprocessing = enable_preprocessing
        self.contrast_factor = contrast_factor
        self.sharpness_factor = sharpness_factor
        
        # Initialize preprocessor if enabled
        self._preprocessor = (
            ImagePreprocessor(contrast_factor, sharpness_factor)
            if enable_preprocessing
            else None
        )

    def process_page(
        self, page_bundle: PageBundle, pdf_page
    ) -> List[OCRResult]:
        """Process all OCR candidates on a page.
        
        Identifies pictures + graphics, checks for selectable text,
        renders to bitmap and runs OCR on candidates without text.
        """
        ocr_results = []

        # Get OCR candidates (pictures and graphics)
        candidates = page_bundle.get_blocks_by_type(
            "picture"
        ) + page_bundle.get_blocks_by_type("graphics")

        logger.info(
            f"Processing {len(candidates)} OCR candidates on page {page_bundle.page}"
        )

        for candidate in candidates:
            # Check if region has selectable text
            if self._has_selectable_text(pdf_page, candidate.bbox):
                logger.debug(
                    f"Skipping OCR for {candidate.citation} - has selectable text"
                )
                continue

            # Render region and run OCR
            try:
                image = self._render_region(pdf_page, candidate.bbox)
                
                # Apply preprocessing if enabled
                if self.enable_preprocessing:
                    image = self._preprocess_image(image)
                
                text, confidence = self._run_ocr(image)

                if confidence >= self.confidence_threshold:
                    ocr_result = OCRResult(
                        bbox=candidate.bbox,
                        text=text,
                        confidence=confidence,
                        source="tesseract",
                        citation="",
                        associated_block=candidate.citation,
                        language=settings.ocr_language,
                    )
                    ocr_results.append(ocr_result)
                    logger.debug(
                        f"OCR extracted text from {candidate.citation} "
                        f"(confidence: {confidence:.2f})"
                    )
                else:
                    logger.warning(
                        f"Low OCR confidence {confidence:.2f} for {candidate.citation}"
                    )

            except Exception as e:
                logger.error(f"OCR failed for {candidate.citation}: {e}")

        logger.info(
            f"OCR complete: {len(ocr_results)} results from {len(candidates)} candidates"
        )
        return ocr_results

    def _has_selectable_text(
        self, pdf_page, bbox: Tuple[float, float, float, float]
    ) -> bool:
        """Check if bbox region contains extractable text."""
        words = pdf_page.get_text("words")

        for word in words:
            word_bbox = tuple(word[:4])  # First 4 elements are bbox
            if bbox_overlap(bbox, word_bbox):
                return True

        return False

    def _render_region(
        self, pdf_page, bbox: Tuple[float, float, float, float]
    ) -> Image.Image:
        """Render bbox region to high-DPI bitmap."""
        page_rect = pdf_page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # Clip bbox to page boundaries to avoid "tile cannot extend outside image" errors
        x0, y0, x1, y1 = bbox
        x0 = max(0, min(x0, page_width))
        y0 = max(0, min(y0, page_height))
        x1 = max(0, min(x1, page_width))
        y1 = max(0, min(y1, page_height))
        
        # Ensure valid bbox (x1 > x0 and y1 > y0)
        if x1 <= x0 or y1 <= y0:
            # Invalid bbox, return blank image
            return Image.new("RGB", (1, 1), color="white")
        
        clipped_bbox = (x0, y0, x1, y1)
        
        # Calculate zoom factor for DPI
        zoom = self.dpi / 72  # 72 is default DPI
        mat = pymupdf.Matrix(zoom, zoom)

        # Render region
        clip = pymupdf.Rect(clipped_bbox)
        pix = pdf_page.get_pixmap(matrix=mat, clip=clip)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        return img

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Apply preprocessing to improve OCR accuracy.
        
        Delegates to ImagePreprocessor module.

        Args:
            image: Original PIL Image

        Returns:
            Preprocessed PIL Image optimized for OCR
        """
        if self._preprocessor:
            return self._preprocessor.preprocess(image)
        return image

    def _otsu_threshold(self, img_array) -> int:
        """
        Calculate Otsu's threshold for binarization.
        
        Delegates to ImagePreprocessor for compatibility with tests.

        Args:
            img_array: Grayscale image as numpy array

        Returns:
            Optimal threshold value (0-255)
        """
        if self._preprocessor:
            return self._preprocessor._otsu_threshold(img_array)
        return 127  # Default fallback

    def _run_ocr(self, image: Image.Image) -> Tuple[str, float]:
        """
        Run Tesseract OCR on image.

        Args:
            image: PIL Image to process

        Returns:
            Tuple of (extracted_text, confidence_score)
        """
        try:
            # Get detailed OCR data
            data = pytesseract.image_to_data(
                image,
                lang=settings.ocr_language,
                output_type=pytesseract.Output.DICT,
            )

            # Extract text and calculate average confidence
            text_parts = []
            confidences = []

            for i, conf in enumerate(data["conf"]):
                if conf > 0:  # Valid confidence
                    text = data["text"][i]
                    if text.strip():
                        text_parts.append(text)
                        confidences.append(conf)

            text = " ".join(text_parts)
            avg_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.0
            )

            # Normalize confidence to 0-1 range (Tesseract gives 0-100)
            avg_confidence = avg_confidence / 100.0

            return text, avg_confidence

        except Exception as e:
            raise OCRError(f"Tesseract OCR failed: {e}")

    def _find_nearest_caption(
        self,
        bbox: Tuple[float, float, float, float],
        text_blocks: List[TextBlock],
    ) -> Optional[TextBlock]:
        """
        Find nearest caption using bbox_distance.
        Look for patterns: "Figure", "Fig.", "Table", etc.

        Args:
            bbox: Bounding box of image/graphics
            text_blocks: List of text blocks to search

        Returns:
            Nearest caption block or None
        """
        import re

        caption_patterns = [
            r"\bFigure\s+\d+",
            r"\bFig\.\s*\d+",
            r"\bTable\s+\d+",
            r"\bDiagram\s+\d+",
            r"\bChart\s+\d+",
        ]

        candidates = []

        for block in text_blocks:
            # Check if block contains caption pattern
            for pattern in caption_patterns:
                if re.search(pattern, block.content, re.IGNORECASE):
                    distance = bbox_distance(bbox, block.bbox)
                    candidates.append((distance, block))
                    break

        if candidates:
            # Return nearest caption
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        return None
