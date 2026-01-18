# POCT1 Spec Parser and Normalizer - V1 Implementation Plan

**Project Status**: V1 Greenfield - No backwards compatibility, no upgrade/update code
**Date**: January 17, 2026

## Overview

Build a production-ready, test-heavy Python V1 project for parsing and normalizing POCT1 (Point-of-Care Testing) specifications using PyMuPDF4LLM's page-chunks mode for multimodal extraction with mandatory citations and full provenance tracking. Every extracted element must be traceable back to its exact position in the source document.

## Core Architecture Principles

### 1. Citation-First Architecture
- **Mandatory citations** on every extracted element
- Every block includes `{page, bbox, source}` metadata
- No information loss - all positional data preserved
- Full traceability from extracted data back to source PDF

### 2. Dual Output System
- **Human-readable Markdown**: Inline OCR annotations with citation footnotes
- **Structured JSON**: Per-page bundles with complete provenance for deterministic parsing
- Raw PDF + extracted images stored with position-encoded filenames

### 3. Smart OCR Pipeline
- PyMuPDF4LLM page-chunks mode for multimodal extraction
- Region-based OCR (not full pages) for efficiency
- Text-check before OCR to avoid duplication
- OCR candidates: picture blocks + graphics cluster bboxes (for vector diagrams)
- High-DPI region bitmap rendering
- Simple bbox vertical/horizontal distance for caption matching

### 4. Code Quality Standards
- All Python files **< 300 lines** - break into specialized modules if larger
- Test-heavy approach with high coverage
- Cross-platform support (Windows/macOS/Linux)
- Use `pathlib` for cross-platform path handling
- Always run Python in venv from project root

## Directory Structure

```
Spec_Parser/
├── .github/
│   └── copilot-instructions.md       # GitHub Copilot workspace instructions
│
├── src/
│   └── spec_parser/                  # Main package
│       ├── __init__.py
│       ├── __main__.py               # CLI entry point
│       ├── config.py                 # Configuration management
│       ├── exceptions.py             # Custom exceptions
│       │
│       ├── parsers/                  # PDF parsing modules
│       │   ├── __init__.py
│       │   ├── pymupdf_extractor.py  # PyMuPDF4LLM page-chunks extraction
│       │   ├── ocr_processor.py      # Region OCR with text-check
│       │   ├── md_merger.py          # Merge text + OCR with citations
│       │   └── json_sidecar.py       # Structured JSON writer
│       │
│       ├── extractors/               # POCT1 entity extraction
│       │   ├── __init__.py
│       │   └── spec_graph.py         # Extract messages, fields, rules with provenance
│       │
│       ├── models/                   # Pydantic data models
│       │   ├── __init__.py
│       │   ├── page_bundle.py        # Page bundle schema
│       │   └── citation.py           # Citation/provenance models
│       │
│       ├── search/                   # Semantic search
│       │   ├── __init__.py
│       │   ├── faiss_indexer.py      # FAISS vector search
│       │   └── bm25_search.py        # BM25 keyword search
│       │
│       ├── embeddings/               # Embedding models
│       │   ├── __init__.py
│       │   └── model_manager.py      # Cross-platform embedding management
│       │
│       ├── llm/                      # LLM integration (future)
│       │   ├── __init__.py
│       │   ├── prompt_builder.py     # Context assembly with citations
│       │   └── llm_interface.py      # Abstract LLM client
│       │
│       └── utils/                    # Utility functions
│           ├── __init__.py
│           ├── file_handler.py       # Cross-platform file operations
│           ├── logger.py             # Logging setup
│           └── bbox_utils.py         # Bounding box operations
│
├── tests/                            # Test suite (test-heavy)
│   ├── __init__.py
│   ├── conftest.py                   # Pytest configuration
│   ├── test_pymupdf_extractor.py     # Page-chunks extraction tests
│   ├── test_ocr_processor.py         # OCR logic tests (text-check, graphics)
│   ├── test_md_merger.py             # Caption distance, citation generation
│   ├── test_json_sidecar.py          # JSON structure validation
│   ├── test_spec_graph.py            # POCT1 entity extraction with provenance
│   ├── test_search.py                # FAISS/BM25 search tests
│   └── fixtures/                     # Test data
│       ├── text_heavy.pdf            # Text-focused PDF
│       ├── image_heavy.pdf           # Image/figure-focused PDF
│       ├── graphics_heavy.pdf        # Vector diagram PDF
│       └── expected_bundles/         # Expected JSON outputs
│
├── .gitignore                        # Python/venv/Docker ignores
├── .env.example                      # Environment variable template
├── pyproject.toml                    # Modern Python packaging (PEP 517/518)
├── requirements.txt                  # Runtime dependencies
├── requirements-dev.txt              # Development dependencies
├── Dockerfile                        # Docker containerization
└── README.md                         # Project documentation
```

