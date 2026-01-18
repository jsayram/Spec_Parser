# POCT1 Spec Parser - Implementation Steps

**Project**: Spec Parser and Normalizer V1
**Date**: January 17, 2026
**Environment**: Python 3.10.6 in `.venv/`
**Status**: Environment setup complete ✅

---

## Phase 1: Foundation (Core Infrastructure)

### Step 1.1: Create Project Structure

**Objective**: Establish the complete directory structure for the project with all necessary packages and submodules.

**Tasks**:
1. Create `src/spec_parser/` as the main package directory
2. Create subdirectories:
   - `src/spec_parser/parsers/` - PDF parsing and extraction modules
   - `src/spec_parser/models/` - Pydantic data models and schemas
   - `src/spec_parser/extractors/` - POCT1 entity extraction logic
   - `src/spec_parser/search/` - FAISS and BM25 search implementations
   - `src/spec_parser/embeddings/` - Embedding model management
   - `src/spec_parser/llm/` - LLM integration (future use)
   - `src/spec_parser/utils/` - Utility functions and helpers
3. Create `tests/` directory structure:
   - `tests/fixtures/` - Test data directory for PDFs and expected outputs
   - `tests/unit/` - Unit tests for individual modules
   - `tests/integration/` - End-to-end integration tests
4. Add `__init__.py` files to all packages to make them importable
5. Each `__init__.py` should expose key classes/functions from the module

**Files Created**:
- `src/spec_parser/__init__.py`
- `src/spec_parser/parsers/__init__.py`
- `src/spec_parser/models/__init__.py`
- `src/spec_parser/extractors/__init__.py`
- `src/spec_parser/search/__init__.py`
- `src/spec_parser/embeddings/__init__.py`
- `src/spec_parser/llm/__init__.py`
- `src/spec_parser/utils/__init__.py`
- `tests/__init__.py`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/fixtures/` (directory only, no __init__.py needed)

**Success Criteria**:
- All directories exist
- All `__init__.py` files are present
- Package structure is importable: `from spec_parser.models import ...`

---

### Step 1.2: Core Data Models (Pydantic Schemas)

**Objective**: Define the core data structures for citations, page bundles, blocks, and OCR results using Pydantic for validation and type safety.

#### Step 1.2.1: Citation Model (`models/citation.py`)

**Purpose**: Represent provenance metadata for every extracted element - the foundation of our citation-first architecture.

**Data Structure**:
```python
class Citation(BaseModel):
    citation_id: str  # Format: "p{page}_{type}_{index}", e.g., "p12_img3"
    page: int  # Page number (1-indexed)
    bbox: Tuple[float, float, float, float]  # [x0, y0, x1, y1] coordinates
    source: Literal["text", "ocr", "graphics"]  # Where data came from
    confidence: Optional[float] = None  # OCR confidence score (0.0-1.0)
    content_type: Literal["picture", "table", "text", "graphics"]
    file_reference: Optional[str] = None  # Reference to extracted image file
```

**Key Features**:
- Type validation with Pydantic
- Mandatory fields: citation_id, page, bbox, source, content_type
- Optional confidence score for OCR results
- File reference for linking to extracted images
- Custom validators for bbox format and citation_id format
- Helper methods: `to_markdown_footnote()`, `to_dict()`

**Tests Required**:
- Valid citation creation
- Invalid bbox coordinates rejected
- Citation ID format validation
- Confidence score range validation (0.0-1.0)
- JSON serialization/deserialization

**File Size**: Target <150 lines

---

#### Step 1.2.2: Block Models (`models/page_bundle.py`)

**Purpose**: Define the structure for content blocks extracted from PDF pages - text, images, tables, graphics.

**Data Structures**:

```python
class Block(BaseModel):
    """Base class for all content blocks"""
    type: Literal["text", "picture", "table", "graphics"]
    bbox: Tuple[float, float, float, float]
    citation: str  # Reference to Citation.citation_id
    
class TextBlock(Block):
    type: Literal["text"] = "text"
    md_slice: Tuple[int, int]  # [start, stop] position in markdown text
    content: str  # Actual text content
    
class PictureBlock(Block):
    type: Literal["picture"] = "picture"
    image_ref: str  # Path to extracted image file
    source: Literal["pdf", "screenshot"] = "pdf"
    
class TableBlock(Block):
    type: Literal["table"] = "table"
    table_ref: str  # Table identifier
    markdown_table: Optional[str] = None  # Table as markdown
    
class GraphicsBlock(Block):
    type: Literal["graphics"] = "graphics"
    source: Literal["vector", "mixed"] = "vector"
```

**OCR Result Structure**:
```python
class OCRResult(BaseModel):
    bbox: Tuple[float, float, float, float]
    text: str  # Extracted text from OCR
    confidence: float  # Tesseract confidence (0.0-1.0)
    source: Literal["tesseract", "easyocr"] = "tesseract"
    citation: str  # Reference to Citation.citation_id
    associated_block: Optional[str] = None  # Citation ID of related image/graphics
    language: str = "eng"  # OCR language used
```

**Page Bundle Structure**:
```python
class PageBundle(BaseModel):
    page: int  # Page number (1-indexed)
    markdown: str  # Full markdown text for this page
    blocks: List[Union[TextBlock, PictureBlock, TableBlock, GraphicsBlock]]
    ocr: List[OCRResult]  # All OCR results for this page
    citations: Dict[str, Citation]  # Lookup dict: citation_id -> Citation
    metadata: Dict[str, Any] = {}  # Additional page metadata
    
    def get_citation(self, citation_id: str) -> Optional[Citation]:
        """Retrieve citation by ID"""
        
    def add_block(self, block: Block, citation: Citation) -> None:
        """Add a block and its citation"""
        
    def add_ocr_result(self, ocr: OCRResult, citation: Citation) -> None:
        """Add an OCR result and its citation"""
