"""
FAISS vector index for semantic search.

Stores embeddings with citation metadata for provenance-preserving search.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import numpy as np
from loguru import logger

try:
    import faiss
except ImportError:
    faiss = None

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.exceptions import ValidationError


class SearchResult:
    """Search result with provenance"""
    
    def __init__(
        self,
        text: str,
        score: float,
        metadata: Dict[str, Any],
        rank: int
    ):
        self.text = text
        self.score = score
        self.metadata = metadata
        self.rank = rank
    
    def __repr__(self) -> str:
        return (
            f"SearchResult(rank={self.rank}, score={self.score:.4f}, "
            f"page={self.metadata.get('page', '?')})"
        )


class FAISSIndexer:
    """
    FAISS vector index with metadata storage.
    
    Features:
    - Flat L2 distance index (exact search)
    - Metadata storage (citations, provenance)
    - Save/load functionality
    - CPU-only (no GPU required)
    """
    
    def __init__(
        self,
        embedding_model: EmbeddingModel,
        index_path: Optional[Path] = None
    ):
        """
        Initialize FAISS indexer.
        
        Args:
            embedding_model: Embedding model for vectorization
            index_path: Path to save/load index
        """
        if faiss is None:
            raise ValidationError(
                "faiss-cpu not installed. "
                "Install with: pip install faiss-cpu"
            )
        
        self.embedding_model = embedding_model
        self.index_path = index_path
        
        # Create flat L2 index (exact search)
        dim = embedding_model.embedding_dim
        self.index = faiss.IndexFlatL2(dim)
        
        # Metadata storage (index_id -> metadata dict)
        self.metadata: List[Dict[str, Any]] = []
        
        logger.info(f"Created FAISS index ({dim} dimensions)")
    
    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add texts to index.
        
        Args:
            texts: List of texts to index
            metadatas: List of metadata dicts (one per text)
        """
        if not texts:
            logger.warning("No texts to add to index")
            return
        
        if metadatas and len(metadatas) != len(texts):
            raise ValidationError(
                f"Metadata count ({len(metadatas)}) != text count ({len(texts)})"
            )
        
        # Generate embeddings
        logger.info(f"Embedding {len(texts)} texts...")
        embeddings = self.embedding_model.embed_batch(
            texts,
            show_progress=len(texts) > 100
        )
        
        # Add to FAISS index
        self.index.add(embeddings)
        
        # Store metadata
        if metadatas:
            self.metadata.extend(metadatas)
        else:
            # Create default metadata
            self.metadata.extend([{"text": text} for text in texts])
        
        logger.info(
            f"Added {len(texts)} texts to index "
            f"(total: {self.index.ntotal})"
        )
    
    def search(
        self,
        query: str,
        k: int = 10,
        filter_fn: Optional[callable] = None
    ) -> List[SearchResult]:
        """
        Search index for similar texts.
        
        Args:
            query: Query text
            k: Number of results to return
            filter_fn: Optional filter function(metadata) -> bool
            
        Returns:
            List of SearchResult objects with provenance
        """
        if self.index.ntotal == 0:
            logger.warning("Index is empty")
            return []
        
        # Embed query
        query_embedding = self.embedding_model.embed_text(query)
        query_embedding = query_embedding.reshape(1, -1)
        
        # Search FAISS index
        # Request more results if filtering
        search_k = k * 5 if filter_fn else k
        search_k = min(search_k, self.index.ntotal)
        
        distances, indices = self.index.search(query_embedding, search_k)
        
        # Build results with metadata
        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:  # No more results
                break
            
            metadata = self.metadata[idx]
            
            # Apply filter
            if filter_fn and not filter_fn(metadata):
                continue
            
            # Convert L2 distance to similarity score (0-1)
            # Lower distance = higher similarity
            score = 1.0 / (1.0 + dist)
            
            result = SearchResult(
                text=metadata.get("text", ""),
                score=score,
                metadata=metadata,
                rank=len(results) + 1
            )
            results.append(result)
            
            if len(results) >= k:
                break
        
        logger.info(
            f"Found {len(results)} results for query: '{query[:50]}...'"
        )
        
        return results
    
    def save(self, index_path: Optional[Path] = None) -> None:
        """
        Save index and metadata to disk.
        
        Args:
            index_path: Path to save index (without extension)
        """
        save_path = index_path or self.index_path
        
        if not save_path:
            raise ValidationError("No index_path specified")
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        index_file = save_path.with_suffix(".faiss")
        faiss.write_index(self.index, str(index_file))
        
        # Save metadata
        metadata_file = save_path.with_suffix(".metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)
        
        logger.info(
            f"Saved FAISS index ({self.index.ntotal} vectors) to {index_file}"
        )
    
    @classmethod
    def load(
        cls,
        index_path: Path,
        embedding_model: EmbeddingModel
    ) -> "FAISSIndexer":
        """
        Load index and metadata from disk.
        
        Args:
            index_path: Path to index (without extension)
            embedding_model: Embedding model for queries
            
        Returns:
            Loaded FAISSIndexer
        """
        index_path = Path(index_path)
        
        # Load FAISS index
        index_file = index_path.with_suffix(".faiss")
        if not index_file.exists():
            raise ValidationError(f"Index not found: {index_file}")
        
        loaded_index = faiss.read_index(str(index_file))
        
        # Load metadata
        metadata_file = index_path.with_suffix(".metadata.json")
        if not metadata_file.exists():
            raise ValidationError(f"Metadata not found: {metadata_file}")
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Create indexer with loaded data
        indexer = cls(embedding_model, index_path)
        indexer.index = loaded_index
        indexer.metadata = metadata
        
        logger.info(
            f"Loaded FAISS index ({loaded_index.ntotal} vectors) from {index_file}"
        )
        
        return indexer
    
    @property
    def size(self) -> int:
        """Number of vectors in index"""
        return self.index.ntotal