## Data Models

### Page Bundle Schema (`models/page_bundle.py`)

```python
{
  "page": 12,
  "markdown": "...",
  "blocks": [
    {
      "type": "text",
      "bbox": [x0, y0, x1, y1],
      "md_slice": [start, stop],
      "citation": "p12_text_1"
    },
    {
      "type": "picture",
      "bbox": [x0, y0, x1, y1],
      "image_ref": "page12_img3.png",
      "citation": "p12_img3",
      "source": "pdf"
    },
    {
      "type": "table",
      "bbox": [x0, y0, x1, y1],
      "table_ref": "table_12_1",
      "citation": "p12_table_1"
    },
    {
      "type": "graphics",
      "bbox": [x0, y0, x1, y1],
      "citation": "p12_graphics_2",
      "source": "vector"
    }
  ],
  "ocr": [
    {
      "bbox": [x0, y0, x1, y1],
      "text": "...",
      "confidence": 0.87,
      "source": "tesseract",
      "citation": "p12_ocr_1",
      "associated_block": "p12_img3"
    }
  ]
}
```

### Citation Schema (`models/citation.py`)

```python
{
  "citation_id": "p12_img3",
  "page": 12,
  "bbox": [x0, y0, x1, y1],
  "source": "ocr" | "text" | "graphics",
  "confidence": 0.87,
  "content_type": "picture" | "table" | "text" | "graphics",
  "file_reference": "page12_img3.png"
}
```

## Pipeline Workflow

### Step 1: PyMuPDF4LLM Extraction (`parsers/pymupdf_extractor.py`)

**Input**: PDF file path
**Output**: Per-page bundles with text, images, tables, graphics bboxes

```python
# Use page-chunks mode
to_markdown(
    doc_path,
    pages=[...],
    page_chunks=True,
    write_images=True,
    image_path="output/images",
    extract_words=True  # For text-check
)
```

**Key features**:
- Extract markdown text with layout preservation
- Get `page_boxes` with class + bbox + md position slice
- Get `images[]` with bboxes and references
- Get `tables[]` with bboxes
- Get `graphics[]` cluster bboxes (for vector diagrams)
- Store raw extraction data with page metadata

### Step 2: OCR Processing (`parsers/ocr_processor.py`)

**Input**: Page bundle with images/graphics bboxes
**Output**: OCR results with confidence scores

**Logic**:
1. For each picture/graphics block:
   - Check if bbox region has selectable text (`get_text("words")` within bbox)
   - If text exists → skip OCR (avoid duplication)
   - If no text → render region to high-DPI bitmap
   - Run pytesseract on region
   - Store OCR text + confidence + bbox + source

2. Graphics cluster handling:
   - Treat graphics bboxes as OCR candidates
   - Important for vector diagram text extraction
   - Render bbox region → OCR

3. Caption proximity:
   - Calculate vertical/horizontal distance from image bbox to text blocks
   - Find nearest caption (pattern match: "Figure", "Fig.", "Table", etc.)
   - Associate OCR with nearest caption

**Key features**:
- Never duplicate existing text
- Region-based OCR (not full page)
- Track OCR confidence per region
- Preserve all bbox positions

### Step 3: Markdown Merger (`parsers/md_merger.py`)

**Input**: Page bundle + OCR results
**Output**: Enhanced markdown with inline OCR + citations

**Logic**:
1. Parse markdown and identify image/table insertion points
2. For each image reference:
   - Insert inline OCR annotation if available
   - Add citation footnote: `[^p12_img3]: Page 12, bbox [x0, y0, x1, y1], source: OCR`
3. For each text block:
   - Add citation anchor: `[^p12_text_1]`
4. Build citation index at end of document

