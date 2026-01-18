# Phase 2: PDF Parsing Pipeline (Core Extraction)

**Prerequisites**: Phase 1 complete ✅
**Status**: Ready to implement
**Goal**: Build complete PDF → structured output pipeline with citations

---

## Overview

Phase 2 implements the core PDF parsing pipeline using PyMuPDF4LLM with intelligent OCR processing. The pipeline extracts:
- Text with bounding boxes and markdown formatting
- Images with position metadata
- Tables with structure preservation
- Graphics vectors that need OCR
- Complete provenance for every element

All extraction follows the citation-first architecture:
- Every extracted element gets a unique citation
- All bboxes and positions preserved
- No information loss from PDF to output
- Dual output: human-readable MD + machine-readable JSON

---

## Step 2.1: PyMuPDF Extractor (`parsers/pymupdf_extractor.py`)

**Objective**: Extract structured content from PDF using PyMuPDF4LLM's page-chunks mode, including text, images, tables, and graphics with bounding boxes.

### Key Functionality

```python
from pathlib import Path
from typing import List, Optional
import pymupdf
import pymupdf4llm
from loguru import logger

from spec_parser.models.page_bundle import (
    PageBundle, TextBlock, PictureBlock, TableBlock, GraphicsBlock
)
from spec_parser.models.citation import Citation
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
        self.doc = pymupdf.open(self.pdf_path)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.doc:
            self.doc.close()
    
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
            raise PDFExtractionError(f"Invalid page number: {page_num}")
        
        logger.info(f"Extracting page {page_num} from {self.pdf_name}")
        
        # Get page (0-indexed in PyMuPDF)
        page = self.doc[page_num - 1]
        
        # Extract using pymupdf4llm
        md_dict = pymupdf4llm.to_markdown(
            self.doc,
            pages=[page_num - 1],
            page_chunks=True,
            write_images=True,
            image_path=settings.image_dir,
            extract_words=True
        )
        
        # Initialize page bundle
        bundle = PageBundle(
            page=page_num,
            markdown="",
            blocks=[],
            ocr=[],
            citations={},
            metadata={"pdf_name": self.pdf_name}
        )
        
        # Extract components
        bundle.markdown = md_dict.get('markdown', '')
        
        text_blocks = self._extract_text_blocks(page, md_dict, page_num)
        image_blocks = self._extract_images(page, page_num)
        table_blocks = self._extract_tables(page, page_num)
        graphics_blocks = self._extract_graphics(page, page_num)
        
        # Add all blocks with citations
        for block in text_blocks + image_blocks + table_blocks + graphics_blocks:
            citation = self._generate_citation(page_num, block.type, len(bundle.blocks), block.bbox)
            block.citation = citation.citation_id
            bundle.add_block(block, citation)
        
        logger.info(f"Extracted {len(bundle.blocks)} blocks from page {page_num}")
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
        
        logger.info(f"Extracted {len(bundles)} pages from {self.pdf_name}")
        return bundles
    
    def _extract_text_blocks(self, page, md_dict, page_num: int) -> List[TextBlock]:
        """Extract text blocks with position data"""
        blocks = []
        page_boxes = md_dict.get('page_boxes', [])
        
        for idx, box in enumerate(page_boxes):
            if box.get('class') == 'text':
                bbox = box.get('bbox', (0, 0, 0, 0))
                md_slice = box.get('md_slice', (0, 0))
                content = md_dict['markdown'][md_slice[0]:md_slice[1]]
                
                blocks.append(TextBlock(
                    type="text",
                    bbox=bbox,
                    citation="",  # Set by extract_page
                    md_slice=md_slice,
                    content=content
                ))
        
        return blocks
    
    def _extract_images(self, page, page_num: int) -> List[PictureBlock]:
        """Extract images from page"""
        blocks = []
        images = page.get_image_info()
        
        for idx, img in enumerate(images):
            bbox = img.get('bbox', (0, 0, 0, 0))
            
            # Generate image filename
            image_ref = f"{self.pdf_name}_p{page_num}_img{idx+1}.png"
            image_path = settings.image_dir / image_ref
            
            # Extract and save image
            try:
                xref = img.get('xref')
                if xref:
                    pix = pymupdf.Pixmap(self.doc, xref)
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        pix.save(str(image_path))
                    else:  # CMYK: convert first
                        pix1 = pymupdf.Pixmap(pymupdf.csRGB, pix)
                        pix1.save(str(image_path))
                        pix1 = None
                    pix = None
            except Exception as e:
                logger.warning(f"Failed to save image {image_ref}: {e}")
                continue
            
            blocks.append(PictureBlock(
                type="picture",
                bbox=bbox,
                citation="",
                image_ref=image_ref,
                source="pdf"
            ))
        
        return blocks
    
    def _extract_tables(self, page, page_num: int) -> List[TableBlock]:
        """Extract tables with bboxes"""
        blocks = []
        tables = page.find_tables()
        
        for idx, table in enumerate(tables):
            bbox = table.bbox
            
            # Convert table to markdown
            try:
                markdown_table = table.to_markdown()
            except:
                markdown_table = None
            
            blocks.append(TableBlock(
                type="table",
                bbox=bbox,
                citation="",
                table_ref=f"table_{page_num}_{idx+1}",
                markdown_table=markdown_table
            ))
        
        return blocks
    
    def _extract_graphics(self, page, page_num: int) -> List[GraphicsBlock]:
        """Extract graphics cluster bboxes (vector graphics)"""
        blocks = []
        drawings = page.get_drawings()
        
        # Group drawings into clusters (simplified - just use individual drawings)
        for idx, drawing in enumerate(drawings):
            # Get bbox from drawing
            bbox = drawing.get('rect', (0, 0, 0, 0))
            
            blocks.append(GraphicsBlock(
                type="graphics",
                bbox=bbox,
                citation="",
                source="vector"
            ))
        
        return blocks
    
    def _generate_citation(self, page: int, block_type: str, index: int, bbox: tuple) -> Citation:
        """Generate citation for extracted element"""
        type_abbrev = {
            "text": "txt",
            "picture": "img",
            "table": "tbl",
            "graphics": "gfx"
        }.get(block_type, "unk")
        
        citation_id = f"p{page}_{type_abbrev}{index+1}"
        
        return Citation(
            citation_id=citation_id,
            page=page,
            bbox=bbox,
            source="text" if block_type in ["text", "table"] else "graphics",
            content_type=block_type
        )
```

