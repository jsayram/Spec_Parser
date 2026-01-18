# Phase 3: Entity Extraction & Search (POCT1 Normalization)

**Prerequisites**: Phases 1 & 2 complete ✅
**Status**: Ready to implement
**Goal**: Extract POCT1 entities and build searchable index with semantic + keyword search

---

## Overview

Phase 3 implements:
- POCT1-specific entity extraction (messages, fields, XML schemas)
- Vector embeddings with FAISS for semantic search
- BM25 for keyword search
- Hybrid search combining both approaches
- All entities maintain complete provenance chains

Every extracted entity includes:
- Source PDF + page + bbox
- Citation linking back to original location
- Confidence scores where applicable

---

## Step 3.1: POCT1 Spec Graph Extractor (`extractors/spec_graph.py`)

**Objective**: Extract structured POCT1 entities from parsed documents using pattern matching and LLM assistance.

### Key Functionality

```python
import re
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from loguru import logger

from spec_parser.models.page_bundle import PageBundle
from spec_parser.models.citation import Citation

class POCT1Message(BaseModel):
    """POCT1 message definition"""
    message_id: str  # e.g., "OBS.R01", "QCN.R01"
    name: str  # e.g., "Observation Result"
    description: Optional[str] = None
    page: int
    citation: str
    bbox: tuple[float, float, float, float]

class POCT1Field(BaseModel):
    """POCT1 field definition"""
    segment: str  # e.g., "MSH", "OBX", "QCN"
    field_num: str  # e.g., "3", "5.1"
    name: str
    type: str  # e.g., "ST", "CE", "NM"
    optionality: str  # "R", "O", "C"
    cardinality: str  # e.g., "1", "0..1", "1..*"
    description: Optional[str] = None
    page: int
    citation: str
    bbox: tuple[float, float, float, float]

class POCT1XMLSchema(BaseModel):
    """XML schema snippet"""
    schema_name: str
    content: str
    namespace: Optional[str] = None
    page: int
    citation: str
    bbox: tuple[float, float, float, float]

class SpecGraphExtractor:
    """
    Extract POCT1 entities from parsed documents.
    Uses regex + heuristics for pattern matching.
    """
    
    def __init__(self):
        """Initialize extractor with patterns"""
        self.message_pattern = re.compile(
            r'\b([A-Z]{3})\s*\.\s*([A-Z]\d{2})\b'
        )
        self.field_table_pattern = re.compile(
            r'^\s*\|\s*(\d+(?:\.\d+)?)\s*\|.*?\|.*?\|\s*([RO])\s*\|',
            re.MULTILINE
        )
    
    def extract_messages(self, page_bundles: List[PageBundle]) -> List[POCT1Message]:
        """
        Extract message definitions (e.g., OBS.R01, QCN.R01).
        
        Args:
            page_bundles: List of parsed page bundles
            
        Returns:
            List of POCT1Message objects
        """
        messages = []
        
        for bundle in page_bundles:
            # Search in markdown text
            matches = self.message_pattern.finditer(bundle.markdown)
            
            for match in matches:
                message_id = f"{match.group(1)}.{match.group(2)}"
                
                # Find corresponding text block
                block = self._find_block_for_match(bundle, match.start(), match.end())
                
                if block:
                    message = POCT1Message(
                        message_id=message_id,
                        name=self._extract_message_name(bundle.markdown, match),
                        page=bundle.page,
                        citation=block.citation,
                        bbox=block.bbox
                    )
                    messages.append(message)
                    logger.debug(f"Extracted message {message_id} from page {bundle.page}")
        
        return messages
    
    def extract_fields(self, page_bundles: List[PageBundle]) -> List[POCT1Field]:
        """
        Extract field definitions from tables.
        
        Pattern:
        | Field # | Name | Type | Opt | Card |
        | 3 | Message Type | CE | R | 1 |
        
        Args:
            page_bundles: List of parsed page bundles
            
        Returns:
            List of POCT1Field objects
        """
        fields = []
        
        for bundle in page_bundles:
            # Look for table blocks
            for table in bundle.get_blocks_by_type("table"):
                if not table.markdown_table:
                    continue
                
                # Parse table rows
                rows = self._parse_table_rows(table.markdown_table)
                
                for row in rows:
                    # Extract field information
                    field = self._parse_field_row(row, bundle.page, table.citation, table.bbox)
                    if field:
                        fields.append(field)
                        logger.debug(f"Extracted field {field.name} from page {bundle.page}")
        
        return fields
    
    def extract_xml_schemas(self, page_bundles: List[PageBundle]) -> List[POCT1XMLSchema]:
        """
        Extract XML schema snippets.
        
        Look for code blocks with XML content.
        
        Args:
            page_bundles: List of parsed page bundles
            
        Returns:
            List of POCT1XMLSchema objects
        """
        schemas = []
        xml_pattern = re.compile(r'```xml\n(.*?)\n```', re.DOTALL)
        
        for bundle in page_bundles:
            matches = xml_pattern.finditer(bundle.markdown)
            
            for idx, match in enumerate(matches):
                xml_content = match.group(1)
                
                # Extract namespace if present
                namespace_match = re.search(r'xmlns(?::(\w+))?="([^"]+)"', xml_content)
                namespace = namespace_match.group(2) if namespace_match else None
                
                # Find corresponding block
                block = self._find_block_for_match(bundle, match.start(), match.end())
                
                if block:
                    schema = POCT1XMLSchema(
                        schema_name=f"schema_{bundle.page}_{idx+1}",
                        content=xml_content,
                        namespace=namespace,
                        page=bundle.page,
                        citation=block.citation,
                        bbox=block.bbox
                    )
                    schemas.append(schema)
                    logger.debug(f"Extracted XML schema from page {bundle.page}")
        
        return schemas
    
    def _find_block_for_match(
        self,
        bundle: PageBundle,
        start: int,
        end: int
    ):
        """Find block containing markdown slice position"""
        for block in bundle.blocks:
            if hasattr(block, 'md_slice'):
                slice_start, slice_end = block.md_slice
                if slice_start <= start < slice_end:
                    return block
        return None
    
    def _extract_message_name(self, markdown: str, match) -> str:
        """Extract message name from context around match"""
        # Look ahead for message name (heuristic)
        context = markdown[match.end():match.end()+100]
        lines = context.split('\n')
        if lines:
            # First line after match likely contains name
            return lines[0].strip(' -–:')
        return "Unknown Message"
    
    def _parse_table_rows(self, markdown_table: str) -> List[List[str]]:
        """Parse markdown table into rows"""
        rows = []
        lines = markdown_table.strip().split('\n')
        
        for line in lines:
            # Skip separator rows
            if re.match(r'^\s*\|[\s\-:|]+\|$', line):
                continue
            
            # Split by | and clean
            cells = [cell.strip() for cell in line.split('|')]
            cells = [cell for cell in cells if cell]  # Remove empty
            
            if cells:
                rows.append(cells)
        
        return rows
    
    def _parse_field_row(
        self,
        row: List[str],
        page: int,
        citation: str,
        bbox: tuple
    ) -> Optional[POCT1Field]:
        """Parse a field table row into POCT1Field"""
        try:
            # Expected format: | Field# | Name | Type | Opt | Card |
            if len(row) < 5:
                return None
            
            return POCT1Field(
                segment="MSH",  # Determine from context
                field_num=row[0],
                name=row[1],
                type=row[2],
                optionality=row[3],
                cardinality=row[4],
                page=page,
                citation=citation,
                bbox=bbox
            )
        except Exception as e:
            logger.warning(f"Failed to parse field row: {e}")
            return None
```

