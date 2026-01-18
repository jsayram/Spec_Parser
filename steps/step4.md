# Phase 4: CLI & LLM Integration (User Interface)

**Prerequisites**: Phases 1, 2, & 3 complete ✅
**Status**: Ready to implement
**Goal**: Build CLI interface and prepare for LLM integration

---

## Overview

Phase 4 implements:
- Click-based CLI with commands for all workflows
- Progress tracking and user-friendly output
- LLM integration scaffolding (placeholders for future)
- Prompt building utilities for LLM interactions
- Complete end-to-end workflows accessible via command line

CLI Commands:
- `parse` - Parse PDF to markdown + JSON
- `extract` - Extract POCT1 entities
- `index` - Build search indices
- `search` - Search indexed documents
- `pipeline` - Run complete workflow

---

## Step 4.1: Main CLI Entry Point (`cli/main.py`)

**Objective**: Create main CLI application with Click framework.

### Key Functionality

```python
import click
from pathlib import Path
from loguru import logger

from spec_parser.config import settings
from spec_parser import __version__

@click.group()
@click.version_option(version=__version__)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
@click.option(
    '--quiet', '-q',
    is_flag=True,
    help='Suppress non-error output'
)
def cli(verbose: bool, quiet: bool):
    """
    POCT1 Specification Parser and Normalizer
    
    Parse PDFs, extract entities, and search specifications with full provenance.
    """
    # Configure logging
    if quiet:
        logger.remove()
        logger.add(lambda msg: None if msg.record["level"].name != "ERROR" else print(msg))
    elif verbose:
        logger.level("DEBUG")
    else:
        logger.level("INFO")

@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--output-dir', '-o',
    type=click.Path(path_type=Path),
    default=None,
    help='Output directory (default: ./output)'
)
@click.option(
    '--with-ocr/--no-ocr',
    default=True,
    help='Enable OCR processing (default: enabled)'
)
def parse(pdf_path: Path, output_dir: Path, with_ocr: bool):
    """
    Parse PDF to structured markdown and JSON with citations.
    
    Example:
        spec-parser parse document.pdf -o output/
    """
    from spec_parser.cli.commands.parse_command import parse_pdf_command
    
    output_dir = output_dir or settings.output_dir
    parse_pdf_command(pdf_path, output_dir, with_ocr)

@cli.command()
@click.argument('json_dir', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    default=None,
    help='Output file for extracted entities'
)
def extract(json_dir: Path, output: Path):
    """
    Extract POCT1 entities from parsed JSON files.
    
    Example:
        spec-parser extract output/json/ -o entities.json
    """
    from spec_parser.cli.commands.extract_command import extract_entities_command
    
    output = output or (json_dir / "entities.json")
    extract_entities_command(json_dir, output)

@cli.command()
@click.argument('json_dir', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--index-dir', '-i',
    type=click.Path(path_type=Path),
    default=None,
    help='Directory to save search indices'
)
def index(json_dir: Path, index_dir: Path):
    """
    Build search indices (FAISS + BM25) from parsed documents.
    
    Example:
        spec-parser index output/json/ -i indices/
    """
    from spec_parser.cli.commands.index_command import build_indices_command
    
    index_dir = index_dir or settings.index_dir
    build_indices_command(json_dir, index_dir)

@cli.command()
@click.argument('query')
@click.option(
    '--index-dir', '-i',
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help='Directory with search indices'
)
@click.option(
    '--top-k', '-k',
    type=int,
    default=5,
    help='Number of results to return'
)
@click.option(
    '--method',
    type=click.Choice(['hybrid', 'faiss', 'bm25']),
    default='hybrid',
    help='Search method to use'
)
def search(query: str, index_dir: Path, top_k: int, method: str):
    """
    Search indexed documents.
    
    Example:
        spec-parser search "OBS.R01 message format" -k 10
    """
    from spec_parser.cli.commands.search_command import search_command
    
    index_dir = index_dir or settings.index_dir
    search_command(query, index_dir, top_k, method)

@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--output-dir', '-o',
    type=click.Path(path_type=Path),
    default=None,
    help='Output directory'
)
def pipeline(pdf_path: Path, output_dir: Path):
    """
    Run complete pipeline: parse → extract → index
    
    Example:
        spec-parser pipeline document.pdf -o output/
    """
    from spec_parser.cli.commands.pipeline_command import pipeline_command
    
    output_dir = output_dir or settings.output_dir
    pipeline_command(pdf_path, output_dir)

if __name__ == '__main__':
    cli()
```

