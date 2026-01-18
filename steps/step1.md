# Phase 1: Foundation (Core Infrastructure)

**Status**: Environment setup complete ✅
**Next**: Build foundation layer

---

## Overview

Phase 1 establishes the complete foundation for the POCT1 Spec Parser project. This includes:
- Project directory structure
- Core Pydantic data models (Citation, PageBundle, Blocks, OCR Results)
- Configuration management with environment variables
- Utility functions (logging, file handling, bounding box operations)
- Initial test infrastructure

All code in this phase follows the V1 greenfield approach with:
- No backwards compatibility
- Files < 300 lines
- Complete type hints
- Comprehensive testing
- Cross-platform support (Windows/macOS/Linux)

---

## Step 1.1: Create Project Structure

**Objective**: Establish the complete directory structure for the project with all necessary packages and submodules.

### Tasks

1. **Create main package directory**: `src/spec_parser/`
   
2. **Create subdirectories**:
   - `src/spec_parser/parsers/` - PDF parsing and extraction modules
   - `src/spec_parser/models/` - Pydantic data models and schemas
   - `src/spec_parser/extractors/` - POCT1 entity extraction logic
   - `src/spec_parser/search/` - FAISS and BM25 search implementations
   - `src/spec_parser/embeddings/` - Embedding model management
   - `src/spec_parser/llm/` - LLM integration (future use)
   - `src/spec_parser/utils/` - Utility functions and helpers

3. **Create test directory structure**:
   - `tests/fixtures/` - Test data directory for PDFs and expected outputs
   - `tests/unit/` - Unit tests for individual modules
   - `tests/integration/` - End-to-end integration tests

4. **Add `__init__.py` files** to all packages to make them importable

5. **Each `__init__.py` should expose key classes/functions** from the module for easy importing

### Files to Create

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

### Success Criteria

✅ All directories exist
✅ All `__init__.py` files are present
✅ Package structure is importable: `from spec_parser.models import ...`
✅ Tests can discover and import project modules

---

## Step 1.2: Core Data Models (Pydantic Schemas)

**Objective**: Define the core data structures for citations, page bundles, blocks, and OCR results using Pydantic for validation and type safety.

### Step 1.2.1: Citation Model (`models/citation.py`)

**Purpose**: Represent provenance metadata for every extracted element - the foundation of our citation-first architecture.

**Data Structure**:
```python
from pydantic import BaseModel, Field, validator
from typing import Literal, Optional, Tuple

class Citation(BaseModel):
    """
    Citation model for provenance tracking.
    Every extracted element must have a citation linking it back to source.
    """
    citation_id: str = Field(
        ...,
        description="Unique identifier: p{page}_{type}_{index}",
        example="p12_img3"
    )
    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    bbox: Tuple[float, float, float, float] = Field(
        ...,
        description="Bounding box [x0, y0, x1, y1]"
    )
    source: Literal["text", "ocr", "graphics"] = Field(
        ...,
        description="Where data came from"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="OCR confidence score"
    )
    content_type: Literal["picture", "table", "text", "graphics"]
    file_reference: Optional[str] = Field(
        None,
        description="Reference to extracted image file"
    )
    
    @validator('bbox')
    def validate_bbox(cls, v):
        """Ensure bbox coordinates are valid"""
        x0, y0, x1, y1 = v
        if x0 >= x1 or y0 >= y1:
            raise ValueError(f"Invalid bbox coordinates: {v}")
        return v
    
    @validator('citation_id')
    def validate_citation_id_format(cls, v):
        """Ensure citation ID follows format: p{page}_{type}_{index}"""
        import re
        if not re.match(r'^p\d+_[a-z]+_\d+$', v):
            raise ValueError(f"Invalid citation_id format: {v}")
        return v
    
    def to_markdown_footnote(self) -> str:
        """
        Generate markdown footnote text.
        
        Returns:
            str: Formatted citation like:
                [^p12_img3]: Page 12, bbox [100, 200, 500, 400], source: ocr, file: page12_img3.png
        """
        parts = [
            f"Page {self.page}",
            f"bbox {list(self.bbox)}",
            f"source: {self.source}"
        ]
        if self.file_reference:
            parts.append(f"file: {self.file_reference}")
        if self.confidence is not None:
            parts.append(f"confidence: {self.confidence:.2f}")
        
        return f"[^{self.citation_id}]: {', '.join(parts)}"
    
    class Config:
        json_schema_extra = {
            "example": {
                "citation_id": "p12_img3",
                "page": 12,
                "bbox": [100.5, 200.0, 500.0, 400.0],
                "source": "ocr",
                "confidence": 0.87,
                "content_type": "picture",
                "file_reference": "page12_img3.png"
            }
        }
```