### Implementation Details

- Use regex patterns for known message formats
- Parse markdown tables for field definitions
- Extract XML code blocks with namespace detection
- Link entities back to source blocks via citations
- Preserve all positional metadata
- Handle variations in formatting

### Entity Patterns to Extract

1. **Messages**: `OBS.R01`, `OPL.R01`, `QCN.R01`, etc.
2. **Segments**: `MSH`, `PID`, `OBX`, `OBR`, etc.
3. **Fields**: Format `segment.field.component`
4. **Data Types**: `ST`, `CE`, `NM`, `TS`, etc.
5. **XML Schemas**: Namespaces and element definitions

### Tests Required (`tests/unit/test_spec_graph.py`)

- ✅ Extract message definitions
- ✅ Extract field tables
- ✅ Extract XML schemas
- ✅ Validate citation preservation
- ✅ Handle variations in formatting
- ✅ Test with real POCT1 spec pages

**File Size**: Target <300 lines

---

## Step 3.2: Embedding Model Manager (`embeddings/embedding_model.py`)

**Objective**: Manage embedding generation using sentence-transformers with CPU-friendly models.

### Key Functionality

```python
from typing import List, Optional
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

from spec_parser.config import settings
from spec_parser.exceptions import EmbeddingError

class EmbeddingModel:
    """
    Manage text embeddings using sentence-transformers.
    Uses lightweight CPU-friendly model by default.
    """
    
    def __init__(
        self,
        model_name: str = None,
        device: str = "cpu"
    ):
        """
        Initialize embedding model.
        
        Args:
            model_name: Model name from HuggingFace (default: all-MiniLM-L6-v2)
            device: Device to run on ("cpu" or "cuda")
        """
        self.model_name = model_name or settings.embedding_model
        self.device = device
        self.model = None
    
    def load(self):
        """Load embedding model"""
        if self.model is not None:
            logger.debug(f"Model {self.model_name} already loaded")
            return
        
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Model loaded successfully")
        except Exception as e:
            raise EmbeddingError(f"Failed to load model {self.model_name}: {e}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as numpy array
        """
        if self.model is None:
            self.load()
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            raise EmbeddingError(f"Failed to embed text: {e}")
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for batch of texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            
        Returns:
            Array of embeddings (shape: [num_texts, embedding_dim])
        """
        if self.model is None:
            self.load()
        
        try:
            logger.debug(f"Embedding batch of {len(texts)} texts")
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=True
            )
            return embeddings
        except Exception as e:
            raise EmbeddingError(f"Failed to embed batch: {e}")
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        if self.model is None:
            self.load()
        return self.model.get_sentence_embedding_dimension()
```

