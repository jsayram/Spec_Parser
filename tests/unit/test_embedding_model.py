"""
Unit tests for embedding model.
"""

import pytest
import numpy as np
from pathlib import Path

from spec_parser.embeddings.embedding_model import EmbeddingModel


@pytest.fixture
def embedding_model():
    """Create embedding model for tests"""
    return EmbeddingModel()


class TestEmbeddingModel:
    """Test embedding model functionality"""
    
    def test_model_initialization(self, embedding_model):
        """Test model loads successfully"""
        assert embedding_model.model is not None
        assert embedding_model.embedding_dim == 384
    
    def test_embed_text_returns_vector(self, embedding_model):
        """Test embedding single text returns correct shape"""
        text = "This is a test sentence."
        embedding = embedding_model.embed_text(text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32
    
    def test_embed_empty_text(self, embedding_model):
        """Test embedding empty text returns zero vector"""
        embedding = embedding_model.embed_text("")
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)
        assert np.all(embedding == 0)
    
    def test_embed_batch_returns_matrix(self, embedding_model):
        """Test embedding multiple texts returns correct shape"""
        texts = [
            "First sentence.",
            "Second sentence.",
            "Third sentence."
        ]
        embeddings = embedding_model.embed_batch(texts)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 384)
        assert embeddings.dtype == np.float32
    
    def test_embed_batch_with_empty_texts(self, embedding_model):
        """Test embedding batch with some empty texts"""
        texts = ["Text one", "", "Text three", ""]
        embeddings = embedding_model.embed_batch(texts)
        
        assert embeddings.shape == (4, 384)
        # Empty text embeddings should be zero
        assert np.all(embeddings[1] == 0)
        assert np.all(embeddings[3] == 0)
        # Non-empty should not be zero
        assert not np.all(embeddings[0] == 0)
        assert not np.all(embeddings[2] == 0)
    
    def test_embed_batch_empty_list(self, embedding_model):
        """Test embedding empty batch"""
        embeddings = embedding_model.embed_batch([])
        
        assert embeddings.shape == (0, 384)
    
    def test_similar_texts_have_similar_embeddings(self, embedding_model):
        """Test semantic similarity works"""
        text1 = "The cat sat on the mat."
        text2 = "A cat was sitting on a mat."
        text3 = "Dogs are playing in the park."
        
        emb1 = embedding_model.embed_text(text1)
        emb2 = embedding_model.embed_text(text2)
        emb3 = embedding_model.embed_text(text3)
        
        # Cosine similarity
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        sim_1_2 = cosine_similarity(emb1, emb2)
        sim_1_3 = cosine_similarity(emb1, emb3)
        
        # Similar sentences should have higher similarity
        assert sim_1_2 > sim_1_3
        assert sim_1_2 > 0.7  # High similarity
    
    def test_chunk_text_short(self, embedding_model):
        """Test chunking text shorter than max_length"""
        text = "Short text."
        chunks = embedding_model.chunk_text(text, max_length=512)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_chunk_text_long(self, embedding_model):
        """Test chunking long text"""
        text = "A" * 1000  # 1000 characters
        chunks = embedding_model.chunk_text(text, max_length=400, overlap=50)
        
        assert len(chunks) > 1
        # Check overlap
        assert chunks[1][:50] in chunks[0]
    
    def test_chunk_text_respects_sentence_boundaries(self, embedding_model):
        """Test chunking breaks at sentence boundaries"""
        text = "First sentence. " * 100  # Long repeated text
        chunks = embedding_model.chunk_text(text, max_length=200)
        
        # Should break at sentence boundaries
        for chunk in chunks[:-1]:  # All but last
            assert chunk.strip().endswith(".")
    
    def test_embedding_dimension_property(self, embedding_model):
        """Test embedding_dim property"""
        assert embedding_model.embedding_dim == 384
        assert embedding_model.embedding_dim == embedding_model.model.get_sentence_embedding_dimension()