### Implementation Details

- Use Click for CLI framework
- Group commands under main `cli()` group
- Support verbose and quiet modes
- Use `click.Path` for file validation
- Delegate to command modules for implementation
- Provide helpful examples in docstrings

### Tests Required (`tests/unit/test_cli_main.py`)

- ✅ Test CLI help output
- ✅ Test version option
- ✅ Test verbose/quiet flags
- ✅ Test command routing
- ✅ Mock command implementations

**File Size**: Target <200 lines

---

## Step 4.2: Parse Command (`cli/commands/parse_command.py`)

**Objective**: Implement PDF parsing command with progress tracking.

### Key Functionality

```python
from pathlib import Path
from loguru import logger
import click

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.parsers.ocr_processor import OCRProcessor
from spec_parser.parsers.md_merger import MarkdownMerger
from spec_parser.parsers.json_sidecar import JSONSidecarWriter
from spec_parser.utils.file_handler import ensure_directory, write_file
from spec_parser.exceptions import PDFExtractionError, OCRError

def parse_pdf_command(
    pdf_path: Path,
    output_dir: Path,
    with_ocr: bool = True
):
    """
    Parse PDF to markdown + JSON with citations.
    
    Workflow:
    1. Extract content with PyMuPDF
    2. Run OCR if enabled
    3. Merge markdown with OCR
    4. Write JSON sidecars
    5. Save final markdown
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    
    logger.info(f"Parsing PDF: {pdf_path}")
    logger.info(f"Output directory: {output_dir}")
    
    # Setup output directories
    ensure_directory(output_dir)
    ensure_directory(output_dir / "markdown")
    ensure_directory(output_dir / "json")
    ensure_directory(output_dir / "images")
    
    try:
        # Extract with PyMuPDF
        logger.info("Extracting content with PyMuPDF...")
        with PyMuPDFExtractor(pdf_path) as extractor:
            page_bundles = extractor.extract_all_pages()
        
        logger.info(f"Extracted {len(page_bundles)} pages")
        
        # OCR processing
        if with_ocr:
            logger.info("Running OCR on image regions...")
            ocr_processor = OCRProcessor()
            
            import pymupdf
            doc = pymupdf.open(pdf_path)
            
            with click.progressbar(
                page_bundles,
                label='OCR Processing',
                show_pos=True
            ) as progress_bundles:
                for bundle in progress_bundles:
                    page_num = bundle.page - 1  # 0-indexed
                    pdf_page = doc[page_num]
                    
                    ocr_results = ocr_processor.process_page(bundle, pdf_page)
                    
                    # Add OCR results to bundle
                    for ocr in ocr_results:
                        bundle.add_ocr(ocr)
            
            doc.close()
            logger.info(f"OCR completed")
        
        # Merge markdown
        logger.info("Merging markdown with citations...")
        md_merger = MarkdownMerger()
        
        full_markdown = []
        for bundle in page_bundles:
            page_md = md_merger.merge(bundle)
            full_markdown.append(page_md)
        
        # Write outputs
        logger.info("Writing outputs...")
        json_writer = JSONSidecarWriter(output_dir / "json")
        
        pdf_name = pdf_path.stem
        
        # Write JSON sidecars (per-page)
        for bundle in page_bundles:
            json_writer.write_page_bundle(bundle, pdf_name)
        
        # Write full document JSON
        json_writer.write_document(page_bundles, pdf_name)
        
        # Write markdown
        md_path = output_dir / "markdown" / f"{pdf_name}.md"
        write_file("\n\n---\n\n".join(full_markdown), md_path)
        
        # Success
        click.secho("✓ PDF parsed successfully!", fg='green', bold=True)
        click.echo(f"  Markdown: {md_path}")
        click.echo(f"  JSON: {output_dir / 'json'}")
        click.echo(f"  Images: {output_dir / 'images'}")
        
    except PDFExtractionError as e:
        logger.error(f"PDF extraction failed: {e}")
        click.secho(f"✗ Error: {e}", fg='red', err=True)
        raise click.Abort()
    
    except OCRError as e:
        logger.error(f"OCR processing failed: {e}")
        click.secho(f"✗ Error: {e}", fg='red', err=True)
        raise click.Abort()
    
    except Exception as e:
        logger.exception("Unexpected error during parsing")
        click.secho(f"✗ Unexpected error: {e}", fg='red', err=True)
        raise click.Abort()
```

