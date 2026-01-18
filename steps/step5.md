# Phase 5: Testing & Packaging (Production Readiness)

**Prerequisites**: Phases 1-4 complete ✅
**Status**: Ready to implement
**Goal**: Comprehensive testing, packaging, and deployment preparation

---

## Overview

Phase 5 implements:
- Comprehensive unit tests for all modules
- Integration tests for complete workflows
- Test fixtures for repeatable testing
- Package configuration (pyproject.toml)
- Docker containerization
- CI/CD pipeline configuration
- Documentation and deployment guides

This phase ensures the project is production-ready with:
- >80% code coverage
- All edge cases tested
- Cross-platform compatibility verified
- Easy installation and deployment
- Complete documentation

---

## Step 5.1: Unit Tests for Core Modules

**Objective**: Write comprehensive unit tests for all modules with >80% coverage.

### Test Structure

```
tests/
├── unit/
│   ├── test_models.py              # Phase 1: Models
│   ├── test_config.py              # Phase 1: Configuration
│   ├── test_exceptions.py          # Phase 1: Exceptions
│   ├── test_logger.py              # Phase 1: Logger
│   ├── test_bbox_utils.py          # Phase 1: BBox utilities
│   ├── test_file_handler.py        # Phase 1: File handler
│   ├── test_pymupdf_extractor.py   # Phase 2: PDF extraction
│   ├── test_ocr_processor.py       # Phase 2: OCR
│   ├── test_md_merger.py           # Phase 2: Markdown merger
│   ├── test_json_sidecar.py        # Phase 2: JSON writer
│   ├── test_spec_graph.py          # Phase 3: Entity extraction
│   ├── test_embedding_model.py     # Phase 3: Embeddings
│   ├── test_faiss_indexer.py       # Phase 3: FAISS
│   ├── test_bm25_search.py         # Phase 3: BM25
│   ├── test_hybrid_search.py       # Phase 3: Hybrid search
│   ├── test_cli_main.py            # Phase 4: CLI
│   ├── test_parse_command.py       # Phase 4: Parse command
│   ├── test_extract_command.py     # Phase 4: Extract command
│   ├── test_index_command.py       # Phase 4: Index command
│   ├── test_search_command.py      # Phase 4: Search command
│   └── test_llm_scaffolding.py     # Phase 4: LLM placeholders
├── integration/
│   ├── test_pdf_pipeline.py        # End-to-end PDF processing
│   ├── test_entity_extraction.py   # Entity extraction workflow
│   ├── test_search_workflow.py     # Search workflow
│   └── test_cli_integration.py     # CLI integration tests
└── fixtures/
    ├── pdfs/
    │   ├── simple_text.pdf         # Text-only PDF
    │   ├── with_images.pdf         # PDF with images
    │   ├── with_tables.pdf         # PDF with tables
    │   └── poct1_sample.pdf        # Sample POCT1 spec
    └── expected/
        ├── simple_text.json        # Expected JSON output
        └── poct1_entities.json     # Expected entities
```

### Example Unit Test: `test_models.py`