**Key Features**:
- Type validation with Pydantic
- Mandatory fields: citation_id, page, bbox, source, content_type
- Optional confidence score for OCR results
- File reference for linking to extracted images
- Custom validators for bbox format and citation_id format
- Helper method: `to_markdown_footnote()`
- Example schema for documentation

**Tests Required** (`tests/unit/test_citation.py`):
- ✅ Valid citation creation
- ✅ Invalid bbox coordinates rejected (x0 >= x1 or y0 >= y1)
- ✅ Citation ID format validation (must match p{page}_{type}_{index})
- ✅ Confidence score range validation (0.0-1.0)
- ✅ JSON serialization/deserialization
- ✅ Markdown footnote generation
- ✅ Optional fields (confidence, file_reference) can be None

**File Size**: Target <150 lines

---

### Step 1.2.2: Block Models (`models/page_bundle.py`)

**Purpose**: Define the structure for content blocks extracted from PDF pages - text, images, tables, graphics.

**Data Structures**:

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Union, Dict, Any, Tuple

class Block(BaseModel):
    """Base class for all content blocks"""
    type: Literal["text", "picture", "table", "graphics"]
    bbox: Tuple[float, float, float, float]
    citation: str = Field(..., description="Reference to Citation.citation_id")

class TextBlock(Block):
    """Text content block with markdown slice"""
    type: Literal["text"] = "text"
    md_slice: Tuple[int, int] = Field(
        ...,
        description="[start, stop] position in markdown text"
    )
    content: str = Field(..., description="Actual text content")

class PictureBlock(Block):
    """Image/picture block"""
    type: Literal["picture"] = "picture"
    image_ref: str = Field(..., description="Path to extracted image file")
    source: Literal["pdf", "screenshot"] = Field(
        "pdf",
        description="Source of the image"
    )

class TableBlock(Block):
    """Table content block"""
    type: Literal["table"] = "table"
    table_ref: str = Field(..., description="Table identifier")
    markdown_table: Optional[str] = Field(
        None,
        description="Table rendered as markdown"
    )

class GraphicsBlock(Block):
    """Vector graphics block"""
    type: Literal["graphics"] = "graphics"
    source: Literal["vector", "mixed"] = Field(
        "vector",
        description="Type of graphics content"
    )

class OCRResult(BaseModel):
    """OCR extraction result"""
    bbox: Tuple[float, float, float, float]
    text: str = Field(..., description="Extracted text from OCR")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Tesseract confidence")
    source: Literal["tesseract", "easyocr"] = Field(
        "tesseract",
        description="OCR engine used"
    )
    citation: str = Field(..., description="Reference to Citation.citation_id")
    associated_block: Optional[str] = Field(
        None,
        description="Citation ID of related image/graphics block"
    )
    language: str = Field("eng", description="OCR language used")

class PageBundle(BaseModel):
    """
    Complete bundle of extracted content for a single page.
    Includes markdown, blocks, OCR results, and citations with full provenance.
    """
    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    markdown: str = Field(..., description="Full markdown text for this page")
    blocks: List[Union[TextBlock, PictureBlock, TableBlock, GraphicsBlock]] = Field(
        default_factory=list,
        description="All content blocks"
    )
    ocr: List[OCRResult] = Field(
        default_factory=list,
        description="All OCR results for this page"
    )
    citations: Dict[str, Any] = Field(
        default_factory=dict,
        description="Lookup dict: citation_id -> Citation"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional page metadata"
    )
    
    def get_citation(self, citation_id: str) -> Optional[Any]:
        """Retrieve citation by ID"""
        return self.citations.get(citation_id)
    
    def add_block(self, block: Block, citation: Any) -> None:
        """Add a block and its citation"""
        self.blocks.append(block)
        self.citations[block.citation] = citation
    
    def add_ocr_result(self, ocr: OCRResult, citation: Any) -> None:
        """Add an OCR result and its citation"""
        self.ocr.append(ocr)
        self.citations[ocr.citation] = citation
    
    def get_blocks_by_type(self, block_type: str) -> List[Block]:
        """Get all blocks of a specific type"""
        return [b for b in self.blocks if b.type == block_type]
    
    def has_ocr(self) -> bool:
        """Check if page has any OCR results"""
        return len(self.ocr) > 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "page": 12,
                "markdown": "## Section Title\n\nContent...",
                "blocks": [
                    {
                        "type": "text",
                        "bbox": [50, 100, 550, 120],
                        "md_slice": [0, 15],
                        "content": "Section Title",
                        "citation": "p12_text_1"
                    }
                ],
                "ocr": [],
                "citations": {},
                "metadata": {}
            }
        }
```

**Key Features**:
- Union types for different block types
- Nested Pydantic models with full validation
- Helper methods for citation management
- JSON serialization with proper typing
- Validation for bbox coordinates
- Automatic citation linking
- Type-specific block queries

**Tests Required** (`tests/unit/test_page_bundle.py`):
- ✅ Create PageBundle with mixed block types
- ✅ Add blocks and verify citation linking
- ✅ Serialize/deserialize to JSON
- ✅ Validate bbox coordinates
- ✅ Test OCR confidence ranges
- ✅ Test citation lookup methods
- ✅ Test get_blocks_by_type filtering
- ✅ Test has_ocr flag
- ✅ Test empty page bundle

**File Size**: Target <300 lines (if larger, split into separate files for each block type)

---

## Step 1.3: Configuration & Core Utilities

### Step 1.3.1: Configuration Management (`config.py`)

**Objective**: Centralized configuration using environment variables with type-safe defaults.

**Implementation**:
```python
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Literal

class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    Loads from .env file if present.
    """
    
    # OCR Configuration
    ocr_engine: Literal["tesseract", "easyocr"] = "tesseract"
    ocr_language: str = "eng"
    ocr_dpi: int = Field(300, ge=72, le=600, description="DPI for rendering")
    ocr_confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    
    # Embedding Model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: Literal["cpu", "cuda"] = "cpu"
    
    # Search Configuration
    faiss_index_type: str = "Flat"
    bm25_k1: float = Field(1.5, gt=0.0)
    bm25_b: float = Field(0.75, ge=0.0, le=1.0)
    
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
        env_prefix = ""
    
    def ensure_directories(self) -> None:
        """Create output directories if they don't exist"""
        for dir_path in [self.output_dir, self.image_dir, self.json_dir, self.markdown_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

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
- Validation ranges for numeric values

**Tests Required** (`tests/unit/test_config.py`):
- ✅ Load settings from environment
- ✅ Override defaults with .env file
- ✅ Path creation and validation
- ✅ Invalid value rejection (e.g., negative DPI, DPI > 600)
- ✅ Test ensure_directories creates all paths
- ✅ Test case-insensitive env vars

**File Size**: Target <150 lines

---

### Step 1.3.2: Custom Exceptions (`exceptions.py`)

**Objective**: Define domain-specific exceptions for better error handling throughout the application.

**Implementation**:
```python
"""
Custom exceptions for the Spec Parser.
All exceptions inherit from SpecParserError for easy catch-all handling.
"""

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

class FileOperationError(SpecParserError):
    """Error during file read/write operations"""
    pass
```

**Key Features**:
- Hierarchical exception structure
- Clear error types for different failure modes
- Inherits from base `SpecParserError` for catch-all handling
- Descriptive names for debugging
- Docstrings for each exception

**Tests Required** (`tests/unit/test_exceptions.py`):
- ✅ Raise and catch each exception type
- ✅ Verify inheritance chain
- ✅ Test error messages
- ✅ Test catch-all with SpecParserError

**File Size**: Target <100 lines

---

### Step 1.3.3: Logging Setup (`utils/logger.py`)

**Objective**: Configure loguru for structured logging with appropriate formatting and levels.

**Implementation**:
```python
from loguru import logger
from pathlib import Path
import sys

def setup_logger(log_level: str = "INFO") -> None:
    """
    Configure loguru logger based on settings.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handler
    logger.remove()
    
    # Console handler with color
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # File handler with rotation
    log_file = Path("logs") / "spec_parser.log"
    log_file.parent.mkdir(exist_ok=True)
    
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        rotation="10 MB",
        retention="1 week",
        compression="zip"
    )
    
    logger.info(f"Logger initialized at level {log_level}")

# Initialize on import with default settings
# Can be reconfigured by calling setup_logger() again
try:
    from spec_parser.config import settings
    setup_logger(settings.log_level)
except ImportError:
    # During initial setup, config might not exist yet
    setup_logger("INFO")
```

**Key Features**:
- Colored console output for readability
- File logging with rotation and compression
- Structured format with module/function/line info
- Configurable log level from settings
- Automatic log directory creation
- Can be reconfigured at runtime

**Tests Required** (`tests/unit/test_logger.py`):
- ✅ Logger initialization
- ✅ Log messages at different levels
- ✅ File creation and rotation
- ✅ Console output formatting
- ✅ Reconfiguration with different log levels

**File Size**: Target <100 lines

---

### Step 1.3.4: Bounding Box Utilities (`utils/bbox_utils.py`)

**Objective**: Utility functions for working with bounding boxes - distance calculation, overlap detection, merging.

**Implementation** (see STEPS.md for full code - included bbox_distance, bbox_overlap, bbox_area, bbox_intersection_area, bbox_iou, bbox_contains_point, bbox_merge, validate_bbox)

**Key Features**:
- Manhattan distance for caption proximity
- Overlap detection for text-check
- IoU calculation for bbox matching
- Merge utility for combining regions
- Validation for bbox coordinates
- Type hints for clarity
- Comprehensive docstrings

**Tests Required** (`tests/unit/test_bbox_utils.py`):
- ✅ Distance calculation with known values
- ✅ Overlap detection (overlapping and non-overlapping cases)
- ✅ IoU calculation with known values
- ✅ Bbox merging multiple boxes
- ✅ Edge cases: zero-area boxes, negative coordinates
- ✅ Contains point tests
- ✅ Validation rejects invalid bboxes

**File Size**: Target <200 lines

---

### Step 1.3.5: File Handler (`utils/file_handler.py`)

**Objective**: Cross-platform file operations using `pathlib` for reading, writing, and managing PDF/image files.

**Implementation** (see STEPS.md for full code - included ensure_directory, read_json, write_json, read_text, write_text, copy_file, get_output_path)

**Key Features**:
- Cross-platform path handling with `pathlib`
- Automatic directory creation
- Error handling with descriptive messages
- Consistent naming conventions
- UTF-8 encoding by default
- Logging for debugging
- Helper for generating output paths

**Tests Required** (`tests/unit/test_file_handler.py`):
- ✅ Directory creation
- ✅ JSON read/write round-trip
- ✅ Text read/write round-trip
- ✅ File copying
- ✅ Output path generation with/without page numbers
- ✅ Cross-platform path handling
- ✅ Error handling for missing files

**File Size**: Target <200 lines

---

### Step 1.3.6: Environment Configuration Template (`.env.example`)

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

---

## Step 1.4: Initial Testing Infrastructure

**Objective**: Set up pytest configuration and basic test structure before writing tests.

### Step 1.4.1: Pytest Configuration (`tests/conftest.py`)

**Implementation**:
```python
import pytest
from pathlib import Path
from spec_parser.config import Settings
from spec_parser.models.citation import Citation

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
    return Citation(
        citation_id="p1_text_1",
        page=1,
        bbox=(100.0, 200.0, 300.0, 400.0),
        source="text",
        content_type="text"
    )

@pytest.fixture
def sample_citation_with_ocr():
    """Provide a sample OCR citation"""
    return Citation(
        citation_id="p2_ocr_1",
        page=2,
        bbox=(150.0, 250.0, 350.0, 450.0),
        source="ocr",
        content_type="picture",
        confidence=0.85,
        file_reference="page2_img1.png"
    )
```

**Key Features**:
- Temporary directories for test isolation
- Test-specific settings to avoid modifying real data
- Reusable fixtures for common test data
- Clear fixture naming
- Fixtures for different citation types

**File Size**: Target <200 lines (will grow as we add more fixtures)

---

## Phase 1 Completion Checklist

### Directory Structure
- [ ] `src/spec_parser/` created with all subdirectories
- [ ] All `__init__.py` files added
- [ ] `tests/` structure created (unit, integration, fixtures)

### Core Models
- [ ] `models/citation.py` - Citation model with validation
- [ ] `models/page_bundle.py` - Block models and PageBundle
- [ ] Unit tests for Citation model
- [ ] Unit tests for PageBundle model

### Configuration & Utilities
- [ ] `config.py` - Settings with environment variables
- [ ] `exceptions.py` - Custom exception hierarchy
- [ ] `utils/logger.py` - Loguru setup
- [ ] `utils/bbox_utils.py` - Bounding box utilities
- [ ] `utils/file_handler.py` - Cross-platform file operations
- [ ] `.env.example` - Configuration template
- [ ] Unit tests for all utilities

### Testing Infrastructure
- [ ] `tests/conftest.py` - Pytest configuration
- [ ] All fixtures defined
- [ ] Test discovery working

### Verification
- [ ] All files < 300 lines
- [ ] All functions have type hints
- [ ] All public methods have docstrings
- [ ] Import structure works: `from spec_parser.models import Citation`
- [ ] Run tests: `pytest tests/unit/`
- [ ] Code formatted with black
- [ ] No linting errors with ruff

---

## Expected Outcome

After completing Phase 1, you will have:

✅ **Solid foundation** with type-safe models
✅ **Reusable utilities** for file and bbox operations
✅ **Configurable environment** via .env
✅ **Test infrastructure** ready for development
✅ **All files < 300 lines** following V1 greenfield approach
✅ **Ready to build** parsing pipeline in Phase 2

---

## Next Steps

Once Phase 1 is complete, proceed to **Phase 2: PDF Parsing Pipeline** (see `step2.md`)