### Implementation Details

- Show progress bar for OCR (long-running)
- Create output directory structure
- Save per-page + full document JSON
- Write combined markdown file
- Color-coded success/error messages
- Handle exceptions gracefully

### Tests Required (`tests/unit/test_parse_command.py`)

- ✅ Parse text-only PDF
- ✅ Parse with OCR enabled
- ✅ Parse with OCR disabled
- ✅ Verify output structure
- ✅ Test error handling

**File Size**: Target <200 lines

---

## Step 4.3: Extract Command (`cli/commands/extract_command.py`)

**Objective**: Extract POCT1 entities from parsed JSON files.

### Key Functionality

```python
from pathlib import Path
from loguru import logger
import click
import json

from spec_parser.extractors.spec_graph import SpecGraphExtractor
from spec_parser.models.page_bundle import PageBundle
from spec_parser.utils.file_handler import read_json, write_json

def extract_entities_command(
    json_dir: Path,
    output: Path
):
    """
    Extract POCT1 entities from parsed JSON files.
    
    Workflow:
    1. Load page bundles from JSON
    2. Extract messages, fields, schemas
    3. Save entities to output file
    """
    json_dir = Path(json_dir)
    output = Path(output)
    
    logger.info(f"Extracting entities from: {json_dir}")
    
    # Load page bundles
    json_files = sorted(json_dir.glob("*_p*.json"))
    
    if not json_files:
        click.secho("✗ No JSON files found", fg='red', err=True)
        raise click.Abort()
    
    logger.info(f"Found {len(json_files)} page bundle files")
    
    page_bundles = []
    for json_file in json_files:
        try:
            data = read_json(json_file)
            bundle = PageBundle(**data)
            page_bundles.append(bundle)
        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
    
    logger.info(f"Loaded {len(page_bundles)} page bundles")
    
    # Extract entities
    logger.info("Extracting POCT1 entities...")
    extractor = SpecGraphExtractor()
    
    messages = extractor.extract_messages(page_bundles)
    fields = extractor.extract_fields(page_bundles)
    schemas = extractor.extract_xml_schemas(page_bundles)
    
    logger.info(f"Extracted {len(messages)} messages, {len(fields)} fields, {len(schemas)} schemas")
    
    # Prepare output
    entities = {
        "messages": [msg.model_dump() for msg in messages],
        "fields": [field.model_dump() for field in fields],
        "schemas": [schema.model_dump() for schema in schemas],
        "metadata": {
            "source_files": [str(f) for f in json_files],
            "total_pages": len(page_bundles)
        }
    }
    
    # Write output
    write_json(entities, output, indent=2)
    
    # Success
    click.secho("✓ Entities extracted successfully!", fg='green', bold=True)
    click.echo(f"  Output: {output}")
    click.echo(f"  Messages: {len(messages)}")
    click.echo(f"  Fields: {len(fields)}")
    click.echo(f"  Schemas: {len(schemas)}")
```

### Implementation Details

- Load all JSON files from directory
- Parse as PageBundle objects
- Run entity extraction
- Save structured output
- Report extraction statistics

### Tests Required (`tests/unit/test_extract_command.py`)

- ✅ Extract from real JSON files
- ✅ Verify entity counts
- ✅ Validate output structure
- ✅ Test error handling

**File Size**: Target <150 lines

---

## Step 4.4: Index Command (`cli/commands/index_command.py`)

**Objective**: Build search indices from extracted entities.

### Key Functionality