**Output format**:
```markdown
## Section Title [^p12_text_1]

The device sends OPL.R01 to download operators... [^p12_text_2]

![Figure 3](images/page12_img3.png) [^p12_img3]

> OCR (from figure): The device sends OPL.R01 to download operators...
> Confidence: 0.87

[^p12_text_1]: Page 12, bbox [50, 100, 550, 120], source: text
[^p12_text_2]: Page 12, bbox [50, 140, 550, 180], source: text
[^p12_img3]: Page 12, bbox [100, 200, 500, 400], source: ocr, file: page12_img3.png
```

### Step 4: JSON Sidecar (`parsers/json_sidecar.py`)

**Input**: Page bundles with OCR + citations
**Output**: Structured JSON for deterministic parsing

**Features**:
- One JSON file per page or single JSON with page array
- Complete provenance metadata
- Easy to diff and version
- Machine-readable for downstream processing

### Step 5: Spec Graph Extraction (`extractors/spec_graph.py`)

**Input**: Merged page bundles (MD + JSON)
**Output**: POCT1 entity graph with citations

**Extract**:
- Message definitions (e.g., `OBS.R01`, `OPL.R01`, `QCN.R01`)
- Field tables (name, type, optionality, cardinality)
- XML snippets and schemas
- Cardinality rules (required, optional, repeating)
- Vendor extension namespaces
- Cross-references between sections

**Output format**:
```python
{
  "message": "OBS.R01",
  "description": "Observation Result",
  "fields": [
    {
      "name": "Patient ID",
      "type": "string",
      "required": True,
      "citation": "p12_text_5",
      "page": 12,
      "bbox": [x0, y0, x1, y1]
    }
  ],
  "citation": "p15_text_2",
  "page": 15,
  "bbox": [x0, y0, x1, y1],
  "source": "text"
}
```

### Step 6: Search Indexing (`search/`)

**FAISS Indexer** (`faiss_indexer.py`):
- Index page bundles using sentence-transformers
- Default model: `all-MiniLM-L6-v2` (lightweight, cross-platform)
- Store embeddings with citation metadata
- Enable semantic similarity search

**BM25 Search** (`bm25_search.py`):
- Keyword-based search using rank-bm25
- Complement to semantic search
- Fast lookup for exact terms

**Combined search**:
- Hybrid approach: BM25 + FAISS
- Return results with citations and provenance

## Dependencies

### Runtime (`requirements.txt`)
```
pymupdf4llm>=0.0.1
pymupdf>=1.23.0
pytesseract>=0.3.10
Pillow>=10.0.0
pydantic>=2.0.0
click>=8.1.0
faiss-cpu>=1.7.4
rank-bm25>=0.2.2
sentence-transformers>=2.2.0
python-dotenv>=1.0.0
loguru>=0.7.0
```

### Development (`requirements-dev.txt`)
```
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
black>=23.7.0
ruff>=0.0.285
mypy>=1.5.0
```

### System Dependencies
- Tesseract OCR (cross-platform):
  - macOS: `brew install tesseract`
  - Windows: Download installer from GitHub
  - Linux: `apt-get install tesseract-ocr`

## Environment Configuration (`.env.example`)

```bash
# OCR Configuration
OCR_ENGINE=tesseract
OCR_LANGUAGE=eng
OCR_DPI=300
OCR_CONFIDENCE_THRESHOLD=0.7

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu

# Search Configuration
FAISS_INDEX_TYPE=Flat
BM25_K1=1.5
BM25_B=0.75

# Output Paths
OUTPUT_DIR=./output
IMAGE_DIR=./output/images
JSON_DIR=./output/json
MARKDOWN_DIR=./output/markdown

# LLM Configuration (future)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## GitHub Copilot Instructions (`.github/copilot-instructions.md`)

**Key directives**:
1. **V1 Greenfield Project**: No backwards compatibility code, no upgrade/update mentions
2. **File Size Limit**: Keep Python files < 300 lines, break into specialized modules
3. **Citations Mandatory**: Every extracted element must have provenance (page, bbox, source)
4. **Testing**: Test-heavy approach, high coverage required
5. **Cross-Platform**: Use pathlib, support Windows/macOS/Linux
6. **Environment**: Always run Python in venv from project root with requirements.txt
7. **No Information Loss**: Preserve all positional data, never discard metadata
8. **Traceability**: Every fact must be traceable back to source PDF
9. **Auditability**: Support human review loop with clear citations

## CLI Interface (`src/spec_parser/__main__.py`)

```bash
# Parse PDF to markdown + JSON
python -m spec_parser parse input.pdf --output ./output

