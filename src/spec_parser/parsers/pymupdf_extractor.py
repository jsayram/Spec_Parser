"""
PyMuPDF extractor for structured content extraction from PDFs.

Uses PyMuPDF4LLM in page-chunks mode for multimodal extraction with full provenance.
Supports parallel page processing with ThreadPoolExecutor for performance.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple, Callable
import pymupdf
import pymupdf4llm
from loguru import logger
from tqdm import tqdm

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
from spec_parser.parsers.text_table_extractor import TextBasedTableExtractor
from spec_parser.parsers.layout_detector import LayoutDetector


class PyMuPDFExtractor:
    """
    Extract structured content from PDF using PyMuPDF4LLM.
    Uses page-chunks mode for multimodal extraction with full provenance.
    """

    def __init__(self, pdf_path: Path, preload_to_ram: bool = True):
        """Initialize extractor with PDF path.
        
        Args:
            pdf_path: Path to the PDF file
            preload_to_ram: If True, load entire PDF into RAM before processing.
                           Faster for parallel extraction but uses more memory.
                           A 236-page PDF typically uses ~20-50MB RAM.
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise PDFExtractionError(f"PDF not found: {pdf_path}")

        self.doc = None
        self.pdf_name = self.pdf_path.stem
        self.layout_detector = LayoutDetector()
        self.preload_to_ram = preload_to_ram
        self._pdf_bytes = None  # Will hold PDF data if preloaded

    def __enter__(self):
        """Context manager entry"""
        if self.preload_to_ram:
            # Load entire PDF into RAM - eliminates disk I/O during extraction
            with open(self.pdf_path, 'rb') as f:
                self._pdf_bytes = f.read()
            self.doc = pymupdf.open(stream=self._pdf_bytes, filetype="pdf")
            size_mb = len(self._pdf_bytes) / (1024 * 1024)
            logger.info(f"Preloaded PDF to RAM: {self.pdf_name} ({len(self.doc)} pages, {size_mb:.1f} MB)")
        else:
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

        # Extract using pymupdf4llm - some pages may fail table detection
        # so we try with tables first, then without if it fails
        md_dict = None
        try:
            md_dict = pymupdf4llm.to_markdown(
                self.doc,
                pages=[page_num - 1],
                page_chunks=True,
                write_images=True,
                image_path=str(settings.image_dir) if settings.image_dir else None,
            )
        except Exception as e:
            logger.debug(f"pymupdf4llm with tables failed on page {page_num}: {e}")
            # Retry without tables (fallback for problematic pages)
            try:
                md_dict = pymupdf4llm.to_markdown(
                    self.doc,
                    pages=[page_num - 1],
                    page_chunks=True,
                    write_images=True,
                    image_path=str(settings.image_dir) if settings.image_dir else None,
                    table_strategy="none",  # Disable table extraction
                )
                logger.debug(f"Page {page_num}: extracted without table detection")
            except Exception as e2:
                logger.warning(f"pymupdf4llm fallback also failed on page {page_num}: {e2}")
                # Continue with empty markdown - we'll still extract blocks manually

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

        # Combine all blocks before layout analysis
        all_blocks = text_blocks + image_blocks + table_blocks + graphics_blocks
        
        # Apply layout detection for proper reading order
        if all_blocks:
            page_width = page.rect.width
            page_height = page.rect.height
            
            try:
                layout = self.layout_detector.analyze_layout(
                    all_blocks, page_width, page_height
                )
                all_blocks = self.layout_detector.reorder_blocks(all_blocks, layout)
                logger.debug(
                    f"Page {page_num}: Detected {layout.num_columns} columns, "
                    f"reordered {len(all_blocks)} blocks"
                )
            except Exception as e:
                logger.warning(f"Layout detection failed for page {page_num}: {e}")
                # Continue with original ordering
        
        # Add all blocks with citations
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

    def extract_all_pages(
        self, 
        max_pages: int = None,
        max_workers: int = 4,
        parallel: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[PageBundle]:
        """Extract content from all pages with optional parallel processing.
        
        Args:
            max_pages: Optional limit on number of pages to extract (for debugging)
            max_workers: Number of parallel workers for extraction (default 4)
            parallel: Enable parallel extraction (default True, set False for debugging)
            progress_callback: Optional callback(current, total) for progress updates
            
        Returns:
            List of PageBundle objects, one per successfully extracted page
        """
        if not self.doc:
            raise PDFExtractionError("PDF not opened. Use context manager.")

        total_pages = len(self.doc)
        pages_to_process = min(max_pages, total_pages) if max_pages else total_pages
        page_numbers = list(range(1, pages_to_process + 1))
        
        bundles: List[PageBundle] = []
        failed_pages: List[int] = []
        
        if parallel and max_workers > 1 and len(page_numbers) > 1:
            bundles, failed_pages = self._extract_pages_parallel(
                page_numbers, max_workers, progress_callback
            )
        else:
            bundles, failed_pages = self._extract_pages_sequential(
                page_numbers, progress_callback
            )
        
        # Sort bundles by page number (parallel processing may return out of order)
        bundles.sort(key=lambda b: b.page)
        
        if failed_pages:
            logger.warning(f"Failed to extract {len(failed_pages)} pages: {failed_pages}")
        
        logger.info(
            f"Extracted {len(bundles)}/{pages_to_process} pages from {self.pdf_name} "
            f"(parallel={parallel}, workers={max_workers})"
        )
        return bundles
    
    def _extract_pages_sequential(
        self,
        page_numbers: List[int],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[List[PageBundle], List[int]]:
        """Extract pages sequentially (single-threaded).
        
        Args:
            page_numbers: List of page numbers to extract
            progress_callback: Optional progress callback
            
        Returns:
            Tuple of (successful bundles, failed page numbers)
        """
        bundles = []
        failed_pages = []
        total = len(page_numbers)
        
        for idx, page_num in enumerate(tqdm(page_numbers, desc="Extracting pages", unit="page")):
            try:
                bundle = self.extract_page(page_num)
                bundles.append(bundle)
            except Exception as e:
                logger.error(f"Failed to extract page {page_num}: {e}")
                failed_pages.append(page_num)
            
            if progress_callback:
                progress_callback(idx + 1, total)
        
        return bundles, failed_pages
    
    def _extract_pages_parallel(
        self,
        page_numbers: List[int],
        max_workers: int,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[List[PageBundle], List[int]]:
        """Extract pages in parallel using ThreadPoolExecutor.
        
        Note: PyMuPDF is thread-safe for reading operations.
        
        Args:
            page_numbers: List of page numbers to extract
            max_workers: Maximum number of concurrent workers
            progress_callback: Optional progress callback
            
        Returns:
            Tuple of (successful bundles, failed page numbers)
        """
        bundles = []
        failed_pages = []
        total = len(page_numbers)
        completed = 0
        
        logger.info(f"Starting parallel extraction with {max_workers} workers for {total} pages")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all page extraction tasks
            future_to_page = {
                executor.submit(self._extract_page_safe, page_num): page_num
                for page_num in page_numbers
            }
            
            # Process completed futures with progress bar
            with tqdm(total=total, desc="Extracting pages (parallel)", unit="page") as pbar:
                for future in as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        bundle = future.result()
                        if bundle:
                            bundles.append(bundle)
                        else:
                            failed_pages.append(page_num)
                    except Exception as e:
                        logger.error(f"Parallel extraction failed for page {page_num}: {e}")
                        failed_pages.append(page_num)
                    
                    completed += 1
                    pbar.update(1)
                    
                    if progress_callback:
                        progress_callback(completed, total)
        
        return bundles, failed_pages
    
    def _extract_page_safe(self, page_num: int) -> Optional[PageBundle]:
        """Thread-safe wrapper for page extraction.
        
        Args:
            page_num: Page number to extract (1-indexed)
            
        Returns:
            PageBundle if successful, None if failed
        """
        try:
            return self.extract_page(page_num)
        except Exception as e:
            logger.error(f"Error extracting page {page_num}: {e}")
            return None

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
        """
        Extract tables with bboxes.
        
        Uses PyMuPDF table detection first, then enhances empty tables
        with text-based extraction as fallback.
        """
        blocks = []
        
        # Try PyMuPDF table detection first
        # Note: find_tables() can return None on some pages (image-only, scanned, etc.)
        try:
            tables = page.find_tables()
        except Exception as e:
            logger.debug(f"Table detection failed on page {page_num}: {e}")
            tables = None
        
        # Early return if no tables found
        if tables is None:
            return blocks
        
        # Get text dictionary for text-based extraction fallback
        text_dict = page.get_text("dict")
        text_extractor = TextBasedTableExtractor()

        # Safely iterate over tables - TableFinder may fail during iteration
        try:
            table_list = list(tables)  # Convert to list to catch iteration errors early
        except Exception as e:
            logger.debug(f"Failed to iterate over tables on page {page_num}: {e}")
            table_list = []

        for idx, table in enumerate(table_list):
            bbox = tuple(table.bbox)

            # Convert table to markdown
            markdown_table = None
            try:
                markdown_table = table.to_markdown()
                
                # Check if table is empty (header-only)
                if markdown_table:
                    lines = [l.strip() for l in markdown_table.split('\n') if l.strip()]
                    # If only 2 lines (header + separator), it's empty
                    if len(lines) <= 2:
                        logger.debug(f"Table {page_num}_{idx+1} is empty, trying text-based extraction")
                        markdown_table = None
                        
            except Exception as e:
                logger.warning(f"Failed to convert table to markdown: {e}")
                markdown_table = None
            
            # If PyMuPDF failed or returned empty table, try text-based extraction
            if not markdown_table:
                try:
                    enhanced = text_extractor.enhance_empty_table(bbox, text_dict)
                    if enhanced:
                        markdown_table = enhanced
                        logger.info(f"Enhanced empty table {page_num}_{idx+1} with text-based extraction")
                except Exception as e:
                    logger.warning(f"Text-based table extraction failed: {e}")

            blocks.append(
                TableBlock(
                    type="table",
                    bbox=bbox,
                    citation="",
                    table_ref=f"table_{page_num}_{idx+1}",
                    markdown_table=markdown_table,
                )
            )
        
        # Also try pure text-based extraction for tables PyMuPDF might have missed
        try:
            text_tables = text_extractor.extract_tables_from_text_dict(
                text_dict, 
                page.rect  # Use page.rect instead of page.bbox
            )
            
            for idx, (bbox, markdown_table) in enumerate(text_tables):
                # Check if this table overlaps with existing tables
                overlaps = False
                for existing_block in blocks:
                    if self._bboxes_overlap(bbox, existing_block.bbox):
                        overlaps = True
                        break
                
                if not overlaps:
                    table_ref = f"table_{page_num}_text_{idx+1}"
                    blocks.append(
                        TableBlock(
                            type="table",
                            bbox=bbox,
                            citation="",
                            table_ref=table_ref,
                            markdown_table=markdown_table,
                        )
                    )
                    logger.debug(f"Added text-based table {table_ref}")
                    
        except Exception as e:
            logger.warning(f"Text-based table detection failed: {e}")

        return blocks
    
    def _bboxes_overlap(self, bbox1: Tuple[float, float, float, float], 
                        bbox2: Tuple[float, float, float, float]) -> bool:
        """Check if two bounding boxes overlap."""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Check for no overlap (easier to reason about)
        no_overlap = (x1_max < x2_min or x2_max < x1_min or
                     y1_max < y2_min or y2_max < y1_min)
        
        return not no_overlap

    def _extract_graphics(self, page, page_num: int) -> List[GraphicsBlock]:
        """Extract graphics cluster bboxes (vector graphics)"""
        blocks = []
        drawings = page.get_drawings()

        # Minimum size threshold to filter out borders/lines
        MIN_DIMENSION_PX = 20

        # Group drawings by proximity (simplified - just use individual drawings)
        for idx, drawing in enumerate(drawings):
            # Get bbox from drawing
            rect = drawing.get("rect")
            if rect:
                bbox = tuple(rect)
                
                # Filter out small graphics (likely table borders/lines)
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                if width < MIN_DIMENSION_PX or height < MIN_DIMENSION_PX:
                    continue

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
