"""
Document assembler for creating master markdown from all pages.

Creates a single markdown file combining all extracted pages.
"""

from pathlib import Path
from typing import List
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle
from spec_parser.parsers.md_merger import MarkdownMerger


class DocumentAssembler:
    """
    Assemble multi-page documents into master markdown.
    
    Creates:
    1. Master markdown: Complete document (all pages combined)
    2. Per-page markdown: Individual page files for reference
    """

    def __init__(self):
        """Initialize document assembler"""
        self.merger = MarkdownMerger()

    def assemble_master_markdown(
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
        markdown = self.merger._insert_ocr_annotations(markdown, page_bundle)

        # Remove any existing citation section
        citation_marker = "\n\n---\n\n## Citations\n\n"
        if citation_marker in markdown:
            markdown = markdown.split(citation_marker)[0]

        return markdown

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
        master_md = self.assemble_master_markdown(page_bundles, pdf_name)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(master_md, encoding="utf-8")

        logger.info(
            f"Wrote master markdown: {output_path} ({len(master_md)} chars)"
        )
