# GitHub Copilot Instructions for Spec Parser and Normalizer

## Project Overview

This is a **V1 greenfield project** for parsing and normalizing POCT1 (Point-of-Care Testing) specifications using PyMuPDF4LLM with mandatory citations and full provenance tracking.

## Critical Rules

### 1. V1 Greenfield Approach
- **This is ALWAYS Version 1** - treat all code as brand new
- **NO backwards compatibility code** - never write compatibility layers or migration code
- **NO upgrade/update mentions** - never reference "upgrading from", "migrating to", or "deprecated"
- **NO legacy support** - assume clean slate, no prior versions exist
- All code, comments, and documentation should reflect this is the initial implementation

### 2. Code Structure Requirements
- **Keep ALL Python files under 300 lines of code**
- If a file approaches 300 lines, break it into specialized modules
- Import functionality from other modules rather than duplicating code
- Maintain Single Responsibility Principle - one module, one purpose
- Use clear, descriptive module and function names

### 3. Citation-First Architecture
- **MANDATORY: Every extracted element MUST have provenance**
- Every block must include `{page, bbox, source}` metadata
- Source types: `"text"`, `"ocr"`, `"graphics"`
- Never discard positional information
- All extracted data must be traceable back to exact source location in PDF
- Include confidence scores for OCR results

### 4. Environment and Execution
- **ALWAYS run Python in virtual environment from project root**
- Use `/Users/jramirez/Git/Spec_Parser/.venv/bin/python` for execution
- All dependencies must be in `requirements.txt` or `requirements-dev.txt`
- Never use system Python or global packages
- Working directory must be `/Users/jramirez/Git/Spec_Parser`

