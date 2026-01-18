"""
Intelligent OCR processing with text-check to avoid duplication.

Only runs OCR on regions without selectable text.
"""

import pytesseract
from PIL import Image
import pymupdf
from typing import List, Optional, Tuple
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle, OCRResult, TextBlock
from spec_parser.schemas.citation import Citation
from spec_parser.utils.bbox_utils import bbox_overlap, bbox_distance
from spec_parser.config import settings
from spec_parser.exceptions import OCRError


class OCRProcessor:
    """
    Intelligent OCR processing with text-check to avoid duplication.
    Only runs OCR on regions without selectable text.
    """

    def __init__(self, dpi: int = 300, confidence_threshold: float = 0.7):
        """
        Initialize OCR processor.

        Args:
            dpi: Rendering DPI for quality
            confidence_threshold: Minimum confidence to accept OCR results
        """
        self.dpi = dpi
        self.confidence_threshold = confidence_threshold

    def process_page(
        self, page_bundle: PageBundle, pdf_page
    ) -> List[OCRResult]:
        """
        Process all OCR candidates on a page.

        Steps:
        1. Identify OCR candidates (pictures + graphics)
        2. For each candidate, check if region has selectable text
        3. If no text, render region to bitmap and run OCR
        4. Return OCR results with confidence scores

        Args:
            page_bundle: PageBundle with blocks to process
            pdf_page: PyMuPDF page object for rendering

        Returns:
            List of OCRResult objects
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
                text, confidence = self._run_ocr(image)

                if confidence >= self.confidence_threshold:
                    # Find nearest caption
                    caption_block = self._find_nearest_caption(
                        candidate.bbox, page_bundle.get_blocks_by_type("text")
                    )

                    ocr_result = OCRResult(
                        bbox=candidate.bbox,
                        text=text,
                        confidence=confidence,
                        source="tesseract",
                        citation="",  # Will be set when added to bundle
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
        """
        Check if bbox region contains extractable text.

        Args:
            pdf_page: PyMuPDF page object
            bbox: Bounding box to check

        Returns:
            True if region has selectable text
        """
        words = pdf_page.get_text("words")

        for word in words:
            word_bbox = tuple(word[:4])  # First 4 elements are bbox
            if bbox_overlap(bbox, word_bbox):
                return True

        return False

    def _render_region(
        self, pdf_page, bbox: Tuple[float, float, float, float]
    ) -> Image.Image:
        """
        Render bbox region to high-DPI bitmap.

        Args:
            pdf_page: PyMuPDF page object
            bbox: Region to render

        Returns:
            PIL Image of the region
        """
        # Get page dimensions
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