### Implementation Details

- Use `pymupdf4llm.to_markdown()` with `page_chunks=True`
- Enable `extract_words=True` for text-check capability
- Enable `write_images=True` to save extracted images
- Parse `page_boxes` for layout information with bboxes
- Store raw extraction data along with processed bundles
- Generate unique citation IDs for every element
- Preserve all positional metadata
- Use context manager for proper PDF handling

### Error Handling

- Handle corrupted PDFs gracefully
- Handle encrypted/password-protected PDFs
- Handle PDFs with no extractable content
- Log warnings for skipped pages
- Continue processing other pages if one fails

### Tests Required (`tests/unit/test_pymupdf_extractor.py`)

- ✅ Extract from text-only PDF
- ✅ Extract from image-heavy PDF
- ✅ Extract from PDF with tables
- ✅ Extract from PDF with vector graphics
- ✅ Validate citation generation
- ✅ Validate bbox coordinates
- ✅ Test multi-page extraction
- ✅ Test image file naming consistency
- ✅ Test context manager usage
- ✅ Test error handling for missing PDF

**File Size**: Target <300 lines

---

## Step 2.2: OCR Processor (`parsers/ocr_processor.py`)

**Objective**: Perform intelligent OCR on image and graphics regions, with text-check to avoid duplication.

### Key Functionality

