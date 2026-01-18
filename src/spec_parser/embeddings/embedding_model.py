"""
Embedding model manager for semantic search.

Uses sentence-transformers with all-MiniLM-L6-v2 (CPU-only, lightweight).
"""

from pathlib import Path
from typing import List, Optional
import numpy as np
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from spec_parser.exceptions import ValidationError


class EmbeddingModel:
    """
    Manages text embedding for semantic search.
    
    Uses all-MiniLM-L6-v2:
    - 384 dimensions
    - CPU-only (no GPU required)
    - 22MB model size
    - Fast inference
    - Good quality for general text
    """
    
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        cache_dir: Optional[Path] = None
    ):
        """
        Initialize embedding model.
        
        Args:
            model_name: HuggingFace model identifier
            cache_dir: Directory to cache downloaded models
        """
        if SentenceTransformer is None:
            raise ValidationError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self.cache_dir = cache_dir
        
        logger.info(f"Loading embedding model: {model_name}")
        try:
            self.model = SentenceTransformer(
                model_name,
                cache_folder=str(cache_dir) if cache_dir else None
            )
            logger.info(
                f"Model loaded: {model_name} "
                f"({self.model.get_sentence_embedding_dimension()} dimensions)"
            )
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise ValidationError(f"Could not load model {model_name}: {e}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Embed single text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (numpy array)
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            dim = self.model.get_sentence_embedding_dimension()
            return np.zeros(dim, dtype=np.float32)
        
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        
        return embedding
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Embed batch of texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for encoding
            show_progress: Show progress bar
            
        Returns:
            Matrix of embeddings (n_texts, embedding_dim)
        """
        if not texts:
            dim = self.model.get_sentence_embedding_dimension()
            return np.zeros((0, dim), dtype=np.float32)
        
        # Filter empty texts, track indices
        non_empty_texts = []
        non_empty_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_texts.append(text)
                non_empty_indices.append(i)
        
        if not non_empty_texts:
            # All texts empty
            dim = self.model.get_sentence_embedding_dimension()
            return np.zeros((len(texts), dim), dtype=np.float32)
        
        # Embed non-empty texts
        embeddings = self.model.encode(
            non_empty_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=show_progress
        )
        
        # Create result array with zeros for empty texts
        dim = embeddings.shape[1]
        result = np.zeros((len(texts), dim), dtype=np.float32)
        for i, embedding in zip(non_empty_indices, embeddings):
            result[i] = embedding
        
        return result
    
    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension"""
        return self.model.get_sentence_embedding_dimension()
    
    def chunk_text(
        self,
        text: str,
        max_length: int = 512,
        overlap: int = 50
    ) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            max_length: Maximum chunk length (characters)
            overlap: Overlap between chunks (characters)
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_length
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending punctuation
                for punct in ['. ', '.\n', '! ', '?\n']:
                    last_punct = text[start:end].rfind(punct)
                    if last_punct > max_length // 2:  # At least halfway through
                        end = start + last_punct + len(punct)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start with overlap
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks
