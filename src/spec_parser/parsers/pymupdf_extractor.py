"""
PyMuPDF extractor for structured content extraction from PDFs.

Uses PyMuPDF4LLM in page-chunks mode for multimodal extraction with full provenance.
"""

from pathlib import Path
from typing import List, Optional, Tuple
import pymupdf
import pymupdf4llm
from loguru import logger

from spec_parser.schemas.page_bundle import (
    PageBundle,
    TextBlock,
    PictureBlock,
    TableBlock,
    GraphicsBlock,
)
from spec_parser.schemas.citation import Citation
from spec_parser.config import settings
from spec_parser.exceptions import PDFExtractionError


class PyMuPDFExtractor:
    """
    Extract structured content from PDF using PyMuPDF4LLM.
    Uses page-chunks mode for multimodal extraction with full provenance.
    """

    def __init__(self, pdf_path: Path):
        """Initialize extractor with PDF path"""
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise PDFExtractionError(f"PDF not found: {pdf_path}")

        self.doc = None
        self.pdf_name = self.pdf_path.stem

    def __enter__(self):
        """Context manager entry"""
        self.doc = pymupdf.open(str(self.pdf_path))
        logger.info(f"Opened PDF: {self.pdf_name} ({len(self.doc)} pages)")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.doc:
            self.doc.close()
            logger.debug(f"Closed PDF: {self.pdf_name}")

    def extract_page(self, page_num: int) -> PageBundle:
        """
        Extract content from a single page.

        Args:
            page_num: Page number (1-indexed)

        Returns:
            PageBundle with markdown, blocks, and citations
        """
        if not self.doc:
            raise PDFExtractionError("PDF not opened. Use context manager.")

        if page_num < 1 or page_num > len(self.doc):
            raise PDFExtractionError(
                f"Invalid page number: {page_num} (PDF has {len(self.doc)} pages)"
            )

        logger.info(f"Extracting page {page_num}/{len(self.doc)} from {self.pdf_name}")

        # Get page (0-indexed in PyMuPDF)
        page = self.doc[page_num - 1]

        # Extract using pymupdf4llm
        md_dict = pymupdf4llm.to_markdown(
            self.doc,
            pages=[page_num - 1],
            page_chunks=True,
            write_images=True,
            image_path=str(settings.image_dir) if settings.image_dir else None,
        )

        # Initialize page bundle
        bundle = PageBundle(
            page=page_num,
            markdown="",
            blocks=[],
            ocr=[],
            citations={},
            metadata={},
        )

        # Get markdown content
        if isinstance(md_dict, list) and len(md_dict) > 0:
            bundle.markdown = md_dict[0].get("text", "")
        elif isinstance(md_dict, dict):
            bundle.markdown = md_dict.get("text", "")
        else:
            bundle.markdown = ""

        # Extract components
        text_blocks = self._extract_text_blocks(page, page_num)
        image_blocks = self._extract_images(page, page_num)
        table_blocks = self._extract_tables(page, page_num)
        graphics_blocks = self._extract_graphics(page, page_num)

        # Add all blocks with citations
        all_blocks = text_blocks + image_blocks + table_blocks + graphics_blocks
        for idx, block in enumerate(all_blocks):
            citation = self._generate_citation(
                page_num, block.type, idx, block.bbox
            )
            block.citation = citation.citation_id
            bundle.add_block(block, citation)

        logger.info(
            f"Extracted {len(bundle.blocks)} blocks from page {page_num}: "
            f"{len(text_blocks)} text, {len(image_blocks)} images, "
            f"{len(table_blocks)} tables, {len(graphics_blocks)} graphics"
        )
        return bundle

    def extract_all_pages(self) -> List[PageBundle]:
        """Extract content from all pages"""
        if not self.doc:
            raise PDFExtractionError("PDF not opened. Use context manager.")

        bundles = []
        for page_num in range(1, len(self.doc) + 1):
            try:
                bundle = self.extract_page(page_num)
                bundles.append(bundle)
            except Exception as e:
                logger.error(f"Failed to extract page {page_num}: {e}")
                # Continue with other pages

        logger.info(f"Extracted {len(bundles)}/{len(self.doc)} pages from {self.pdf_name}")
        return bundles

    def _extract_text_blocks(self, page, page_num: int) -> List[TextBlock]:
        """Extract text blocks with position data"""
        blocks = []

        # Get text blocks with bboxes
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                bbox = tuple(block.get("bbox", (0, 0, 0, 0)))

                # Extract text content
                lines = block.get("lines", [])
                content_parts = []
                for line in lines:
                    spans = line.get("spans", [])
                    for span in spans:
                        content_parts.append(span.get("text", ""))

                content = " ".join(content_parts)

                if content.strip():
                    blocks.append(
                        TextBlock(
                            type="text",
                            bbox=bbox,
                            citation="",  # Set by extract_page
                            md_slice=(0, 0),  # Placeholder
                            content=content,
                        )
                    )

        return blocks

    def _extract_images(self, page, page_num: int) -> List[PictureBlock]:
        """Extract images from page"""
        blocks = []
        images = page.get_image_info()

        for idx, img in enumerate(images):
            bbox = tuple(img.get("bbox", (0, 0, 0, 0)))

            # Generate image filename
            image_ref = f"{self.pdf_name}_p{page_num}_img{idx+1}.png"
            if settings.image_dir:
                image_path = settings.image_dir / image_ref
            else:
                image_path = Path(image_ref)

            # Extract and save image
            try:
                xref = img.get("xref")
                if xref:
                    pix = pymupdf.Pixmap(self.doc, xref)
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        pix.save(str(image_path))
                    else:  # CMYK: convert first
                        pix1 = pymupdf.Pixmap(pymupdf.csRGB, pix)
                        pix1.save(str(image_path))
                        pix1 = None
                    pix = None
                    logger.debug(f"Saved image: {image_ref}")
            except Exception as e:
                logger.warning(f"Failed to save image {image_ref}: {e}")
                continue

            blocks.append(
                PictureBlock(
                    type="picture",
                    bbox=bbox,
                    citation="",
                    image_ref=image_ref,
                    source="pdf",
                )
            )

        return blocks

    def _extract_tables(self, page, page_num: int) -> List[TableBlock]:
        """Extract tables with bboxes"""
        blocks = []
        tables = page.find_tables()

        for idx, table in enumerate(tables):
            bbox = tuple(table.bbox)

            # Convert table to markdown
            try:
                markdown_table = table.to_markdown()
            except Exception as e:
                logger.warning(f"Failed to convert table to markdown: {e}")
                markdown_table = None

            blocks.append(
                TableBlock(
                    type="table",
                    bbox=bbox,
                    citation="",
                    table_ref=f"table_{page_num}_{idx+1}",
                    markdown_table=markdown_table,
                )
            )

        return blocks

    def _extract_graphics(self, page, page_num: int) -> List[GraphicsBlock]:
        """Extract graphics cluster bboxes (vector graphics)"""
        blocks = []
        drawings = page.get_drawings()

        # Group drawings by proximity (simplified - just use individual drawings)
        for idx, drawing in enumerate(drawings):
            # Get bbox from drawing
            rect = drawing.get("rect")
            if rect:
                bbox = tuple(rect)

                blocks.append(
                    GraphicsBlock(
                        type="graphics",
                        bbox=bbox,
                        citation="",
                        source="vector",
                    )
                )

        return blocks

    def _generate_citation(
        self, page: int, block_type: str, index: int, bbox: Tuple[float, float, float, float]
    ) -> Citation:
        """Generate citation for extracted element"""
        type_abbrev = {
            "text": "txt",
            "picture": "img",
            "table": "tbl",
            "graphics": "gfx",
        }.get(block_type, "unk")

        citation_id = f"p{page}_{type_abbrev}{index+1}"

        return Citation(
            citation_id=citation_id,
            page=page,
            bbox=bbox,
            source="text" if block_type in ["text", "table"] else "graphics",
            content_type=block_type,
        )