# Extract POCT1 entities
python -m spec_parser extract ./output/json --output entities.json

# Index for search
python -m spec_parser index ./output/json --index-dir ./index

# Search
python -m spec_parser search "OBS.R01 message format" --index-dir ./index
```

## Testing Strategy

### Unit Tests
- `test_pymupdf_extractor.py`: Page-chunks extraction, image/table/graphics detection
- `test_ocr_processor.py`: Text-check logic, region rendering, graphics bbox OCR
- `test_md_merger.py`: Caption distance calculation, citation generation, inline formatting
- `test_json_sidecar.py`: Schema validation, provenance completeness
- `test_spec_graph.py`: POCT1 entity extraction, citation attachment
- `test_search.py`: FAISS/BM25 indexing and retrieval

### Integration Tests
- End-to-end: PDF → page bundles → OCR → merge → extract → search
- Multi-page documents
- Mixed content (text + images + tables + graphics)
- Citation completeness validation

### Test Fixtures
- `text_heavy.pdf`: Primarily text content
- `image_heavy.pdf`: Many figures and screenshots
- `graphics_heavy.pdf`: Vector diagrams and technical drawings
- Expected outputs for validation

## Docker Support (`Dockerfile`)

```dockerfile
FROM python:3.11-slim

# Install Tesseract
RUN apt-get update && apt-get install -y tesseract-ocr

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app

# Entry point
ENTRYPOINT ["python", "-m", "spec_parser"]
```

## Provenance Guarantees

1. **Never lose content**: Store raw PDF, raw MD, extracted images, OCR sidecar
2. **Every fact has provenance**: page + bbox + source (text vs OCR vs graphics)
3. **Normalization is repeatable**: Mapping rules versioned, OCR confidence tracked
4. **Human review supported**: POCT coordinator can see where each rule came from
5. **Auditability**: Complete chain from extracted data → source document location

## Future Enhancements (Post-V1)

- LLM integration for intelligent entity extraction
- Web interface for manual review and correction
- Database backend for storing parsed specs
- API endpoints for integration with healthcare systems
- Support for additional specification formats (HL7, FHIR)
- Automated validation against POCT1-A standard
- Diff tool for comparing specification versions

## Implementation Checklist

- [ ] Create directory structure
- [ ] Set up packaging configuration (pyproject.toml, requirements.txt)
- [ ] Add .gitignore for Python/venv/Docker
- [ ] Create GitHub Copilot instructions (.github/copilot-instructions.md)
- [ ] Implement Pydantic models (page_bundle.py, citation.py)
- [ ] Build PyMuPDF extractor (pymupdf_extractor.py)
- [ ] Build OCR processor with text-check (ocr_processor.py)
- [ ] Build markdown merger with citations (md_merger.py)
- [ ] Build JSON sidecar writer (json_sidecar.py)
- [ ] Build spec graph extractor (spec_graph.py)
- [ ] Implement FAISS indexer (faiss_indexer.py)
- [ ] Implement BM25 search (bm25_search.py)
- [ ] Create CLI interface (__main__.py)
- [ ] Set up test infrastructure (conftest.py)
- [ ] Write unit tests for all modules
- [ ] Write integration tests
- [ ] Create test fixtures
- [ ] Add .env.example
- [ ] Create Dockerfile
- [ ] Test cross-platform compatibility
- [ ] Validate citation completeness
- [ ] Test with real POCT1 specification PDFs

## Success Criteria

✅ All Python files < 300 lines
✅ Every extracted element has complete citation (page, bbox, source)
✅ No information loss from PDF to output
✅ Full traceability from data → source location
✅ Test coverage > 80%
✅ Works on Windows, macOS, Linux
✅ Can run in Docker container
✅ Can drag-and-drop and run anywhere
✅ Handles text-heavy, image-heavy, and graphics-heavy PDFs
✅ OCR only regions without selectable text
✅ Human-readable MD + machine-readable JSON outputs
✅ POCT1 entity extraction with provenance
✅ Semantic + keyword search with citations

---

**Ready for implementation upon approval.**