### Model Selection

**Default**: `all-MiniLM-L6-v2`
- Embedding dimension: 384
- CPU-friendly
- Fast inference
- Good quality for technical text

**Alternatives**:
- `all-mpnet-base-v2`: Higher quality, slower
- `paraphrase-MiniLM-L3-v2`: Smaller, faster

### Implementation Details

- Lazy loading (load on first use)
- Batch processing for efficiency
- Progress bar for large batches
- CPU by default (GPU optional)
- Cache model downloads

### Tests Required (`tests/unit/test_embedding_model.py`)

- ✅ Load model successfully
- ✅ Embed single text
- ✅ Embed batch of texts
- ✅ Validate embedding dimensions
- ✅ Handle invalid text
- ✅ Test lazy loading

**File Size**: Target <150 lines

---

## Step 3.3: FAISS Indexer (`search/faiss_indexer.py`)

**Objective**: Build and manage FAISS vector index for semantic search.

### Key Functionality

```python
import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from loguru import logger

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.exceptions import SearchError
from spec_parser.utils.file_handler import ensure_directory

class FAISSIndexer:
    """
    FAISS-based semantic search index.
    Stores embeddings with metadata for retrieval.
    """
    
    def __init__(
        self,
        embedding_model: EmbeddingModel,
        index_path: Path = None
    ):
        """
        Initialize FAISS indexer.
        
        Args:
            embedding_model: Embedding model for encoding queries
            index_path: Path to save/load index
        """
        self.embedding_model = embedding_model
        self.index_path = index_path
        self.index = None
        self.metadata = []  # List of metadata dicts, one per vector
    
    def build_index(self, texts: List[str], metadata: List[Dict]):
        """
        Build FAISS index from texts and metadata.
        
        Args:
            texts: List of text chunks to index
            metadata: List of metadata dicts (must match texts length)
        """
        if len(texts) != len(metadata):
            raise SearchError("texts and metadata must have same length")
        
        logger.info(f"Building FAISS index for {len(texts)} documents")
        
        # Generate embeddings
        embeddings = self.embedding_model.embed_batch(texts)
        
        # Create FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product (cosine sim)
        
        # Normalize vectors for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self.index.add(embeddings)
        self.metadata = metadata
        
        logger.info(f"FAISS index built with {self.index.ntotal} vectors")
    
    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Tuple[Dict, float]]:
        """
        Search index for query.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            List of (metadata, score) tuples, sorted by score (desc)
        """
        if self.index is None:
            raise SearchError("Index not built. Call build_index() first.")
        
        # Embed query
        query_embedding = self.embedding_model.embed_text(query)
        query_embedding = query_embedding.reshape(1, -1)
        
        # Normalize
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding, top_k)
        
        # Build results
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < len(self.metadata):
                results.append((self.metadata[idx], float(score)))
        
        logger.debug(f"FAISS search returned {len(results)} results")
        return results
    
    def save(self, path: Path = None):
        """Save FAISS index to disk"""
        save_path = path or self.index_path
        if save_path is None:
            raise SearchError("No index path specified")
        
        ensure_directory(save_path.parent)
        
        # Save index
        faiss.write_index(self.index, str(save_path))
        
        # Save metadata separately
        import pickle
        metadata_path = save_path.with_suffix('.metadata.pkl')
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        
        logger.info(f"Saved FAISS index to {save_path}")
    
    def load(self, path: Path = None):
        """Load FAISS index from disk"""
        load_path = path or self.index_path
        if load_path is None or not load_path.exists():
            raise SearchError(f"Index not found at {load_path}")
        
        # Load index
        self.index = faiss.read_index(str(load_path))
        
        # Load metadata
        import pickle
        metadata_path = load_path.with_suffix('.metadata.pkl')
        with open(metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
        
        logger.info(f"Loaded FAISS index from {load_path} ({self.index.ntotal} vectors)")
```