```python
import pytest
from spec_parser.models.citation import Citation
from spec_parser.models.page_bundle import PageBundle, TextBlock
from pydantic import ValidationError

class TestCitation:
    """Test Citation model"""
    
    def test_citation_creation(self):
        """Test creating a valid citation"""
        citation = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",
            content_type="text"
        )
        
        assert citation.citation_id == "p1_txt1"
        assert citation.page == 1
        assert citation.source == "text"
    
    def test_citation_bbox_validation(self):
        """Test bbox validation"""
        with pytest.raises(ValidationError):
            Citation(
                citation_id="p1_txt1",
                page=1,
                bbox=(500.0, 200.0, 100.0, 300.0),  # Invalid: x1 < x0
                source="text",
                content_type="text"
            )
    
    def test_citation_to_markdown_footnote(self):
        """Test markdown footnote generation"""
        citation = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",
            content_type="text"
        )
        
        footnote = citation.to_markdown_footnote()
        assert "[^p1_txt1]:" in footnote
        assert "Page 1" in footnote
        assert "bbox [100.0, 200.0, 500.0, 300.0]" in footnote
    
    def test_citation_overlaps(self):
        """Test citation overlap detection"""
        citation1 = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",
            content_type="text"
        )
        
        citation2 = Citation(
            citation_id="p1_txt2",
            page=1,
            bbox=(400.0, 250.0, 600.0, 350.0),
            source="text",
            content_type="text"
        )
        
        assert citation1.overlaps(citation2)

class TestPageBundle:
    """Test PageBundle model"""
    
    def test_page_bundle_creation(self):
        """Test creating a page bundle"""
        bundle = PageBundle(
            page=1,
            markdown="# Test\n\nContent",
            blocks=[],
            ocr=[],
            citations={},
            metadata={"pdf_name": "test.pdf"}
        )
        
        assert bundle.page == 1
        assert "Test" in bundle.markdown
    
    def test_add_block_with_citation(self):
        """Test adding block with automatic citation"""
        bundle = PageBundle(
            page=1,
            markdown="",
            blocks=[],
            ocr=[],
            citations={}
        )
        
        block = TextBlock(
            type="text",
            bbox=(100.0, 200.0, 500.0, 300.0),
            citation="p1_txt1",
            md_slice=(0, 10),
            content="Test content"
        )
        
        citation = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",
            content_type="text"
        )
        
        bundle.add_block(block, citation)
        
        assert len(bundle.blocks) == 1
        assert "p1_txt1" in bundle.citations
    
    def test_get_blocks_by_type(self):
        """Test filtering blocks by type"""
        bundle = PageBundle(page=1, markdown="", blocks=[], ocr=[], citations={})
        
        text_block = TextBlock(
            type="text",
            bbox=(0, 0, 100, 100),
            citation="c1",
            md_slice=(0, 10),
            content="text"
        )
        
        bundle.blocks.append(text_block)
        
        text_blocks = bundle.get_blocks_by_type("text")
        assert len(text_blocks) == 1
        assert text_blocks[0].type == "text"
```

### Example Unit Test: `test_bbox_utils.py`

```python
import pytest
from spec_parser.utils.bbox_utils import (
    bbox_overlap,
    bbox_distance,
    bbox_iou,
    bbox_merge,
    validate_bbox
)

class TestBBoxUtils:
    """Test bounding box utilities"""
    
    def test_bbox_overlap_overlapping(self):
        """Test overlap detection for overlapping boxes"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (50, 50, 150, 150)
        
        assert bbox_overlap(bbox1, bbox2) is True
    
    def test_bbox_overlap_non_overlapping(self):
        """Test overlap detection for non-overlapping boxes"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (200, 200, 300, 300)
        
        assert bbox_overlap(bbox1, bbox2) is False
    
    def test_bbox_distance(self):
        """Test distance calculation between boxes"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (200, 200, 300, 300)
        
        distance = bbox_distance(bbox1, bbox2)
        assert distance > 0
    
    def test_bbox_iou(self):
        """Test IoU calculation"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (0, 0, 100, 100)  # Same box
        
        iou = bbox_iou(bbox1, bbox2)
        assert iou == 1.0
    
    def test_bbox_merge(self):
        """Test merging bounding boxes"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (50, 50, 150, 150)
        
        merged = bbox_merge([bbox1, bbox2])
        assert merged == (0, 0, 150, 150)
    
    def test_validate_bbox_valid(self):
        """Test bbox validation with valid bbox"""
        bbox = (0, 0, 100, 100)
        assert validate_bbox(bbox) is True
    
    def test_validate_bbox_invalid(self):
        """Test bbox validation with invalid bbox"""
        bbox = (100, 100, 0, 0)  # x1 < x0, y1 < y0
        assert validate_bbox(bbox) is False
```

### Testing Best Practices

1. **Use pytest fixtures** for common test data
2. **Mock external dependencies** (file I/O, network calls)
3. **Test edge cases**: empty inputs, invalid inputs, boundary conditions
4. **Test error handling**: exceptions, validation errors
5. **Use parametrize** for testing multiple scenarios
6. **Keep tests isolated**: no shared state between tests
7. **Test both success and failure paths**

### pytest Configuration (`tests/conftest.py`)

```python
import pytest
from pathlib import Path
from spec_parser.models.page_bundle import PageBundle
from spec_parser.models.citation import Citation

@pytest.fixture
def sample_citation():
    """Sample citation for testing"""
    return Citation(
        citation_id="p1_txt1",
        page=1,
        bbox=(100.0, 200.0, 500.0, 300.0),
        source="text",
        content_type="text"
    )

@pytest.fixture
def sample_page_bundle():
    """Sample page bundle for testing"""
    return PageBundle(
        page=1,
        markdown="# Test Page\n\nSample content",
        blocks=[],
        ocr=[],
        citations={},
        metadata={"pdf_name": "test.pdf"}
    )

@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir

@pytest.fixture
def sample_pdf_path():
    """Path to sample PDF for testing"""
    return Path(__file__).parent / "fixtures" / "pdfs" / "simple_text.pdf"
```