```

**Key Features**:
- Union types for different block types
- Nested Pydantic models with full validation
- Helper methods for citation management
- JSON serialization with proper typing
- Validation for bbox coordinates
- Automatic citation linking

**Tests Required**:
- Create PageBundle with mixed block types
- Add blocks and verify citation linking
- Serialize/deserialize to JSON
- Validate bbox coordinates
- Test OCR confidence ranges
- Test citation lookup methods

**File Size**: Target <300 lines (if larger, split into separate files for each block type)

---

### Step 1.3: Configuration & Core Utilities

#### Step 1.3.1: Configuration Management (`config.py`)

**Objective**: Centralized configuration using environment variables with type-safe defaults.

**Implementation**:
```python
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Literal

class Settings(BaseSettings):
    # OCR Configuration
    ocr_engine: Literal["tesseract", "easyocr"] = "tesseract"
    ocr_language: str = "eng"
    ocr_dpi: int = 300
    ocr_confidence_threshold: float = 0.7
    
    # Embedding Model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: Literal["cpu", "cuda"] = "cpu"
    
    # Search Configuration
    faiss_index_type: str = "Flat"
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    
    # Output Paths (use Path objects for cross-platform)
    output_dir: Path = Path("./output")
    image_dir: Path = Path("./output/images")
    json_dir: Path = Path("./output/json")
    markdown_dir: Path = Path("./output/markdown")
    
    # LLM Configuration (future)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4"
    llm_api_key: str = ""
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "text"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def ensure_directories(self) -> None:
        """Create output directories if they don't exist"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
```

**Key Features**:
- Environment variable loading with `.env` support
- Type validation on all settings
- Cross-platform path handling with `pathlib.Path`
- Automatic directory creation
- Default values for all settings
- Case-insensitive environment variable names

**Tests Required**:
- Load settings from environment
- Override defaults with .env file
- Path creation and validation
- Invalid value rejection (e.g., negative DPI)

**File Size**: Target <150 lines

---

#### Step 1.3.2: Custom Exceptions (`exceptions.py`)

**Objective**: Define domain-specific exceptions for better error handling throughout the application.

**Implementation**:
```python
class SpecParserError(Exception):
    """Base exception for all spec parser errors"""
    pass

class PDFExtractionError(SpecParserError):
    """Error during PDF text/image extraction"""
    pass

class OCRError(SpecParserError):
    """Error during OCR processing"""
    pass

class CitationError(SpecParserError):
    """Error related to citation generation or validation"""
    pass

class ValidationError(SpecParserError):
    """Error validating data models or schemas"""
    pass

class SearchIndexError(SpecParserError):
    """Error building or querying search index"""
    pass

class ConfigurationError(SpecParserError):
    """Error in configuration or settings"""
    pass
```

**Key Features**:
- Hierarchical exception structure
- Clear error types for different failure modes
- Inherits from base `SpecParserError` for catch-all handling
- Descriptive names for debugging

**Tests Required**:
- Raise and catch each exception type
- Verify inheritance chain
- Test error messages

**File Size**: Target <100 lines

---

#### Step 1.3.3: Logging Setup (`utils/logger.py`)

**Objective**: Configure loguru for structured logging with appropriate formatting and levels.

**Implementation**:
```python
from loguru import logger
from pathlib import Path
from spec_parser.config import settings
import sys

def setup_logger() -> None:
    """Configure loguru logger based on settings"""
    # Remove default handler
    logger.remove()
    
    # Console handler with color
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True
    )
    
    # File handler with rotation
    log_file = Path("logs") / "spec_parser.log"
    log_file.parent.mkdir(exist_ok=True)
    
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
        rotation="10 MB",
        retention="1 week",
        compression="zip"
    )
    
    logger.info(f"Logger initialized at level {settings.log_level}")

# Initialize on import
setup_logger()
```

**Key Features**:
- Colored console output for readability
- File logging with rotation and compression
- Structured format with module/function/line info
- Configurable log level from settings
- Automatic log directory creation

**Tests Required**:
- Logger initialization
- Log messages at different levels
- File creation and rotation

**File Size**: Target <100 lines

---

#### Step 1.3.4: Bounding Box Utilities (`utils/bbox_utils.py`)

**Objective**: Utility functions for working with bounding boxes - distance calculation, overlap detection, merging.

**Implementation**:
```python
from typing import Tuple

BBox = Tuple[float, float, float, float]  # [x0, y0, x1, y1]

def bbox_distance(bbox1: BBox, bbox2: BBox) -> float:
    """
    Calculate Manhattan distance between bbox centers.
    Used for finding nearest captions to images.
    """
    x1_center = (bbox1[0] + bbox1[2]) / 2
    y1_center = (bbox1[1] + bbox1[3]) / 2
    x2_center = (bbox2[0] + bbox2[2]) / 2
    y2_center = (bbox2[1] + bbox2[3]) / 2
    
    return abs(x1_center - x2_center) + abs(y1_center - y2_center)

def bbox_overlap(bbox1: BBox, bbox2: BBox) -> bool:
    """
    Check if two bboxes overlap.
    Used for text-check before OCR.
    """
    # Check if one bbox is to the left of the other
    if bbox1[2] < bbox2[0] or bbox2[2] < bbox1[0]:
        return False
    # Check if one bbox is above the other
    if bbox1[3] < bbox2[1] or bbox2[3] < bbox1[1]:
        return False
    return True

def bbox_area(bbox: BBox) -> float:
    """Calculate area of a bounding box"""
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width * height

def bbox_intersection_area(bbox1: BBox, bbox2: BBox) -> float:
    """Calculate intersection area between two bboxes"""
    if not bbox_overlap(bbox1, bbox2):
        return 0.0
    
    x_left = max(bbox1[0], bbox2[0])
    y_top = max(bbox1[1], bbox2[1])
    x_right = min(bbox1[2], bbox2[2])
    y_bottom = min(bbox1[3], bbox2[3])
    
    return (x_right - x_left) * (y_bottom - y_top)

def bbox_iou(bbox1: BBox, bbox2: BBox) -> float:
    """
    Calculate Intersection over Union (IoU) for two bboxes.
    Returns value between 0.0 (no overlap) and 1.0 (complete overlap).
    """
    intersection = bbox_intersection_area(bbox1, bbox2)
    if intersection == 0.0:
        return 0.0
    
    area1 = bbox_area(bbox1)
    area2 = bbox_area(bbox2)
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0.0

def bbox_contains_point(bbox: BBox, x: float, y: float) -> bool:
    """Check if a point is inside a bounding box"""
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]

def bbox_merge(bboxes: list[BBox]) -> BBox:
    """Merge multiple bboxes into a single bounding box"""
    if not bboxes:
        raise ValueError("Cannot merge empty bbox list")
    
    x0 = min(b[0] for b in bboxes)
    y0 = min(b[1] for b in bboxes)
    x1 = max(b[2] for b in bboxes)
    y1 = max(b[3] for b in bboxes)
    
    return (x0, y0, x1, y1)

def validate_bbox(bbox: BBox) -> bool:
    """Validate that bbox coordinates are valid"""
    x0, y0, x1, y1 = bbox
    return x0 < x1 and y0 < y1 and all(isinstance(v, (int, float)) for v in bbox)
```

**Key Features**:
- Manhattan distance for caption proximity
- Overlap detection for text-check
- IoU calculation for bbox matching
- Merge utility for combining regions
- Validation for bbox coordinates
- Type hints for clarity

**Tests Required**:
- Distance calculation with known values
- Overlap detection (overlapping and non-overlapping cases)
- IoU calculation
- Bbox merging
- Edge cases: zero-area boxes, negative coordinates

**File Size**: Target <200 lines

---

#### Step 1.3.5: File Handler (`utils/file_handler.py`)

**Objective**: Cross-platform file operations using `pathlib` for reading, writing, and managing PDF/image files.

**Implementation**:
```python
from pathlib import Path
from typing import Union, Optional
from loguru import logger
import json
import shutil

def ensure_directory(path: Union[str, Path]) -> Path:
    """Create directory if it doesn't exist (cross-platform)"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {path}")
    return path