### Implementation Details

- Use `IndexFlatIP` for cosine similarity (inner product)
- Normalize vectors for proper cosine similarity
- Store metadata alongside vectors
- Support save/load for persistence
- Return results with scores

### Metadata Format

```python
{
    "text": "Original text chunk",
    "page": 12,
    "citation": "p12_text_3",
    "bbox": [100, 200, 500, 300],
    "type": "text|picture|table",
    "pdf_name": "spec.pdf"
}
```

### Tests Required (`tests/unit/test_faiss_indexer.py`)

- ✅ Build index from texts
- ✅ Search returns relevant results
- ✅ Save and load index
- ✅ Handle empty query
- ✅ Validate metadata preservation
- ✅ Test with various top_k values

**File Size**: Target <200 lines

---

## Step 3.4: BM25 Search (`search/bm25_search.py`)

**Objective**: Implement keyword-based search using BM25 algorithm.

### Key Functionality

```python
from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
from loguru import logger

from spec_parser.exceptions import SearchError

class BM25Search:
    """BM25 keyword-based search"""
    
    def __init__(self):
        """Initialize BM25 search"""
        self.bm25 = None
        self.corpus = []
        self.metadata = []
    
    def build_index(self, texts: List[str], metadata: List[Dict]):
        """
        Build BM25 index from texts.
        
        Args:
            texts: List of text chunks to index
            metadata: List of metadata dicts
        """
        if len(texts) != len(metadata):
            raise SearchError("texts and metadata must have same length")
        
        logger.info(f"Building BM25 index for {len(texts)} documents")
        
        # Tokenize corpus
        tokenized_corpus = [self._tokenize(text) for text in texts]
        
        # Build BM25 index
        self.bm25 = BM25Okapi(tokenized_corpus)
        self.corpus = texts
        self.metadata = metadata
        
        logger.info(f"BM25 index built with {len(self.corpus)} documents")
    
    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Tuple[Dict, float]]:
        """
        Search using BM25 keyword matching.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (metadata, score) tuples
        """
        if self.bm25 is None:
            raise SearchError("Index not built. Call build_index() first.")
        
        # Tokenize query
        query_tokens = self._tokenize(query)
        
        # Get scores
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top-k indices
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]
        
        # Build results
        results = [
            (self.metadata[idx], float(scores[idx]))
            for idx in top_indices
        ]
        
        logger.debug(f"BM25 search returned {len(results)} results")
        return results
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization (can be improved)"""
        import re
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r'\w+', text.lower())
        return tokens
```

