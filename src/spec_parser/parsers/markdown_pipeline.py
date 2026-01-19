"""
Unified markdown generation pipeline with OCR integration.

Consolidates markdown_builder, md_merger, and document_assembler into
a single pipeline for generating markdown from PageBundles.
"""

import re
from pathlib import Path
from typing import List, Dict
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle, OCRResult
from spec_parser.exceptions import ValidationError


class MarkdownPipeline:
    """
    Unified markdown generation pipeline with OCR integration.
    
    Provides:
    - Simple markdown building from PageBundles
    - OCR annotation merging
    - Master document assembly with citations
    """

    def __init__(self):
        """Initialize markdown pipeline"""
        pass

    def build_simple_markdown(self, pages: List[PageBundle]) -> str:
        """
        Build simple markdown document from extracted pages.
        
        Lightweight function for quick markdown generation without
        OCR annotations or citation index.
        
        Args:
            pages: List of PageBundle objects with blocks
        
        Returns:
            Complete markdown document
        """
        markdown_lines = []
        
        for page_bundle in pages:
            markdown_lines.append(f"\n# Page {page_bundle.page}\n")
            
            for block in page_bundle.blocks:
                # Handle different block types with their specific content fields
                if block.type == "text" and hasattr(block, 'content') and block.content:
                    markdown_lines.append(block.content)
                    markdown_lines.append("\n")
                elif block.type == "table" and hasattr(block, 'markdown_table') and block.markdown_table:
                    markdown_lines.append(block.markdown_table)
                    markdown_lines.append("\n")
                elif block.type == "picture" and hasattr(block, 'image_ref') and block.image_ref:
                    markdown_lines.append(f"![{block.image_ref}]({block.image_ref})")
                    markdown_lines.append("\n")
        
        return "\n".join(markdown_lines)

    def merge_page_with_ocr(self, page_bundle: PageBundle) -> str:
        """
        Create enhanced markdown with OCR and citations for single page.

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

        # Build citation index
        citation_index = self._build_citation_index(page_bundle)

        # Append citation index
        if citation_index:
            markdown += "\n\n---\n\n## Citations\n\n" + citation_index

        return markdown

    def assemble_master_document(
        self, page_bundles: List[PageBundle], pdf_name: str
    ) -> str:
        """
        Create master markdown from all pages.

        Args:
            page_bundles: List of PageBundle objects (one per page)
            pdf_name: Name of source PDF

        Returns:
            Complete markdown document with all pages
        """
        logger.info(f"Assembling master markdown from {len(page_bundles)} pages")

        # Build document header
        lines = [
            f"# {pdf_name}",
            "",
            f"**Total Pages:** {len(page_bundles)}",
            "",
            "---",
            "",
        ]

        # Add each page with separator
        for i, bundle in enumerate(page_bundles, 1):
            # Page header
            lines.append(f"## Page {bundle.page}")
            lines.append("")

            # Page content (without citations - they'll be at end)
            page_md = self._get_page_content_without_citations(bundle)
            lines.append(page_md)

            # Page separator (except for last page)
            if i < len(page_bundles):
                lines.append("")
                lines.append("---")
                lines.append("")

        # Build master citation index for entire document
        citation_index = self._build_master_citation_index(page_bundles)
        if citation_index:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## Master Citation Index")
            lines.append("")
            lines.append(citation_index)

        return "\n".join(lines)

    def write_master_markdown(
        self,
        page_bundles: List[PageBundle],
        pdf_name: str,
        output_path: Path,
    ) -> None:
        """
        Write master markdown file.

        Args:
            page_bundles: List of PageBundle objects
            pdf_name: Name of source PDF
            output_path: Path to write markdown file
        """
        master_md = self.assemble_master_document(page_bundles, pdf_name)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(master_md, encoding="utf-8")

        logger.info(
            f"Wrote master markdown: {output_path} ({len(master_md)} chars)"
        )

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
        images = list(re.finditer(image_pattern, markdown))

        # Build OCR lookup by image reference
        ocr_by_image = {}
        for ocr in page_bundle.ocr:
            if ocr.associated_block:
                block = page_bundle.get_block_by_citation(ocr.associated_block)
                if block and hasattr(block, "image_ref"):
                    ocr_by_image[block.image_ref] = ocr

        # Insert OCR annotations (reverse order to maintain positions)
        for match in reversed(images):
            alt_text = match.group(1)
            image_path = match.group(2)
            image_name = image_path.split("/")[-1]

            if image_name in ocr_by_image:
                ocr = ocr_by_image[image_name]
                citation_ref = f" [^{ocr.citation}]"

                # Insert citation reference after image
                insert_pos = match.end()
                markdown = (
                    markdown[:insert_pos] + citation_ref + markdown[insert_pos:]
                )

        return markdown

    def _get_page_content_without_citations(self, page_bundle: PageBundle) -> str:
        """
        Get page markdown content without citation footnotes.

        Args:
            page_bundle: PageBundle for single page

        Returns:
            Page markdown content (no citations section)
        """
        markdown = page_bundle.markdown

        # Insert OCR annotations
        markdown = self._insert_ocr_annotations(markdown, page_bundle)

        # Remove any existing citation section
        citation_marker = "\n\n---\n\n## Citations\n\n"
        if citation_marker in markdown:
            markdown = markdown.split(citation_marker)[0]

        return markdown

    def _build_citation_index(self, page_bundle: PageBundle) -> str:
        """
        Build citation index for footnotes (single page).

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

    def _build_master_citation_index(
        self, page_bundles: List[PageBundle]
    ) -> str:
        """
        Build master citation index for all pages.

        Args:
            page_bundles: List of all PageBundle objects

        Returns:
            Complete citation index markdown
        """
        lines = []

        for bundle in page_bundles:
            # Add page section header
            lines.append(f"### Page {bundle.page}")
            lines.append("")

            # Add block citations
            for citation_id, citation in bundle.citations.items():
                lines.append(f"[^{citation_id}]: {citation.to_markdown_footnote()}")

            # Add OCR citations
            for ocr in bundle.ocr:
                if ocr.citation:
                    text_preview = (
                        ocr.text[:80] + "..." if len(ocr.text) > 80 else ocr.text
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