```python
import pytesseract
from PIL import Image
import pymupdf
from typing import List, Optional, Tuple
from loguru import logger

from spec_parser.models.page_bundle import PageBundle, OCRResult, TextBlock
from spec_parser.models.citation import Citation
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
    
    def process_page(self, page_bundle: PageBundle, pdf_page) -> List[OCRResult]:
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
        candidates = page_bundle.get_blocks_by_type("picture") + page_bundle.get_blocks_by_type("graphics")
        
        logger.info(f"Processing {len(candidates)} OCR candidates on page {page_bundle.page}")
        
        for candidate in candidates:
            # Check if region has selectable text
            if self._has_selectable_text(pdf_page, candidate.bbox):
                logger.debug(f"Skipping OCR for {candidate.citation} - has selectable text")
                continue
            
            # Render region and run OCR
            try:
                image = self._render_region(pdf_page, candidate.bbox)
                text, confidence = self._run_ocr(image)
                
                if confidence >= self.confidence_threshold:
                    # Find nearest caption
                    caption_block = self._find_nearest_caption(
                        candidate.bbox,
                        page_bundle.get_blocks_by_type("text")
                    )
                    
                    ocr_result = OCRResult(
                        bbox=candidate.bbox,
                        text=text,
                        confidence=confidence,
                        source="tesseract",
                        citation="",  # Will be set when added to bundle
                        associated_block=candidate.citation,
                        language=settings.ocr_language
                    )
                    ocr_results.append(ocr_result)
                    
                    logger.debug(f"OCR extracted text from {candidate.citation} (confidence: {confidence:.2f})")
                else:
                    logger.warning(f"Low OCR confidence {confidence:.2f} for {candidate.citation}")
            
            except Exception as e:
                logger.error(f"OCR failed for {candidate.citation}: {e}")
        
        return ocr_results
    
    def _has_selectable_text(self, pdf_page, bbox: Tuple[float, float, float, float]) -> bool:
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
            word_bbox = word[:4]  # First 4 elements are bbox
            if bbox_overlap(bbox, word_bbox):
                return True
        
        return False
    
    def _render_region(self, pdf_page, bbox: Tuple[float, float, float, float]) -> Image.Image:
        """
        Render bbox region to high-DPI bitmap.
        
        Args:
            pdf_page: PyMuPDF page object
            bbox: Region to render
            
        Returns:
            PIL Image of the region
        """
        # Calculate zoom factor for DPI
        zoom = self.dpi / 72  # 72 is default DPI
        mat = pymupdf.Matrix(zoom, zoom)
        
        # Render region
        clip = pymupdf.Rect(bbox)
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
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and calculate average confidence
            text_parts = []
            confidences = []
            
            for i, conf in enumerate(data['conf']):
                if conf > 0:  # Valid confidence
                    text = data['text'][i]
                    if text.strip():
                        text_parts.append(text)
                        confidences.append(conf)
            
            text = ' '.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Normalize confidence to 0-1 range (Tesseract gives 0-100)
            avg_confidence = avg_confidence / 100.0
            
            return text, avg_confidence
        
        except Exception as e:
            raise OCRError(f"Tesseract OCR failed: {e}")
    
    def _find_nearest_caption(
        self,
        bbox: Tuple[float, float, float, float],
        text_blocks: List[TextBlock]
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
            r'\bFigure\s+\d+',
            r'\bFig\.\s*\d+',
            r'\bTable\s+\d+',
            r'\bDiagram\s+\d+',
            r'\bChart\s+\d+'
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
```

### Implementation Details

- Use pytesseract for OCR
- High-DPI rendering (300+ DPI) for accuracy
- Text-check before OCR to avoid duplication
- Handle both picture blocks and graphics blocks
- Calculate distance to find nearest captions
- Track OCR confidence per region
- Skip OCR if confidence threshold not met
- Generate citations for OCR results

### Pattern Matching for Captions

- Regex patterns for "Figure X", "Fig. X", "Table X"
- Proximity threshold (find nearest match)
- Prefer text blocks above or below image

### Error Handling

- Handle OCR failures gracefully
- Handle unreadable images
- Handle non-English text (configurable)
- Log warnings for low-confidence results

### Tests Required (`tests/unit/test_ocr_processor.py`)

- ✅ Text-check detects selectable text
- ✅ Text-check skips OCR when text present
- ✅ OCR runs on image regions without text
- ✅ Graphics blocks processed as OCR candidates
- ✅ Caption proximity detection works
- ✅ Confidence threshold filtering
- ✅ High-DPI rendering produces readable results
- ✅ Handle OCR failures gracefully

**File Size**: Target <300 lines

---

## Step 2.3: Markdown Merger (`parsers/md_merger.py`)

**Objective**: Merge PyMuPDF markdown with OCR results, adding inline annotations and citation footnotes.

### Key Functionality

```python
import re
from typing import List
from loguru import logger

from spec_parser.models.page_bundle import PageBundle, OCRResult
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
        
        # Add citation anchors
        markdown = self._add_citation_anchors(markdown, page_bundle)
        
        # Build citation index
        citation_index = self._build_citation_index(page_bundle)
        
        # Append citation index
        if citation_index:
            markdown += "\n\n---\n\n## Citations\n\n" + citation_index
        
        return markdown
    
    def _insert_ocr_annotations(self, markdown: str, page_bundle: PageBundle) -> str:
        """
        Insert OCR results near image references.
        
        Format:
        ![Figure 3](images/page12_img3.png) [^p12_img3]
        
        > OCR (from figure): The device sends OPL.R01...
        > Confidence: 0.87
        """
        for ocr in page_bundle.ocr:
            if not ocr.associated_block:
                continue
            
            # Find associated block
            citation = page_bundle.get_citation(ocr.associated_block)
            if not citation or not citation.file_reference:
                continue
            
            # Find image reference in markdown
            pattern = re.escape(citation.file_reference)
            match = re.search(rf'!\[.*?\]\(.*?{pattern}.*?\)', markdown)
            
            if match:
                # Insert OCR annotation after image
                annotation = f"\n\n> **OCR (from figure)**: {ocr.text}\n> _Confidence: {ocr.confidence:.2f}_\n"
                
                # Insert after image reference
                insert_pos = match.end()
                markdown = markdown[:insert_pos] + annotation + markdown[insert_pos:]
        
        return markdown
    
    def _add_citation_anchors(self, markdown: str, page_bundle: PageBundle) -> str:
        """
        Add citation reference marks throughout text.
        
        Args:
            markdown: Original markdown
            page_bundle: PageBundle with citations
            
        Returns:
            Markdown with citation anchors
        """
        # For each text block, add citation at end of content
        for block in page_bundle.get_blocks_by_type("text"):
            if hasattr(block, 'md_slice'):
                # Add citation anchor at end of slice
                start, stop = block.md_slice
                if stop <= len(markdown):
                    anchor = f" [^{block.citation}]"
                    markdown = markdown[:stop] + anchor + markdown[stop:]
        
        return markdown
    
    def _build_citation_index(self, page_bundle: PageBundle) -> str:
        """
        Build citation footnotes at end of document.
        
        Format:
        [^p12_text_1]: Page 12, bbox [50, 100, 550, 120], source: text
        [^p12_img3]: Page 12, bbox [100, 200, 500, 400], source: ocr, file: page12_img3.png
        """
        lines = []
        
        for citation_id, citation_obj in page_bundle.citations.items():
            footnote = citation_obj.to_markdown_footnote()
            lines.append(footnote)
        
        return "\n".join(lines)
```

### Implementation Details

- Parse markdown to identify structure
- Use regex to find image references
- Calculate insertion points for OCR annotations
- Format citations as markdown footnotes
- Preserve original markdown structure
- Human-readable output
- Link citations to original positions

### Citation Format

```markdown
[^citation_id]: Page {page}, bbox [{x0}, {y0}, {x1}, {y1}], source: {source}[, file: {file_ref}][, confidence: {conf}]
```

### Tests Required (`tests/unit/test_md_merger.py`)

- ✅ Insert OCR annotations near images
- ✅ Add citation anchors to text
- ✅ Build complete citation index
- ✅ Preserve markdown structure
- ✅ Handle pages without images
- ✅ Handle pages without OCR results
- ✅ Test with multiple images/OCR results

**File Size**: Target <250 lines

---

## Step 2.4: JSON Sidecar Writer (`parsers/json_sidecar.py`)

**Objective**: Write structured JSON output with complete provenance for machine processing.

### Key Functionality

```python
import json
from pathlib import Path
from typing import List
from datetime import datetime
from loguru import logger

from spec_parser.models.page_bundle import PageBundle
from spec_parser.utils.file_handler import ensure_directory, write_json
from spec_parser.config import settings

class JSONSidecarWriter:
    """Write structured JSON sidecars for machine processing"""
    
    def __init__(self, output_dir: Path = None):
        """
        Initialize writer with output directory.
        
        Args:
            output_dir: Directory for JSON output (default from settings)
        """
        self.output_dir = output_dir or settings.json_dir
        ensure_directory(self.output_dir)
    
    def write_page_bundle(self, page_bundle: PageBundle, pdf_name: str) -> Path:
        """
        Write single page bundle to JSON.
        
        Args:
            page_bundle: PageBundle to write
            pdf_name: Name of source PDF
            
        Returns:
            Path to written JSON file
        """
        filename = f"{pdf_name}_p{page_bundle.page}.json"
        output_path = self.output_dir / filename
        
        data = self._serialize_bundle(page_bundle)
        data['metadata']['pdf_name'] = pdf_name
        data['metadata']['extracted_at'] = datetime.utcnow().isoformat()
        
        write_json(data, output_path, indent=2)
        logger.info(f"Wrote page bundle to {output_path}")
        
        return output_path
    
    def write_document(self, page_bundles: List[PageBundle], pdf_name: str) -> Path:
        """
        Write all page bundles to single JSON file.
        
        Args:
            page_bundles: List of PageBundle objects
            pdf_name: Name of source PDF
            
        Returns:
            Path to written JSON file
        """
        filename = f"{pdf_name}_document.json"
        output_path = self.output_dir / filename
        
        data = {
            "document": pdf_name,
            "pages": [self._serialize_bundle(bundle) for bundle in page_bundles],
            "metadata": {
                "extracted_at": datetime.utcnow().isoformat(),
                "extractor_version": "1.0.0",
                "total_pages": len(page_bundles)
            }
        }
        
        write_json(data, output_path, indent=2)
        logger.info(f"Wrote {len(page_bundles)} pages to {output_path}")
        
        return output_path
    
    def _serialize_bundle(self, page_bundle: PageBundle) -> dict:
        """
        Convert PageBundle to JSON-serializable dict.
        
        Args:
            page_bundle: PageBundle to serialize
            
        Returns:
            Dictionary ready for JSON serialization
        """
        return page_bundle.model_dump()
```

### JSON Structure

```json
{
  "document": "spec_name.pdf",
  "pages": [
    {
      "page": 1,
      "markdown": "...",
      "blocks": [...],
      "ocr": [...],
      "citations": {...}
    }
  ],
  "metadata": {
    "extracted_at": "2026-01-17T10:30:00Z",
    "extractor_version": "1.0.0",
    "total_pages": 50
  }
}
```

### Implementation Details

- Use Pydantic's `.model_dump()` for serialization
- Pretty-print JSON with indentation
- Include metadata timestamps
- One file per page + one file for full document
- Easy to diff and version control

### Tests Required (`tests/unit/test_json_sidecar.py`)

- ✅ Write single page bundle
- ✅ Write multi-page document
- ✅ Validate JSON structure
- ✅ Round-trip: write then read back
- ✅ Verify all citations present
- ✅ Check metadata fields

**File Size**: Target <150 lines

---

## Phase 2 Completion Checklist

### Core Modules
- [ ] `parsers/pymupdf_extractor.py` implemented
- [ ] `parsers/ocr_processor.py` implemented
- [ ] `parsers/md_merger.py` implemented
- [ ] `parsers/json_sidecar.py` implemented

### Unit Tests
- [ ] Test PyMuPDF extraction
- [ ] Test OCR text-check logic
- [ ] Test OCR processing
- [ ] Test markdown merging
- [ ] Test JSON writing

### Integration Tests
- [ ] End-to-end: PDF → PageBundle → OCR → Markdown + JSON
- [ ] Test with text-only PDF
- [ ] Test with image-heavy PDF
- [ ] Test with table PDF
- [ ] Citation completeness validation

### Verification
- [ ] All files < 300 lines
- [ ] All functions have type hints
- [ ] All public methods have docstrings
- [ ] Error handling in place
- [ ] Logging throughout
- [ ] Run tests: `pytest tests/unit/test_parsers*.py`

---

## Expected Outcome

After completing Phase 2, you will have:

✅ **Complete PDF → structured output pipeline**
✅ **Dual output: human-readable MD + machine-readable JSON**
✅ **Every element has citation with provenance**
✅ **OCR only runs where needed (text-check)**
✅ **All files < 300 lines**
✅ **Ready for entity extraction** in Phase 3

---

## Next Steps

Once Phase 2 is complete, proceed to **Phase 3: Entity Extraction & Search** (see `step3.md`)