### Implementation Details

- Use `rank_bm25` library
- Simple tokenization (can be enhanced)
- Fast keyword matching
- Good for exact term searches

### Tests Required (`tests/unit/test_bm25_search.py`)

- ✅ Build index
- ✅ Search returns relevant results
- ✅ Test with exact keyword matches
- ✅ Test with partial matches
- ✅ Validate scoring

**File Size**: Target <150 lines

---

## Step 3.5: Hybrid Search (`search/hybrid_search.py`)

**Objective**: Combine FAISS semantic search with BM25 keyword search for best results.

### Key Functionality

```python
from typing import List, Dict, Tuple
from loguru import logger

from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_search import BM25Search

class HybridSearch:
    """
    Hybrid search combining semantic (FAISS) and keyword (BM25) search.
    Uses weighted fusion for result ranking.
    """
    
    def __init__(
        self,
        faiss_indexer: FAISSIndexer,
        bm25_search: BM25Search,
        alpha: float = 0.5
    ):
        """
        Initialize hybrid search.
        
        Args:
            faiss_indexer: FAISS semantic search
            bm25_search: BM25 keyword search
            alpha: Weight for semantic search (1-alpha for keyword)
        """
        self.faiss = faiss_indexer
        self.bm25 = bm25_search
        self.alpha = alpha
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        rerank: bool = True
    ) -> List[Tuple[Dict, float]]:
        """
        Hybrid search using both semantic and keyword matching.
        
        Args:
            query: Search query
            top_k: Number of results to return
            rerank: Whether to rerank combined results
            
        Returns:
            List of (metadata, combined_score) tuples
        """
        # Get results from both indices (retrieve more for reranking)
        retrieve_k = top_k * 2 if rerank else top_k
        
        faiss_results = self.faiss.search(query, top_k=retrieve_k)
        bm25_results = self.bm25.search(query, top_k=retrieve_k)
        
        # Combine results
        combined = self._fuse_results(faiss_results, bm25_results)
        
        # Rerank if requested
        if rerank:
            combined = self._rerank(combined, query)
        
        # Return top-k
        return combined[:top_k]
    
    def _fuse_results(
        self,
        faiss_results: List[Tuple[Dict, float]],
        bm25_results: List[Tuple[Dict, float]]
    ) -> List[Tuple[Dict, float]]:
        """
        Fuse results using weighted scoring.
        
        Normalize scores and combine with alpha weighting.
        """
        # Build score maps
        faiss_scores = {self._get_key(meta): score for meta, score in faiss_results}
        bm25_scores = {self._get_key(meta): score for meta, score in bm25_results}
        
        # Normalize scores
        faiss_scores = self._normalize_scores(faiss_scores)
        bm25_scores = self._normalize_scores(bm25_scores)
        
        # Combine all unique results
        all_keys = set(faiss_scores.keys()) | set(bm25_scores.keys())
        combined = []
        
        for key in all_keys:
            semantic_score = faiss_scores.get(key, 0.0)
            keyword_score = bm25_scores.get(key, 0.0)
            
            # Weighted combination
            final_score = self.alpha * semantic_score + (1 - self.alpha) * keyword_score
            
            # Get metadata (prefer FAISS if present)
            metadata = None
            for meta, _ in faiss_results:
                if self._get_key(meta) == key:
                    metadata = meta
                    break
            if metadata is None:
                for meta, _ in bm25_results:
                    if self._get_key(meta) == key:
                        metadata = meta
                        break
            
            if metadata:
                combined.append((metadata, final_score))
        
        # Sort by score
        combined.sort(key=lambda x: x[1], reverse=True)
        
        logger.debug(f"Fused {len(combined)} unique results")
        return combined
    
    def _normalize_scores(self, score_dict: Dict[str, float]) -> Dict[str, float]:
        """Min-max normalize scores to [0, 1]"""
        if not score_dict:
            return score_dict
        
        values = list(score_dict.values())
        min_score = min(values)
        max_score = max(values)
        
        if max_score == min_score:
            return {k: 1.0 for k in score_dict}
        
        return {
            k: (v - min_score) / (max_score - min_score)
            for k, v in score_dict.items()
        }
    
    def _get_key(self, metadata: Dict) -> str:
        """Generate unique key from metadata"""
        return f"{metadata.get('pdf_name')}_{metadata.get('page')}_{metadata.get('citation')}"
    
    def _rerank(
        self,
        results: List[Tuple[Dict, float]],
        query: str
    ) -> List[Tuple[Dict, float]]:
        """Optional reranking (placeholder for future enhancement)"""
        # Can add cross-encoder reranking here
        return results
```