```python
from pathlib import Path
from loguru import logger
import click

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_search import BM25Search
from spec_parser.utils.file_handler import read_json, ensure_directory
from spec_parser.models.page_bundle import PageBundle

def build_indices_command(
    json_dir: Path,
    index_dir: Path
):
    """
    Build search indices (FAISS + BM25) from parsed documents.
    
    Workflow:
    1. Load page bundles
    2. Prepare texts and metadata
    3. Build FAISS index
    4. Build BM25 index
    5. Save indices
    """
    json_dir = Path(json_dir)
    index_dir = Path(index_dir)
    
    logger.info(f"Building indices from: {json_dir}")
    logger.info(f"Index directory: {index_dir}")
    
    ensure_directory(index_dir)
    
    # Load page bundles
    json_files = sorted(json_dir.glob("*_p*.json"))
    
    if not json_files:
        click.secho("✗ No JSON files found", fg='red', err=True)
        raise click.Abort()
    
    logger.info(f"Found {len(json_files)} page bundle files")
    
    texts = []
    metadata = []
    
    with click.progressbar(
        json_files,
        label='Loading documents',
        show_pos=True
    ) as progress_files:
        for json_file in progress_files:
            try:
                data = read_json(json_file)
                bundle = PageBundle(**data)
                
                # Extract text chunks with metadata
                for block in bundle.blocks:
                    if hasattr(block, 'content') and block.content:
                        texts.append(block.content)
                        metadata.append({
                            "text": block.content,
                            "page": bundle.page,
                            "citation": block.citation,
                            "bbox": block.bbox,
                            "type": block.type,
                            "pdf_name": bundle.metadata.get('pdf_name', 'unknown')
                        })
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")
    
    logger.info(f"Prepared {len(texts)} text chunks for indexing")
    
    # Build FAISS index
    logger.info("Building FAISS index...")
    embedding_model = EmbeddingModel()
    faiss_indexer = FAISSIndexer(embedding_model, index_path=index_dir / "faiss.index")
    faiss_indexer.build_index(texts, metadata)
    faiss_indexer.save()
    
    # Build BM25 index
    logger.info("Building BM25 index...")
    bm25_search = BM25Search()
    bm25_search.build_index(texts, metadata)
    
    # Save BM25 index
    import pickle
    bm25_path = index_dir / "bm25.pkl"
    with open(bm25_path, 'wb') as f:
        pickle.dump({
            'bm25': bm25_search.bm25,
            'corpus': bm25_search.corpus,
            'metadata': bm25_search.metadata
        }, f)
    
    # Success
    click.secho("✓ Indices built successfully!", fg='green', bold=True)
    click.echo(f"  FAISS index: {index_dir / 'faiss.index'}")
    click.echo(f"  BM25 index: {bm25_path}")
    click.echo(f"  Indexed chunks: {len(texts)}")
```

### Implementation Details

- Load all page bundles
- Extract text chunks with metadata
- Build both FAISS and BM25 indices
- Save indices to disk
- Show progress bar

### Tests Required (`tests/unit/test_index_command.py`)

- ✅ Build indices from JSON
- ✅ Verify index files created
- ✅ Test index loading
- ✅ Validate metadata preservation

**File Size**: Target <200 lines

---

## Step 4.5: Search Command (`cli/commands/search_command.py`)

**Objective**: Search indexed documents from command line.

### Key Functionality

```python
from pathlib import Path
from loguru import logger
import click
import pickle

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_search import BM25Search
from spec_parser.search.hybrid_search import HybridSearch

def search_command(
    query: str,
    index_dir: Path,
    top_k: int,
    method: str
):
    """
    Search indexed documents.
    
    Args:
        query: Search query
        index_dir: Directory with indices
        top_k: Number of results
        method: Search method (hybrid|faiss|bm25)
    """
    index_dir = Path(index_dir)
    
    logger.info(f"Searching for: {query}")
    logger.info(f"Method: {method}, Top-K: {top_k}")
    
    # Load indices
    faiss_path = index_dir / "faiss.index"
    bm25_path = index_dir / "bm25.pkl"
    
    if not faiss_path.exists() or not bm25_path.exists():
        click.secho("✗ Indices not found. Run 'index' command first.", fg='red', err=True)
        raise click.Abort()
    
    # Load FAISS
    logger.info("Loading FAISS index...")
    embedding_model = EmbeddingModel()
    faiss_indexer = FAISSIndexer(embedding_model, index_path=faiss_path)
    faiss_indexer.load()
    
    # Load BM25
    logger.info("Loading BM25 index...")
    with open(bm25_path, 'rb') as f:
        bm25_data = pickle.load(f)
    
    bm25_search = BM25Search()
    bm25_search.bm25 = bm25_data['bm25']
    bm25_search.corpus = bm25_data['corpus']
    bm25_search.metadata = bm25_data['metadata']
    
    # Search
    logger.info("Searching...")
    
    if method == 'faiss':
        results = faiss_indexer.search(query, top_k=top_k)
    elif method == 'bm25':
        results = bm25_search.search(query, top_k=top_k)
    else:  # hybrid
        hybrid = HybridSearch(faiss_indexer, bm25_search)
        results = hybrid.search(query, top_k=top_k)
    
    # Display results
    click.echo()
    click.secho(f"Search Results ({len(results)} found):", fg='cyan', bold=True)
    click.echo()
    
    for idx, (meta, score) in enumerate(results, 1):
        click.secho(f"{idx}. Score: {score:.4f}", fg='yellow', bold=True)
        click.echo(f"   Page: {meta['page']}, Citation: {meta['citation']}")
        click.echo(f"   Type: {meta['type']}, PDF: {meta['pdf_name']}")
        click.echo(f"   Text: {meta['text'][:200]}...")
        click.echo()
```