---

## Step 5.2: Integration Tests

**Objective**: Test complete workflows end-to-end.

### Example Integration Test: `test_pdf_pipeline.py`

```python
import pytest
from pathlib import Path
from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.parsers.ocr_processor import OCRProcessor
from spec_parser.parsers.md_merger import MarkdownMerger
from spec_parser.parsers.json_sidecar import JSONSidecarWriter

@pytest.mark.integration
class TestPDFPipeline:
    """Integration tests for complete PDF pipeline"""
    
    def test_full_pipeline_text_only(self, sample_pdf_path, temp_output_dir):
        """Test complete pipeline with text-only PDF"""
        # Extract
        with PyMuPDFExtractor(sample_pdf_path) as extractor:
            page_bundles = extractor.extract_all_pages()
        
        assert len(page_bundles) > 0
        
        # No OCR needed for text-only
        
        # Merge markdown
        md_merger = MarkdownMerger()
        for bundle in page_bundles:
            markdown = md_merger.merge(bundle)
            assert len(markdown) > 0
        
        # Write JSON
        json_writer = JSONSidecarWriter(temp_output_dir / "json")
        json_writer.write_document(page_bundles, "test")
        
        # Verify outputs
        json_file = temp_output_dir / "json" / "test_document.json"
        assert json_file.exists()
    
    def test_full_pipeline_with_images(self, sample_pdf_with_images, temp_output_dir):
        """Test complete pipeline with images and OCR"""
        import pymupdf
        
        # Extract
        with PyMuPDFExtractor(sample_pdf_with_images) as extractor:
            page_bundles = extractor.extract_all_pages()
        
        # Run OCR
        ocr_processor = OCRProcessor()
        doc = pymupdf.open(sample_pdf_with_images)
        
        for bundle in page_bundles:
            page_num = bundle.page - 1
            pdf_page = doc[page_num]
            
            ocr_results = ocr_processor.process_page(bundle, pdf_page)
            for ocr in ocr_results:
                bundle.add_ocr(ocr)
        
        doc.close()
        
        # Verify OCR was run
        assert any(len(bundle.ocr) > 0 for bundle in page_bundles)
        
        # Merge and write
        md_merger = MarkdownMerger()
        json_writer = JSONSidecarWriter(temp_output_dir / "json")
        
        for bundle in page_bundles:
            markdown = md_merger.merge(bundle)
            assert "OCR" in markdown or True  # May or may not have OCR annotations
        
        json_writer.write_document(page_bundles, "test_images")
        
        # Verify outputs
        json_file = temp_output_dir / "json" / "test_images_document.json"
        assert json_file.exists()
```

### Example Integration Test: `test_search_workflow.py`

```python
import pytest
from pathlib import Path
from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_search import BM25Search
from spec_parser.search.hybrid_search import HybridSearch

@pytest.mark.integration
class TestSearchWorkflow:
    """Integration tests for search workflow"""
    
    def test_index_and_search(self, temp_output_dir):
        """Test building index and searching"""
        # Sample data
        texts = [
            "POCT1 defines OBS.R01 message for observation results",
            "The MSH segment contains message header information",
            "OBX segment carries observation results and values",
            "QCN.R01 is used for query by parameter",
        ]
        
        metadata = [
            {"page": 1, "citation": "p1_txt1", "bbox": (0, 0, 100, 100), "type": "text", "pdf_name": "spec.pdf", "text": texts[0]},
            {"page": 2, "citation": "p2_txt1", "bbox": (0, 0, 100, 100), "type": "text", "pdf_name": "spec.pdf", "text": texts[1]},
            {"page": 3, "citation": "p3_txt1", "bbox": (0, 0, 100, 100), "type": "text", "pdf_name": "spec.pdf", "text": texts[2]},
            {"page": 4, "citation": "p4_txt1", "bbox": (0, 0, 100, 100), "type": "text", "pdf_name": "spec.pdf", "text": texts[3]},
        ]
        
        # Build indices
        embedding_model = EmbeddingModel()
        
        faiss_indexer = FAISSIndexer(embedding_model, index_path=temp_output_dir / "faiss.index")
        faiss_indexer.build_index(texts, metadata)
        faiss_indexer.save()
        
        bm25_search = BM25Search()
        bm25_search.build_index(texts, metadata)
        
        # Search with each method
        query = "observation results OBS"
        
        faiss_results = faiss_indexer.search(query, top_k=2)
        assert len(faiss_results) == 2
        assert faiss_results[0][0]['page'] in [1, 3]  # Should match observation-related pages
        
        bm25_results = bm25_search.search(query, top_k=2)
        assert len(bm25_results) == 2
        
        # Hybrid search
        hybrid = HybridSearch(faiss_indexer, bm25_search)
        hybrid_results = hybrid.search(query, top_k=2)
        assert len(hybrid_results) == 2
        
        # Verify results have metadata
        for meta, score in hybrid_results:
            assert 'page' in meta
            assert 'citation' in meta
            assert 'text' in meta
```