### Implementation Details

- Retrieve 2x results from each index
- Normalize scores to [0, 1] range
- Weighted fusion: `alpha * semantic + (1-alpha) * keyword`
- Default alpha = 0.5 (equal weight)
- Remove duplicates
- Sort by combined score

### Fusion Strategies

1. **Weighted Sum**: Current implementation
2. **RRF (Reciprocal Rank Fusion)**: Alternative approach
3. **Cross-Encoder Reranking**: Future enhancement

### Tests Required (`tests/unit/test_hybrid_search.py`)

- ✅ Combine FAISS + BM25 results
- ✅ Validate score normalization
- ✅ Test different alpha values
- ✅ Verify deduplication
- ✅ Compare with single-method search

**File Size**: Target <250 lines

---

## Phase 3 Completion Checklist

### Core Modules
- [ ] `extractors/spec_graph.py` implemented
- [ ] `embeddings/embedding_model.py` implemented
- [ ] `search/faiss_indexer.py` implemented
- [ ] `search/bm25_search.py` implemented
- [ ] `search/hybrid_search.py` implemented

### Unit Tests
- [ ] Test POCT1 entity extraction
- [ ] Test embedding generation
- [ ] Test FAISS indexing and search
- [ ] Test BM25 search
- [ ] Test hybrid search fusion

### Integration Tests
- [ ] Extract entities from real POCT1 spec
- [ ] Build search index from extracted entities
- [ ] End-to-end search workflow
- [ ] Compare search quality across methods

### Verification
- [ ] All files < 300 lines
- [ ] All functions have type hints
- [ ] All public methods have docstrings
- [ ] Error handling in place
- [ ] Logging throughout
- [ ] Run tests: `pytest tests/unit/test_extractors*.py tests/unit/test_search*.py`

---

## Expected Outcome

After completing Phase 3, you will have:

✅ **POCT1 entity extraction with pattern matching**
✅ **Semantic search with FAISS (CPU-friendly)**
✅ **Keyword search with BM25**
✅ **Hybrid search combining both approaches**
✅ **All entities maintain complete provenance**
✅ **All files < 300 lines**
✅ **Ready for CLI and LLM integration** in Phase 4

---

## Next Steps

Once Phase 3 is complete, proceed to **Phase 4: CLI & LLM Integration** (see `step4.md`)