### Implementation Details

- Load saved indices
- Support multiple search methods
- Format results nicely
- Show metadata and snippets
- Handle missing indices gracefully

### Tests Required (`tests/unit/test_search_command.py`)

- ✅ Search with each method
- ✅ Verify result format
- ✅ Test top-k filtering
- ✅ Test with no results

**File Size**: Target <150 lines

---

## Step 4.6: LLM Scaffolding (`llm/prompt_builder.py` & `llm/llm_interface.py`)

**Objective**: Create placeholders for future LLM integration.

### Prompt Builder

```python
from typing import List, Dict
from pydantic import BaseModel

class PromptTemplate(BaseModel):
    """Template for LLM prompts"""
    template: str
    variables: List[str]

class PromptBuilder:
    """
    Build prompts for LLM interactions.
    PLACEHOLDER for future LLM integration.
    """
    
    def __init__(self):
        """Initialize prompt builder"""
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, PromptTemplate]:
        """Load prompt templates"""
        return {
            "entity_extraction": PromptTemplate(
                template="Extract POCT1 entities from the following text:\n\n{text}\n\nEntities:",
                variables=["text"]
            ),
            "field_definition": PromptTemplate(
                template="Given this POCT1 field: {field}\n\nProvide a detailed explanation.",
                variables=["field"]
            )
        }
    
    def build(self, template_name: str, **kwargs) -> str:
        """
        Build prompt from template.
        
        Args:
            template_name: Name of template
            **kwargs: Variables to fill
            
        Returns:
            Formatted prompt string
        """
        template = self.templates.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")
        
        return template.template.format(**kwargs)
```

### LLM Interface

```python
from typing import Optional
from loguru import logger

class LLMInterface:
    """
    Interface for LLM interactions.
    PLACEHOLDER for future LLM integration.
    """
    
    def __init__(self, model: str = "gpt-4"):
        """Initialize LLM interface"""
        self.model = model
        logger.info(f"LLM Interface initialized (placeholder) with model: {model}")
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """
        Generate text from prompt.
        
        PLACEHOLDER - Not yet implemented.
        
        Args:
            prompt: Input prompt
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        logger.warning("LLM generation called but not yet implemented")
        return "LLM response (placeholder)"
```

### Tests Required

- ✅ Test prompt building
- ✅ Test template loading
- ✅ LLM interface placeholder

**File Size**: Each < 100 lines

---

## Phase 4 Completion Checklist

### Core Modules
- [ ] `cli/main.py` implemented
- [ ] `cli/commands/parse_command.py` implemented
- [ ] `cli/commands/extract_command.py` implemented
- [ ] `cli/commands/index_command.py` implemented
- [ ] `cli/commands/search_command.py` implemented
- [ ] `cli/commands/pipeline_command.py` implemented
- [ ] `llm/prompt_builder.py` implemented (placeholder)
- [ ] `llm/llm_interface.py` implemented (placeholder)

### Unit Tests
- [ ] Test CLI commands
- [ ] Test command options
- [ ] Test error handling
- [ ] Test prompt building

### Integration Tests
- [ ] Run parse command on real PDF
- [ ] Run extract command on parsed JSON
- [ ] Run index command on JSON
- [ ] Run search command
- [ ] Run complete pipeline

### Verification
- [ ] All files < 300 lines
- [ ] CLI help messages clear
- [ ] Progress bars work
- [ ] Error messages helpful
- [ ] Run tests: `pytest tests/unit/test_cli*.py`

---

## Expected Outcome

After completing Phase 4, you will have:

✅ **Complete CLI interface with all commands**
✅ **User-friendly progress tracking and output**
✅ **LLM scaffolding ready for future integration**
✅ **End-to-end workflows accessible from command line**
✅ **All files < 300 lines**
✅ **Ready for testing and packaging** in Phase 5

---

## Next Steps

Once Phase 4 is complete, proceed to **Phase 5: Testing & Packaging** (see `step5.md`)
