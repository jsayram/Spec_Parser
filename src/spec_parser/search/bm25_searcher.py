"""
BM25 keyword search for exact term matching.

Complements semantic search with traditional keyword-based retrieval.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import pickle
from loguru import logger

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

from spec_parser.exceptions import ValidationError


class BM25Searcher:
    """
    BM25 keyword search index.
    
    Uses BM25Okapi algorithm for ranking:
    - Term frequency scoring
    - Inverse document frequency weighting
    - Document length normalization
    - Exact keyword matching
    """
    
    def __init__(self, index_path: Optional[Path] = None):
        """
        Initialize BM25 searcher.
        
        Args:
            index_path: Path to save/load index
        """
        if BM25Okapi is None:
            raise ValidationError(
                "rank-bm25 not installed. "
                "Install with: pip install rank-bm25"
            )
        
        self.index_path = index_path
        self.bm25: Optional[BM25Okapi] = None
        self.corpus: List[List[str]] = []  # Tokenized documents
        self.documents: List[str] = []  # Original texts
        self.metadata: List[Dict[str, Any]] = []
        
        logger.info("Created BM25 searcher")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization (split on whitespace, lowercase).
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        # Simple whitespace tokenization
        # For production, consider: nltk, spacy, or custom tokenizer
        return text.lower().split()
    
    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add texts to BM25 index.
        
        Args:
            texts: List of texts to index
            metadatas: List of metadata dicts (one per text)
        """
        if not texts:
            logger.warning("No texts to add to BM25 index")
            return
        
        if metadatas and len(metadatas) != len(texts):
            raise ValidationError(
                f"Metadata count ({len(metadatas)}) != text count ({len(texts)})"
            )
        
        # Tokenize documents
        logger.info(f"Tokenizing {len(texts)} texts for BM25...")
        tokenized = [self._tokenize(text) for text in texts]
        
        # Add to corpus
        self.corpus.extend(tokenized)
        self.documents.extend(texts)
        
        # Store metadata
        if metadatas:
            self.metadata.extend(metadatas)
        else:
            self.metadata.extend([{"text": text} for text in texts])
        
        # Rebuild BM25 index
        self.bm25 = BM25Okapi(self.corpus)
        
        logger.info(f"Added {len(texts)} texts to BM25 (total: {len(self.documents)})")
    
    def search(
        self,
        query: str,
        k: int = 10,
        filter_fn: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Search BM25 index for keyword matches.
        
        Args:
            query: Query text
            k: Number of results to return
            filter_fn: Optional filter function(metadata) -> bool
            
        Returns:
            List of results with scores and metadata
        """
        if not self.bm25 or len(self.documents) == 0:
            logger.warning("BM25 index is empty")
            return []
        
        # Tokenize query
        query_tokens = self._tokenize(query)
        
        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)
        
        # Sort by score (descending)
        sorted_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )
        
        # Build results
        results = []
        for idx in sorted_indices:
            score = scores[idx]
            
            if score <= 0:  # No match
                continue
            
            metadata = self.metadata[idx]
            
            # Apply filter
            if filter_fn and not filter_fn(metadata):
                continue
            
            result = {
                "text": self.documents[idx],
                "score": float(score),
                "metadata": metadata,
                "rank": len(results) + 1
            }
            results.append(result)
            
            if len(results) >= k:
                break
        
        logger.info(
            f"BM25 found {len(results)} results for query: '{query[:50]}...'"
        )
        
        return results
    
    def save(self, index_path: Optional[Path] = None) -> None:
        """
        Save BM25 index and metadata to disk.
        
        Args:
            index_path: Path to save index (without extension)
        """
        save_path = index_path or self.index_path
        
        if not save_path:
            raise ValidationError("No index_path specified")
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save BM25 model
        bm25_file = save_path.with_suffix(".bm25.pkl")
        with open(bm25_file, "wb") as f:
            pickle.dump(
                {
                    "bm25": self.bm25,
                    "corpus": self.corpus,
                    "documents": self.documents
                },
                f
            )
        
        # Save metadata
        metadata_file = save_path.with_suffix(".bm25_metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)
        
        logger.info(
            f"Saved BM25 index ({len(self.documents)} docs) to {bm25_file}"
        )
    
    @classmethod
    def load(cls, index_path: Path) -> "BM25Searcher":
        """
        Load BM25 index and metadata from disk.
        
        Args:
            index_path: Path to index (without extension)
            
        Returns:
            Loaded BM25Searcher
        """
        index_path = Path(index_path)
        
        # Load BM25 model
        bm25_file = index_path.with_suffix(".bm25.pkl")
        if not bm25_file.exists():
            raise ValidationError(f"BM25 index not found: {bm25_file}")
        
        with open(bm25_file, "rb") as f:
            data = pickle.load(f)
        
        # Load metadata
        metadata_file = index_path.with_suffix(".bm25_metadata.json")
        if not metadata_file.exists():
            raise ValidationError(f"Metadata not found: {metadata_file}")
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Create searcher with loaded data
        searcher = cls(index_path)
        searcher.bm25 = data["bm25"]
        searcher.corpus = data["corpus"]
        searcher.documents = data["documents"]
        searcher.metadata = metadata
        
        logger.info(
            f"Loaded BM25 index ({len(searcher.documents)} docs) from {bm25_file}"
        )
        
        return searcher
    
    @property
    def size(self) -> int:
        """Number of documents in index"""
        return len(self.documents)