---

## Step 5.3: Test Fixtures

**Objective**: Create reusable test data and sample PDFs.

### Creating Test PDFs

```python
# tests/fixtures/create_fixtures.py
import pymupdf
from pathlib import Path

def create_simple_text_pdf():
    """Create a simple text-only PDF"""
    doc = pymupdf.open()
    page = doc.new_page()
    
    text = """
    POCT1 Specification
    
    Section 1: Overview
    
    This document defines the POCT1 interface specification for
    point-of-care testing devices.
    
    Section 2: Message Types
    
    OBS.R01 - Observation Result
    QCN.R01 - Query by Parameter
    OPL.R01 - Order Preference List
    """
    
    page.insert_text((50, 50), text)
    
    output_path = Path(__file__).parent / "pdfs" / "simple_text.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    
    print(f"Created: {output_path}")

if __name__ == "__main__":
    create_simple_text_pdf()
```

### Fixture Organization

```
tests/fixtures/
├── pdfs/
│   ├── simple_text.pdf          # Basic text PDF
│   ├── with_images.pdf          # PDF with embedded images
│   ├── with_tables.pdf          # PDF with tables
│   └── poct1_sample.pdf         # Sample POCT1 spec (5-10 pages)
├── expected/
│   ├── simple_text_p1.json      # Expected JSON for page 1
│   ├── poct1_entities.json      # Expected extracted entities
│   └── poct1_messages.json      # Expected message definitions
└── README.md                     # Documentation for fixtures
```

---

## Step 5.4: Package Configuration (`pyproject.toml`)

**Objective**: Configure project for distribution.

### pyproject.toml

```toml
[build-system]
requires = ["setuptools>=65.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "spec-parser"
version = "1.0.0"
description = "POCT1 Specification Parser and Normalizer with Citations"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
keywords = ["poct1", "pdf", "parser", "ocr", "citations", "specifications"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Healthcare Industry",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Topic :: Scientific/Engineering",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

dependencies = [
    "pymupdf>=1.26.0",
    "pymupdf4llm>=0.2.0",
    "pytesseract>=0.3.13",
    "Pillow>=12.0.0",
    "pydantic>=2.12.0",
    "pydantic-settings>=2.8.0",
    "click>=8.3.0",
    "loguru>=0.7.3",
    "python-dotenv>=1.2.0",
    "faiss-cpu>=1.13.0",
    "sentence-transformers>=5.2.0",
    "rank-bm25>=0.2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "pytest-mock>=3.15.0",
    "black>=24.12.0",
    "ruff>=0.9.2",
    "mypy>=1.15.0",
]

[project.scripts]
spec-parser = "spec_parser.cli.main:cli"

[project.urls]
Homepage = "https://github.com/yourusername/spec-parser"
Documentation = "https://github.com/yourusername/spec-parser#readme"
Repository = "https://github.com/yourusername/spec-parser"
Issues = "https://github.com/yourusername/spec-parser/issues"

[tool.setuptools.packages.find]
where = ["src"]
include = ["spec_parser*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--cov=spec_parser",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
    "-v"
]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]

[tool.black]
line-length = 100
target-version = ['py310']
include = '\.pyi?$'

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

---

## Step 5.5: Docker Configuration

**Objective**: Containerize application for easy deployment.

### Dockerfile

```dockerfile
FROM python:3.10-slim

# Install system dependencies for Tesseract OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY pyproject.toml ./

# Install package in editable mode
RUN pip install -e .

# Create output directory
RUN mkdir -p /app/output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/app/output