def read_json(file_path: Union[str, Path]) -> dict:
    """Read JSON file with error handling"""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    
    with file_path.open('r', encoding='utf-8') as f:
        return json.load(f)

def write_json(data: dict, file_path: Union[str, Path], indent: int = 2) -> None:
    """Write JSON file with proper formatting"""
    file_path = Path(file_path)
    ensure_directory(file_path.parent)
    
    with file_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    
    logger.debug(f"Wrote JSON to {file_path}")

def read_text(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """Read text file"""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Text file not found: {file_path}")
    
    return file_path.read_text(encoding=encoding)

def write_text(content: str, file_path: Union[str, Path], encoding: str = 'utf-8') -> None:
    """Write text file"""
    file_path = Path(file_path)
    ensure_directory(file_path.parent)
    file_path.write_text(content, encoding=encoding)
    logger.debug(f"Wrote text to {file_path}")

def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
    """Copy file with error handling"""
    src = Path(src)
    dst = Path(dst)
    
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")
    
    ensure_directory(dst.parent)
    shutil.copy2(src, dst)
    logger.debug(f"Copied {src} to {dst}")

def get_output_path(
    base_name: str,
    output_dir: Path,
    extension: str,
    page: Optional[int] = None
) -> Path:
    """
    Generate output file path with consistent naming.
    e.g., "spec.pdf" page 12 -> "output/images/spec_p12_img1.png"
    """
    if page is not None:
        stem = f"{Path(base_name).stem}_p{page}"
    else:
        stem = Path(base_name).stem
    
    return output_dir / f"{stem}.{extension.lstrip('.')}"
```

**Key Features**:
- Cross-platform path handling with `pathlib`
- Automatic directory creation
- Error handling with descriptive messages
- Consistent naming conventions
- UTF-8 encoding by default
- Logging for debugging

**Tests Required**:
- Directory creation
- JSON read/write
- Text read/write
- File copying
- Output path generation with/without page numbers
- Cross-platform path handling

**File Size**: Target <200 lines

---

#### Step 1.3.6: Environment Configuration Template (`.env.example`)

**Objective**: Provide a template for users to configure their environment.

**Content**:
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

# Output Paths (relative to project root)
OUTPUT_DIR=./output
IMAGE_DIR=./output/images
JSON_DIR=./output/json
MARKDOWN_DIR=./output/markdown

# LLM Configuration (future use)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=text
```

**Key Features**:
- All configuration options documented
- Sensible defaults provided
- Comments explaining each section
- Ready to copy to `.env` for customization

**File Size**: Small config file

---

### Step 1.4: Initial Testing Infrastructure

**Objective**: Set up pytest configuration and basic test structure before writing tests.

#### Step 1.4.1: Pytest Configuration (`tests/conftest.py`)

**Implementation**:
```python
import pytest
from pathlib import Path
from spec_parser.config import Settings

@pytest.fixture
def temp_output_dir(tmp_path):
    """Provide a temporary output directory for tests"""
    return tmp_path / "output"

@pytest.fixture
def test_settings(temp_output_dir):
    """Provide test-specific settings"""
    return Settings(
        output_dir=temp_output_dir,
        image_dir=temp_output_dir / "images",
        json_dir=temp_output_dir / "json",
        markdown_dir=temp_output_dir / "markdown",
        log_level="DEBUG"
    )

@pytest.fixture
def sample_bbox():
    """Provide a sample bounding box for testing"""
    return (100.0, 200.0, 300.0, 400.0)

@pytest.fixture
def sample_citation():
    """Provide a sample citation for testing"""
    from spec_parser.models.citation import Citation
    return Citation(
        citation_id="p1_text_1",
        page=1,
        bbox=(100.0, 200.0, 300.0, 400.0),
        source="text",
        content_type="text"
    )
```

**Key Features**:
- Temporary directories for test isolation
- Test-specific settings to avoid modifying real data
- Reusable fixtures for common test data
- Clear fixture naming

**File Size**: Target <200 lines (will grow as we add more fixtures)

---

## Phase 1 Summary

**Completion Checklist**:
- [ ] Directory structure created
- [ ] All `__init__.py` files added
- [ ] Citation model implemented (`models/citation.py`)
- [ ] Page bundle models implemented (`models/page_bundle.py`)
- [ ] Configuration management implemented (`config.py`)
- [ ] Custom exceptions defined (`exceptions.py`)
- [ ] Logger configured (`utils/logger.py`)
- [ ] Bbox utilities implemented (`utils/bbox_utils.py`)
- [ ] File handler utilities implemented (`utils/file_handler.py`)
- [ ] `.env.example` created
- [ ] Pytest configuration setup (`tests/conftest.py`)
- [ ] Basic unit tests written for models and utilities

**Expected Outcome**:
- Solid foundation with type-safe models
- Reusable utilities for file and bbox operations
- Configurable environment
- Test infrastructure ready
- All files <300 lines
- Ready to build parsing pipeline in Phase 2

---

## Phase 2: PDF Parsing Pipeline (Core Extraction)

### Step 2.1: PyMuPDF Extractor (`parsers/pymupdf_extractor.py`)

**Objective**: Extract structured content from PDF using PyMuPDF4LLM's page-chunks mode, including text, images, tables, and graphics with bounding boxes.

**Key Functionality**:

```python
class PyMuPDFExtractor:
    def __init__(self, pdf_path: Path):
        """Initialize extractor with PDF path"""
        
    def extract_page(self, page_num: int) -> PageBundle:
        """
        Extract content from a single page.
        
        Returns PageBundle with:
        - markdown text
        - text blocks with bboxes
        - image blocks with bboxes and file references
        - table blocks with bboxes
        - graphics blocks with bboxes
        - citations for all elements
        """
        
    def extract_all_pages(self) -> List[PageBundle]:
        """Extract content from all pages"""
        
    def _extract_text_blocks(self, page) -> List[TextBlock]:
        """Extract text blocks with position data"""
        
    def _extract_images(self, page, output_dir: Path) -> List[PictureBlock]:
        """
        Extract images from page.
        Save images to output_dir with naming: {pdf_name}_p{page}_img{index}.png
        """
        
    def _extract_tables(self, page) -> List[TableBlock]:
        """Extract tables with bboxes"""
        
    def _extract_graphics(self, page) -> List[GraphicsBlock]:
        """
        Extract graphics cluster bboxes.
        These are vector graphics that may need OCR.
        """
        
    def _generate_citation(self, page: int, block_type: str, index: int, bbox: BBox) -> Citation:
        """Generate citation for extracted element"""
```

**Implementation Details**:
- Use `pymupdf4llm.to_markdown()` with `page_chunks=True`
- Enable `extract_words=True` for text-check capability
- Enable `write_images=True` to save extracted images
- Parse `page_boxes` for layout information with bboxes
- Store raw extraction data along with processed bundles
- Generate unique citation IDs for every element
- Preserve all positional metadata

**Error Handling**:
- Handle corrupted PDFs gracefully
- Handle encrypted/password-protected PDFs
- Handle PDFs with no extractable content
- Log warnings for skipped pages

**Tests Required**:
- Extract from text-only PDF
- Extract from image-heavy PDF
- Extract from PDF with tables
- Extract from PDF with vector graphics
- Validate citation generation
- Validate bbox coordinates
- Test multi-page extraction
- Test image file naming consistency

**File Size**: Target <300 lines (if larger, split into `_text_extractor.py`, `_image_extractor.py`, etc.)

---

### Step 2.2: OCR Processor (`parsers/ocr_processor.py`)

**Objective**: Perform intelligent OCR on image and graphics regions, with text-check to avoid duplication.

**Key Functionality**:

```python
class OCRProcessor:
    def __init__(self, dpi: int = 300, confidence_threshold: float = 0.7):
        """Initialize OCR processor with settings"""
        
    def process_page(self, page_bundle: PageBundle, pdf_page) -> List[OCRResult]:
        """
        Process all OCR candidates on a page.
        
        Steps:
        1. Identify OCR candidates (pictures + graphics without selectable text)
        2. For each candidate, check if region has text
        3. If no text, render region to bitmap and run OCR
        4. Return OCR results with confidence scores
        """
        
    def _has_selectable_text(self, pdf_page, bbox: BBox) -> bool:
        """
        Check if bbox region contains extractable text.
        Use get_text("words") and check for word overlap with bbox.
        """
        
    def _render_region(self, pdf_page, bbox: BBox) -> Image:
        """
        Render bbox region to high-DPI bitmap.
        Use DPI setting for quality.
        """
        
    def _run_ocr(self, image: Image) -> Tuple[str, float]:
        """
        Run Tesseract OCR on image.
        Returns (text, confidence_score)
        """
        
    def _find_nearest_caption(self, bbox: BBox, text_blocks: List[TextBlock]) -> Optional[TextBlock]:
        """
        Find nearest caption using bbox_distance.
        Look for patterns: "Figure", "Fig.", "Table", etc.
        """
```

**Implementation Details**:
- Use pytesseract for OCR
- High-DPI rendering (300+ DPI) for accuracy
- Text-check before OCR to avoid duplication
- Handle both picture blocks and graphics blocks
- Calculate distance to find nearest captions
- Track OCR confidence per region
- Skip OCR if confidence threshold not met
- Generate citations for OCR results

**Pattern Matching for Captions**:
- Regex patterns for "Figure X", "Fig. X", "Table X"
- Proximity threshold (e.g., within 100 units)
- Prefer text blocks above or below image

**Error Handling**:
- Handle OCR failures gracefully
- Handle unreadable images
- Handle non-English text
- Log warnings for low-confidence results

**Tests Required**:
- Text-check detects selectable text
- Text-check skips OCR when text present
- OCR runs on image regions without text
- Graphics blocks processed as OCR candidates
- Caption proximity detection works
- Confidence threshold filtering
- High-DPI rendering produces readable results

**File Size**: Target <300 lines

---

### Step 2.3: Markdown Merger (`parsers/md_merger.py`)

**Objective**: Merge PyMuPDF markdown with OCR results, adding inline annotations and citation footnotes.

**Key Functionality**:

```python
class MarkdownMerger:
    def __init__(self):
        """Initialize markdown merger"""
        
    def merge(self, page_bundle: PageBundle) -> str:
        """
        Create enhanced markdown with OCR and citations.
        
        Steps:
        1. Parse markdown to find image/table insertion points
        2. For each image, insert inline OCR annotation if available
        3. Add citation anchors for text blocks
        4. Build citation index at end
        """
        
    def _insert_ocr_annotations(self, markdown: str, page_bundle: PageBundle) -> str:
        """
        Insert OCR results near image references.
        
        Format:
        ![Figure 3](images/page12_img3.png) [^p12_img3]
        
        > OCR (from figure): The device sends OPL.R01...
        > Confidence: 0.87
        """
        
    def _add_citation_anchors(self, markdown: str, page_bundle: PageBundle) -> str:
        """
        Add citation reference marks throughout text.
        e.g., "Section Title [^p12_text_1]"
        """
        
    def _build_citation_index(self, page_bundle: PageBundle) -> str:
        """
        Build citation footnotes at end of document.
        
        Format:
        [^p12_text_1]: Page 12, bbox [50, 100, 550, 120], source: text
        [^p12_img3]: Page 12, bbox [100, 200, 500, 400], source: ocr, file: page12_img3.png
        """
```

**Implementation Details**:
- Parse markdown to identify structure
- Use regex to find image references
- Calculate insertion points for OCR annotations
- Format citations as markdown footnotes
- Preserve original markdown structure
- Human-readable output
- Link citations to original positions

**Citation Format**:
```markdown
[^citation_id]: Page {page}, bbox [{x0}, {y0}, {x1}, {y1}], source: {source}[, file: {file_ref}][, confidence: {conf}]
```

**Tests Required**:
- Insert OCR annotations near images
- Add citation anchors to text
- Build complete citation index
- Preserve markdown structure
- Handle pages without images
- Handle pages without OCR results

**File Size**: Target <250 lines

---

### Step 2.4: JSON Sidecar Writer (`parsers/json_sidecar.py`)

**Objective**: Write structured JSON output with complete provenance for machine processing.

**Key Functionality**:

```python
class JSONSidecarWriter:
    def __init__(self, output_dir: Path):
        """Initialize writer with output directory"""
        
    def write_page_bundle(self, page_bundle: PageBundle, pdf_name: str) -> Path:
        """
        Write single page bundle to JSON.
        Filename: {pdf_name}_p{page}.json
        """
        
    def write_document(self, page_bundles: List[PageBundle], pdf_name: str) -> Path:
        """
        Write all page bundles to single JSON file.
        Filename: {pdf_name}_document.json
        """
        
    def _serialize_bundle(self, page_bundle: PageBundle) -> dict:
        """Convert PageBundle to JSON-serializable dict"""
```

**JSON Structure**:
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

**Implementation Details**:
- Use Pydantic's `.model_dump()` for serialization
- Pretty-print JSON with indentation
- Include metadata timestamps
- One file per page + one file for full document
- Easy to diff and version control

**Tests Required**:
- Write single page bundle
- Write multi-page document
- Validate JSON structure
- Round-trip: write then read back
- Verify all citations present

**File Size**: Target <150 lines

---

## Phase 2 Summary

**Completion Checklist**:
- [ ] PyMuPDF extractor implemented
- [ ] OCR processor with text-check implemented
- [ ] Markdown merger with citations implemented
- [ ] JSON sidecar writer implemented
- [ ] Unit tests for each module
- [ ] Integration test: PDF → PageBundle → OCR → Markdown + JSON
- [ ] Test with sample POCT1 PDF

**Expected Outcome**:
- Complete PDF → structured output pipeline
- Dual output: human-readable MD + machine-readable JSON
- Every element has citation with provenance
- OCR only runs where needed
- All files <300 lines

---

## Phase 3: Entity Extraction & Search

### Step 3.1: POCT1 Spec Graph Extractor (`extractors/spec_graph.py`)

**Objective**: Extract POCT1-specific entities (messages, fields, rules) from parsed page bundles with citations.

**Key Functionality**:

```python
class SpecGraphExtractor:
    def __init__(self):
        """Initialize extractor with POCT1 patterns"""
        
    def extract_entities(self, page_bundles: List[PageBundle]) -> Dict[str, Any]:
        """
        Extract all POCT1 entities from page bundles.
        
        Returns:
        {
          "messages": [...],
          "fields": [...],
          "rules": [...],
          "xml_schemas": [...],
          "vendor_extensions": [...]
        }
        """
        
    def _extract_messages(self, page_bundles) -> List[MessageDefinition]:
        """
        Extract message definitions.
        Pattern: OBS.R01, OPL.R01, QCN.R01, etc.
        """
        
    def _extract_field_tables(self, page_bundles) -> List[FieldTable]:
        """
        Extract field tables with name, type, optionality, cardinality.
        Look for table structures in blocks.
        """
        
    def _extract_xml_snippets(self, page_bundles) -> List[XMLSnippet]:
        """Extract XML schemas and examples"""
        
    def _extract_cardinality_rules(self, page_bundles) -> List[Rule]:
        """Extract rules for required/optional/repeating fields"""
        
    def _extract_vendor_extensions(self, page_bundles) -> List[Extension]:
        """Extract vendor-specific namespace extensions"""
```

**Entity Models**:
```python
class MessageDefinition(BaseModel):
    message_id: str  # e.g., "OBS.R01"
    description: str
    fields: List[str]  # Field names
    citation: str
    page: int
    bbox: BBox
    
class FieldTable(BaseModel):
    name: str
    field_type: str
    required: bool
    cardinality: str  # "1", "0..1", "1..*", etc.
    citation: str
    page: int
    bbox: BBox
```

**Pattern Matching**:
- Regex for message IDs: `r"[A-Z]{3}\.[A-Z]\d{2}"`
- Table detection from markdown tables
- XML detection: `<...>` tags
- Cardinality patterns: "required", "optional", "repeating"

**Tests Required**:
- Extract message definitions
- Extract field tables
- Extract XML snippets
- Verify citations attached to all entities
- Handle malformed or incomplete specs

**File Size**: Target <300 lines (if larger, split by entity type)

---

### Step 3.2: Embedding Model Manager (`embeddings/model_manager.py`)

**Objective**: Manage sentence-transformers embedding model for semantic search.

**Key Functionality**:

```python
class EmbeddingModelManager:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        """Initialize embedding model"""
        
    def load_model(self) -> SentenceTransformer:
        """Load model (downloads if needed, caches locally)"""
        
    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for batch of texts"""
        
    def get_embedding_dim(self) -> int:
        """Return embedding dimension (384 for MiniLM-L6)"""
```

**Implementation Details**:
- Use sentence-transformers library
- CPU-only for cross-platform compatibility
- Model caching in `.cache/` directory
- Batch processing for efficiency
- Progress logging for large batches

**Tests Required**:
- Model loading
- Single text embedding
- Batch embedding
- Verify embedding dimensions
- Test with different model names

**File Size**: Target <150 lines

---

### Step 3.3: FAISS Indexer (`search/faiss_indexer.py`)

**Objective**: Build FAISS index for semantic vector search over page bundles.

**Key Functionality**:

```python
class FAISSIndexer:
    def __init__(self, embedding_manager: EmbeddingModelManager):
        """Initialize indexer with embedding model"""
        
    def build_index(self, page_bundles: List[PageBundle]) -> faiss.Index:
        """
        Build FAISS index from page bundles.
        
        Index each text block with its citation metadata.
        """
        
    def add_to_index(self, index: faiss.Index, texts: List[str], metadata: List[dict]) -> None:
        """Add texts with metadata to existing index"""
        
    def search(self, index: faiss.Index, query: str, k: int = 10) -> List[SearchResult]:
        """
        Search index for query.
        
        Returns:
        [
          {
            "text": "...",
            "score": 0.87,
            "citation": "p12_text_5",
            "page": 12,
            "bbox": [...]
          }
        ]
        """
        
    def save_index(self, index: faiss.Index, metadata: List[dict], path: Path) -> None:
        """Save index and metadata to disk"""
        
    def load_index(self, path: Path) -> Tuple[faiss.Index, List[dict]]:
        """Load index and metadata from disk"""
```

**Implementation Details**:
- Use FAISS Flat index for simplicity (exact search)
- Store citation metadata alongside index
- Save/load index for reuse
- Return results with full provenance

**Tests Required**:
- Build index from page bundles
- Search returns relevant results
- Save and load index
- Verify citation metadata preserved

**File Size**: Target <250 lines

---

### Step 3.4: BM25 Search (`search/bm25_search.py`)

**Objective**: Implement BM25 keyword search for exact term matching.

**Key Functionality**:

```python
class BM25Search:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 with parameters"""
        
    def build_index(self, page_bundles: List[PageBundle]) -> BM25Okapi:
        """Build BM25 index from page bundles"""
        
    def search(self, index: BM25Okapi, query: str, k: int = 10) -> List[SearchResult]:
        """Search for query using BM25"""
        
    def hybrid_search(
        self,
        bm25_index: BM25Okapi,
        faiss_index: faiss.Index,
        query: str,
        k: int = 10,
        alpha: float = 0.5
    ) -> List[SearchResult]:
        """
        Combine BM25 + FAISS results.
        alpha: weight for FAISS (1-alpha for BM25)
        """
```

**Implementation Details**:
- Use rank-bm25 library
- Tokenize text for indexing
- Combine with FAISS for hybrid search
- Return results with citations

**Tests Required**:
- Build BM25 index
- Search returns relevant results
- Hybrid search combines both methods
- Verify citation metadata preserved

**File Size**: Target <200 lines

---

## Phase 3 Summary

**Completion Checklist**:
- [ ] POCT1 entity extractor implemented
- [ ] Embedding model manager implemented
- [ ] FAISS indexer implemented
- [ ] BM25 search implemented
- [ ] Hybrid search implemented
- [ ] Unit tests for all modules
- [ ] Integration test: extract entities from sample spec
- [ ] Integration test: search for POCT1 messages

**Expected Outcome**:
- POCT1-specific entity extraction with citations
- Semantic + keyword search with provenance
- Reusable search infrastructure
- All files <300 lines

---

## Phase 4: CLI & LLM Integration

### Step 4.1: CLI Interface (`__main__.py`)

**Objective**: Provide command-line interface using Click for all pipeline operations.

**Commands**:

```bash
# Parse PDF to markdown + JSON
python -m spec_parser parse input.pdf --output ./output

# Extract POCT1 entities
python -m spec_parser extract ./output/json --output entities.json

# Build search index
python -m spec_parser index ./output/json --index-dir ./index

# Search
python -m spec_parser search "OBS.R01 message format" --index-dir ./index

# Full pipeline
python -m spec_parser pipeline input.pdf --output ./output --index
```

**Implementation**:
```python
import click
from loguru import logger

@click.group()
def cli():
    """POCT1 Spec Parser and Normalizer"""
    pass

@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', default='./output', help='Output directory')
def parse(pdf_path, output):
    """Parse PDF to markdown + JSON with citations"""
    # Implementation
    
@cli.command()
@click.argument('json_dir', type=click.Path(exists=True))
@click.option('--output', '-o', required=True, help='Output file')
def extract(json_dir, output):
    """Extract POCT1 entities from JSON bundles"""
    # Implementation
    
@cli.command()
@click.argument('json_dir', type=click.Path(exists=True))
@click.option('--index-dir', required=True, help='Index directory')
def index(json_dir, index_dir):
    """Build search index from JSON bundles"""
    # Implementation
    
@cli.command()
@click.argument('query')
@click.option('--index-dir', required=True, help='Index directory')
@click.option('--top-k', default=10, help='Number of results')
def search(query, index_dir, top_k):
    """Search indexed documents"""
    # Implementation
    
if __name__ == '__main__':
    cli()
```

**Tests Required**:
- Test each CLI command
- Test with valid/invalid arguments
- Test output file creation

**File Size**: Target <300 lines (if larger, split commands into separate modules)

---

### Step 4.2: LLM Integration Placeholders (`llm/`)

**Objective**: Create interfaces for future LLM integration.

**Files**:

#### `llm/prompt_builder.py`
```python
class PromptBuilder:
    def build_context(self, search_results: List[SearchResult]) -> str:
        """
        Assemble context from search results with citations.
        
        Format:
        Based on the following excerpts from the specification:
        
        [1] Page 12: "The device sends OPL.R01..." [Citation: p12_text_5]
        [2] Page 15: "Field Patient ID is required..." [Citation: p15_text_8]
        """
        
    def build_prompt(self, query: str, context: str) -> str:
        """Build LLM prompt with context"""
```

#### `llm/llm_interface.py`
```python
from abc import ABC, abstractmethod

class LLMInterface(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate response from LLM"""
        pass
    
class OpenAIClient(LLMInterface):
    """Future OpenAI implementation"""
    pass
    
class AnthropicClient(LLMInterface):
    """Future Anthropic implementation"""
    pass
```

**Tests Required**:
- Test prompt building
- Test context assembly with citations
- Mock LLM calls for interface testing

**File Size**: Target <150 lines each

---

## Phase 4 Summary

**Completion Checklist**:
- [ ] CLI interface implemented
- [ ] All CLI commands tested
- [ ] LLM prompt builder implemented
- [ ] LLM interface defined
- [ ] Documentation for CLI usage

**Expected Outcome**:
- Fully functional CLI
- Ready for LLM integration
- User-friendly interface

---

## Phase 5: Testing & Packaging

### Step 5.1: Comprehensive Unit Tests

**Test Files to Create**:

1. `tests/unit/test_models.py` - Test Citation and PageBundle models
2. `tests/unit/test_bbox_utils.py` - Test bbox calculations
3. `tests/unit/test_file_handler.py` - Test file operations
4. `tests/unit/test_pymupdf_extractor.py` - Test PDF extraction
5. `tests/unit/test_ocr_processor.py` - Test OCR logic
6. `tests/unit/test_md_merger.py` - Test markdown merging
7. `tests/unit/test_json_sidecar.py` - Test JSON writing
8. `tests/unit/test_spec_graph.py` - Test entity extraction
9. `tests/unit/test_search.py` - Test FAISS and BM25

**Coverage Goal**: >80%

---

### Step 5.2: Integration Tests

**Test Files**:

1. `tests/integration/test_pipeline.py` - End-to-end pipeline
2. `tests/integration/test_citation_completeness.py` - Verify all elements have citations
3. `tests/integration/test_search_pipeline.py` - Extract → index → search

**Sample Test**:
```python
def test_full_pipeline(sample_pdf):
    # Extract
    extractor = PyMuPDFExtractor(sample_pdf)
    bundles = extractor.extract_all_pages()
    
    # OCR
    ocr = OCRProcessor()
    for bundle in bundles:
        ocr.process_page(bundle, ...)
    
    # Merge
    merger = MarkdownMerger()
    md = merger.merge(bundles[0])
    
    # Verify citations
    assert all(block.citation for block in bundles[0].blocks)
```

---

### Step 5.3: Test Fixtures

**Create Minimal Test PDFs**:
1. `tests/fixtures/text_only.pdf` - Simple text document
2. `tests/fixtures/with_images.pdf` - Document with embedded images
3. `tests/fixtures/with_tables.pdf` - Document with tables
4. `tests/fixtures/graphics_heavy.pdf` - Vector graphics

**Use Real Specs** (if available):
- Add sample POCT1 specification pages

---

### Step 5.4: Packaging (`pyproject.toml`)

**Content**:
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "spec-parser"
version = "1.0.0"
description = "POCT1 Specification Parser and Normalizer with citation tracking"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
dependencies = [
    "pymupdf4llm>=0.0.1",
    "pymupdf>=1.23.0",
    "pytesseract>=0.3.10",
    "Pillow>=10.0.0",
    "pydantic>=2.0.0",
    "click>=8.1.0",
    "faiss-cpu>=1.7.4",
    "rank-bm25>=0.2.2",
    "sentence-transformers>=2.2.0",
    "python-dotenv>=1.0.0",
    "loguru>=0.7.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.0",
    "black>=23.7.0",
    "ruff>=0.0.285",
    "mypy>=1.5.0"
]

[project.scripts]
spec-parser = "spec_parser.__main__:cli"

[tool.black]
line-length = 100
target-version = ['py310']

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--cov=src/spec_parser --cov-report=html --cov-report=term"
```

---

### Step 5.5: Docker Support (`Dockerfile`)

**Content**:
```dockerfile
FROM python:3.11-slim

# Install Tesseract
RUN apt-get update && \
    apt-get install -y tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY pyproject.toml .

# Install package
RUN pip install -e .

# Set Python path
ENV PYTHONPATH=/app

# Create output directory
RUN mkdir -p /app/output

# Entry point
ENTRYPOINT ["spec-parser"]
CMD ["--help"]
```

**Docker Compose** (`docker-compose.yml`):
```yaml
version: '3.8'

services:
  spec-parser:
    build: .
    volumes:
      - ./specs:/app/specs
      - ./output:/app/output
    environment:
      - LOG_LEVEL=INFO
```

---

## Phase 5 Summary

**Completion Checklist**:
- [ ] All unit tests written
- [ ] All integration tests written
- [ ] Test fixtures created
- [ ] Test coverage >80%
- [ ] pyproject.toml configured
- [ ] Dockerfile created
- [ ] Docker compose configured
- [ ] All tests passing

**Expected Outcome**:
- Comprehensive test coverage
- Production-ready packaging
- Docker support for easy deployment
- Ready for distribution

---

## Final Checklist

**Code Quality**:
- [ ] All Python files <300 lines
- [ ] Type hints on all functions
- [ ] Docstrings on all public methods
- [ ] Error handling throughout
- [ ] Logging at appropriate levels

**Citations & Provenance**:
- [ ] Every extracted element has citation
- [ ] Every citation has page + bbox + source
- [ ] Citations preserved through pipeline
- [ ] Human-readable MD output with citations
- [ ] Machine-readable JSON with complete metadata

**Testing**:
- [ ] >80% code coverage
- [ ] All edge cases tested
- [ ] Citation completeness validated
- [ ] Cross-platform compatibility verified

**Documentation**:
- [ ] README updated with usage instructions
- [ ] CLI help text complete
- [ ] .env.example provided
- [ ] Implementation plan complete

**Deployment**:
- [ ] Package installable via pip
- [ ] Docker container works
- [ ] Runs on Windows/macOS/Linux
- [ ] No hardcoded paths

---

## Success Metrics

✅ **All Python files < 300 lines**
✅ **Every extracted element has complete citation (page, bbox, source)**
✅ **No information loss from PDF to output**
✅ **Full traceability from data → source location**
✅ **Test coverage > 80%**
✅ **Works on Windows, macOS, Linux**
✅ **Can run in Docker container**
✅ **Can drag-and-drop and run anywhere**
✅ **Handles text-heavy, image-heavy, and graphics-heavy PDFs**
✅ **OCR only regions without selectable text**
✅ **Human-readable MD + machine-readable JSON outputs**
✅ **POCT1 entity extraction with provenance**
✅ **Semantic + keyword search with citations**

---

**This is Version 1. No backwards compatibility. Citations are mandatory. Test everything.**
