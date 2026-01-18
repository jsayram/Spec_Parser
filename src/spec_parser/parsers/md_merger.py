"""
Markdown merger for combining PyMuPDF markdown with OCR results.

Adds inline annotations and citation footnotes.
"""

import re
from typing import List, Dict
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle, OCRResult
from spec_parser.exceptions import ValidationError


class MarkdownMerger:
    """
    Merge PyMuPDF markdown with OCR results.
    Adds inline annotations and citation footnotes.
    """

    def __init__(self):
        """Initialize markdown merger"""
        pass

    def merge(self, page_bundle: PageBundle) -> str:
        """
        Create enhanced markdown with OCR and citations.

        Steps:
        1. Start with base markdown from page_bundle
        2. Insert OCR annotations near image references
        3. Add citation anchors for text blocks
        4. Build citation index at end

        Args:
            page_bundle: PageBundle with markdown and OCR results

        Returns:
            Enhanced markdown with citations
        """
        markdown = page_bundle.markdown

        # Insert OCR annotations
        markdown = self._insert_ocr_annotations(markdown, page_bundle)

        # Add citation anchors (optional - can be verbose)
        # markdown = self._add_citation_anchors(markdown, page_bundle)

        # Build citation index
        citation_index = self._build_citation_index(page_bundle)

        # Append citation index
        if citation_index:
            markdown += "\n\n---\n\n## Citations\n\n" + citation_index

        return markdown

    def _insert_ocr_annotations(
        self, markdown: str, page_bundle: PageBundle
    ) -> str:
        """
        Insert OCR results near image references.

        Format:
        ![Figure 3](images/page12_img3.png) [^p12_img3]

        [^p12_img3]: OCR: "Message structure for OBS.R01..."

        Args:
            markdown: Base markdown content
            page_bundle: PageBundle with OCR results

        Returns:
            Markdown with OCR annotations
        """
        if not page_bundle.ocr:
            return markdown

        # Find image references in markdown
        image_pattern = r"!\[([^\]]*)\]\(([^\)]+)\)"
        images = re.finditer(image_pattern, markdown)

        # Build OCR lookup by image reference
        ocr_by_image = {}
        for ocr in page_bundle.ocr:
            if ocr.associated_block:
                block = page_bundle.get_block_by_citation(ocr.associated_block)
                if block and hasattr(block, "image_ref"):
                    ocr_by_image[block.image_ref] = ocr

        # Insert OCR annotations
        offset = 0
        for match in images:
            alt_text = match.group(1)
            image_path = match.group(2)
            image_name = image_path.split("/")[-1]

            if image_name in ocr_by_image:
                ocr = ocr_by_image[image_name]
                citation_ref = f"[^{ocr.citation}]"

                # Insert citation reference after image
                insert_pos = match.end() + offset
                markdown = (
                    markdown[:insert_pos] + f" {citation_ref}" + markdown[insert_pos:]
                )
                offset += len(f" {citation_ref}")

        return markdown

    def _add_citation_anchors(
        self, markdown: str, page_bundle: PageBundle
    ) -> str:
        """
        Add citation anchors for text blocks (optional).

        This can make markdown verbose - use sparingly.

        Args:
            markdown: Base markdown content
            page_bundle: PageBundle with blocks

        Returns:
            Markdown with citation anchors
        """
        # Implementation would add [^citation_id] markers
        # Not implemented to avoid cluttering markdown
        return markdown

    def _build_citation_index(self, page_bundle: PageBundle) -> str:
        """
        Build citation index for footnotes.

        Format:
        [^p12_img3]: Page 12, Image 3 (100.0, 200.0, 500.0, 400.0)
                     Source: OCR, Confidence: 0.87
                     Content: "Message structure for OBS.R01..."

        Args:
            page_bundle: PageBundle with citations

        Returns:
            Markdown citation index
        """
        lines = []

        # Add block citations
        for citation_id, citation in page_bundle.citations.items():
            lines.append(f"[^{citation_id}]: {citation.to_markdown_footnote()}")

        # Add OCR citations
        for ocr in page_bundle.ocr:
            if ocr.citation:
                text_preview = (
                    ocr.text[:100] + "..." if len(ocr.text) > 100 else ocr.text
                )
                lines.append(
                    f"[^{ocr.citation}]: OCR Result (Confidence: {ocr.confidence:.2f})"
                )
                lines.append(f"    Text: \"{text_preview}\"")
                lines.append(
                    f"    BBox: {ocr.bbox}, Associated: {ocr.associated_block}"
                )
                lines.append("")

        return "\n".join(lines)