### 5. Cross-Platform Support
- Support Windows, macOS, and Linux equally
- **Use `pathlib.Path` for all file operations** - never use string path manipulation
- Never hardcode paths or use platform-specific separators (`\` or `/`)
- Use `os.path.join()` or `pathlib` for path construction
- Test code works on all platforms

### 6. Testing Requirements
- **Test-heavy approach** - aim for >80% code coverage
- Write unit tests for every module
- Write integration tests for pipelines
- Test edge cases: empty PDFs, image-only PDFs, text-only PDFs, corrupted files
- Validate citation completeness in all tests
- Use fixtures in `tests/fixtures/` for test data
- Never skip tests or leave TODO test stubs

### 7. No Information Loss
- **Preserve ALL positional data** from source documents
- Never discard metadata, bboxes, or provenance information
- Store raw PDF + extracted images + OCR results + JSON sidecar
- If unsure whether to keep data, keep it
- Traceability is more important than storage efficiency

## Technical Guidelines

### PDF Processing with PyMuPDF4LLM
- Use `page_chunks=True` mode for multimodal extraction
- Extract text, images, tables, and graphics with bboxes
- Enable `extract_words=True` for text-check before OCR
- Store `page_boxes` with class + bbox + markdown position slice
- Never lose image positions from original document

### OCR Processing
- **Check for selectable text before running OCR** to avoid duplication
- Use region-based OCR (render bbox to bitmap), not full-page OCR
- Treat both picture blocks AND graphics cluster bboxes as OCR candidates
- High-DPI rendering (300+ DPI) for accuracy
- Track OCR confidence per region
- Use pytesseract for OCR engine

### Markdown Output with Citations
- Insert inline OCR annotations near image references
- Use citation footnotes: `[^p12_img3]` linking to page + bbox
- Calculate vertical/horizontal distance for caption proximity
- Build citation index at end of document
- Human-readable format with complete provenance

### JSON Sidecar for Machine Processing
- Per-page bundles: `{page, markdown, blocks, ocr}`
- Each block includes: `{type, bbox, md_slice, image_ref, citation, source}`
- OCR entries include: `{bbox, text, confidence, source, citation}`
- Machine-readable, deterministic parsing
- Easy to diff and version control

### POCT1 Entity Extraction
- Extract message definitions (e.g., `OBS.R01`, `OPL.R01`, `QCN.R01`)
- Extract field tables with name, type, optionality, cardinality
- Extract XML snippets and schemas
- Extract vendor extension namespaces
- Attach provenance to every extracted entity: `{page, bbox, source, confidence}`

### Search and Indexing
- Use FAISS for semantic vector search
- Use BM25 for keyword search
- Default embedding model: `all-MiniLM-L6-v2` (lightweight, cross-platform, CPU-only)
- Store embeddings with citation metadata
- Return search results with full provenance

## Code Style

### Imports
```python
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field
from loguru import logger
```

### Type Hints
- Use type hints for all function parameters and return values
- Use Pydantic models for structured data
- Use `Optional[]` for nullable values
- Use `List[]`, `Dict[]`, `Tuple[]` for collections

### Error Handling
```python
from src.spec_parser.exceptions import PDFExtractionError, OCRError

try:
    result = extract_pdf(pdf_path)
except PDFExtractionError as e:
    logger.error(f"Failed to extract PDF: {e}")
    raise
```

### Logging
```python
from loguru import logger

logger.info(f"Processing page {page_num} with {len(blocks)} blocks")
logger.debug(f"OCR confidence: {confidence}")
logger.warning(f"Low OCR confidence: {confidence}")
logger.error(f"Failed to process: {error}")
```

### Configuration
- Use `.env` files for configuration (never hardcode)
- Use `python-dotenv` to load environment variables
- Provide `.env.example` with all required variables
- Use `pydantic` Settings for type-safe config

## File Organization

```
src/spec_parser/
├── parsers/          # PDF parsing (pymupdf_extractor, ocr_processor, md_merger)
├── extractors/       # POCT1 entity extraction (spec_graph)
├── models/           # Pydantic data models (page_bundle, citation)
├── search/           # FAISS + BM25 indexing and search
├── embeddings/       # Embedding model management
├── llm/              # LLM integration (prompt_builder, llm_interface)
└── utils/            # Utilities (file_handler, logger, bbox_utils)
```

## Provenance Guarantees

Every implementation must guarantee:
1. **Never lose content** - store raw PDF, raw MD, extracted images, OCR sidecar
2. **Every fact has provenance** - page + bbox + source (text vs OCR vs graphics)
3. **Normalization is repeatable** - mapping rules versioned, OCR confidence tracked
4. **Human review supported** - POCT coordinator can see where each rule came from
5. **Full auditability** - complete chain from extracted data → source document location

## Example Citation Structure

```python
{
    "citation_id": "p12_img3",
    "page": 12,
    "bbox": [100.5, 200.0, 500.0, 400.0],
    "source": "ocr",
    "confidence": 0.87,
    "content_type": "picture",
    "file_reference": "page12_img3.png"
}
```

## Common Patterns

### Reading Files
```python
from pathlib import Path

def read_pdf(pdf_path: Path) -> dict:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    # Process...
```

### Bbox Distance Calculation
```python
def bbox_distance(bbox1: Tuple[float, float, float, float],
                  bbox2: Tuple[float, float, float, float]) -> float:
    """Calculate vertical + horizontal distance between two bboxes."""
    x1_min, y1_min, x1_max, y1_max = bbox1
    x2_min, y2_min, x2_max, y2_max = bbox2
    
    # Calculate center points
    center1_x = (x1_min + x1_max) / 2
    center1_y = (y1_min + y1_max) / 2
    center2_x = (x2_min + x2_max) / 2
    center2_y = (y2_min + y2_max) / 2
    
    # Manhattan distance
    return abs(center1_x - center2_x) + abs(center1_y - center2_y)
```

### Text Check Before OCR
```python
def has_selectable_text(page: Page, bbox: Tuple[float, float, float, float]) -> bool:
    """Check if bbox region contains selectable text."""
    words = page.get_text("words")
    for word in words:
        word_bbox = word[:4]
        if bbox_overlap(bbox, word_bbox):
            return True
    return False
```

## What to Avoid

❌ Backwards compatibility code
❌ Migration scripts or upgrade paths
❌ Files over 300 lines
❌ Hardcoded file paths
❌ Missing citations or provenance
❌ Discarding positional metadata
❌ Platform-specific code
❌ Untested code
❌ Running OCR on regions with selectable text
❌ Losing image positions from original document
❌ Missing type hints
❌ Ignoring errors silently
❌ Creating summary documents or status reports (unless explicitly requested)

## What to Always Do

✅ Treat as V1 greenfield project
✅ Keep files under 300 lines
✅ Include citations on every extracted element
✅ Preserve all positional data
✅ Use pathlib for cross-platform paths
✅ Run Python in venv from project root
✅ Write comprehensive tests
✅ Use type hints everywhere
✅ Log important operations
✅ Handle errors explicitly
✅ Check for text before OCR
✅ Track confidence scores
✅ Support human review with clear provenance
✅ Respond directly without creating status/summary documents

---

**Remember: This is Version 1. No backwards compatibility. Citations are mandatory. Test everything.**