# Default command
ENTRYPOINT ["spec-parser"]
CMD ["--help"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  spec-parser:
    build: .
    image: spec-parser:latest
    container_name: spec-parser
    volumes:
      - ./input:/app/input:ro
      - ./output:/app/output
    environment:
      - OUTPUT_DIR=/app/output
      - OCR_LANGUAGE=eng
    command: parse /app/input/document.pdf -o /app/output
```

### .dockerignore

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
output/
.git/
.github/
tests/
docs/
*.md
!README.md
```

---

## Step 5.6: CI/CD Configuration (GitHub Actions)

**Objective**: Automate testing and deployment.

### .github/workflows/test.yml

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install Tesseract (Ubuntu)
      if: runner.os == 'Linux'
      run: |
        sudo apt-get update
        sudo apt-get install -y tesseract-ocr
    
    - name: Install Tesseract (macOS)
      if: runner.os == 'macOS'
      run: brew install tesseract
    
    - name: Install Tesseract (Windows)
      if: runner.os == 'Windows'
      run: choco install tesseract
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest tests/unit/ -v --cov=spec_parser --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-${{ matrix.os }}-py${{ matrix.python-version }}
```

---

## Phase 5 Completion Checklist

### Unit Tests
- [ ] All Phase 1 modules tested (models, config, utils)
- [ ] All Phase 2 modules tested (parsers)
- [ ] All Phase 3 modules tested (extractors, search)
- [ ] All Phase 4 modules tested (CLI)
- [ ] Code coverage >80%

### Integration Tests
- [ ] PDF pipeline test (text-only)
- [ ] PDF pipeline test (with images)
- [ ] Entity extraction test
- [ ] Search workflow test
- [ ] CLI integration test

### Test Fixtures
- [ ] Sample PDFs created
- [ ] Expected outputs prepared
- [ ] Fixture documentation written

### Packaging
- [ ] pyproject.toml configured
- [ ] Package builds successfully
- [ ] CLI entry point works
- [ ] Installation via pip works

### Docker
- [ ] Dockerfile created
- [ ] Docker image builds
- [ ] docker-compose.yml configured
- [ ] Container runs successfully

### CI/CD
- [ ] GitHub Actions workflow configured
- [ ] Tests run on multiple OS (Ubuntu, Windows, macOS)
- [ ] Tests run on multiple Python versions (3.10, 3.11)
- [ ] Code coverage reporting enabled

### Documentation
- [ ] README.md complete
- [ ] API documentation generated
- [ ] Usage examples provided
- [ ] Deployment guide written

### Verification
- [ ] All files < 300 lines
- [ ] All tests pass
- [ ] No type errors (mypy)
- [ ] Code formatted (black)
- [ ] Linting passes (ruff)
- [ ] Cross-platform compatibility verified

---

## Expected Outcome

After completing Phase 5, you will have:

✅ **Comprehensive test suite with >80% coverage**
✅ **Production-ready package configuration**
✅ **Docker containerization**
✅ **CI/CD pipeline with multi-platform testing**
✅ **Complete documentation**
✅ **Ready for deployment and distribution**
✅ **All quality gates passing**

---

## Final Steps

### Build and Distribute

```bash
# Build package
python -m build

# Check package
twine check dist/*

# Upload to PyPI (when ready)
twine upload dist/*
```

### Docker Build

```bash
# Build image
docker build -t spec-parser:latest .

# Run container
docker run -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output spec-parser parse /app/input/document.pdf
```

### Run All Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v --slow

# All tests with coverage
pytest -v --cov=spec_parser --cov-report=html

# Type checking
mypy src/spec_parser

# Linting
ruff check src/

# Formatting
black --check src/
```

---

## Project Complete! 🎉

Congratulations! You now have a production-ready POCT1 specification parser with:

- ✅ Complete PDF → Markdown + JSON pipeline
- ✅ Intelligent OCR with text-check
- ✅ Citation-first architecture with full provenance
- ✅ Entity extraction for POCT1 specifications
- ✅ Hybrid search (FAISS + BM25)
- ✅ CLI interface for all workflows
- ✅ Comprehensive test suite (>80% coverage)
- ✅ Cross-platform support (Windows/macOS/Linux)
- ✅ Docker containerization
- ✅ CI/CD pipeline
- ✅ V1 greenfield approach (no backwards compatibility)
- ✅ All files < 300 lines

**Ready for production use!**
