"""
Unit tests for FAISS indexer.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer


@pytest.fixture
def embedding_model():
    """Create embedding model for tests"""
    return EmbeddingModel()


@pytest.fixture
def faiss_indexer(embedding_model):
    """Create FAISS indexer for tests"""
    return FAISSIndexer(embedding_model)


@pytest.fixture
def sample_texts():
    """Sample texts for indexing"""
    return [
        "The POCT1 specification defines message formats.",
        "Host Interface Manual describes system communication.",
        "Roche diagnostics provides medical devices.",
        "Blood glucose monitoring requires accurate sensors.",
        "HL7 standard enables healthcare data exchange."
    ]


@pytest.fixture
def sample_metadata():
    """Sample metadata for texts"""
    return [
        {"page": 1, "citation": "p1_txt1", "type": "text"},
        {"page": 2, "citation": "p2_txt1", "type": "text"},
        {"page": 3, "citation": "p3_txt1", "type": "text"},
        {"page": 4, "citation": "p4_txt1", "type": "text"},
        {"page": 5, "citation": "p5_txt1", "type": "text"},
    ]


class TestFAISSIndexer:
    """Test FAISS indexer functionality"""
    
    def test_indexer_initialization(self, faiss_indexer):
        """Test indexer initializes correctly"""
        assert faiss_indexer.index is not None
        assert faiss_indexer.size == 0
        assert len(faiss_indexer.metadata) == 0
    
    def test_add_texts_increases_size(self, faiss_indexer, sample_texts, sample_metadata):
        """Test adding texts increases index size"""
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        
        assert faiss_indexer.size == 5
        assert len(faiss_indexer.metadata) == 5
    
    def test_add_texts_without_metadata(self, faiss_indexer, sample_texts):
        """Test adding texts without metadata creates default metadata"""
        faiss_indexer.add_texts(sample_texts)
        
        assert faiss_indexer.size == 5
        assert len(faiss_indexer.metadata) == 5
        assert "text" in faiss_indexer.metadata[0]
    
    def test_add_empty_texts(self, faiss_indexer):
        """Test adding empty list does nothing"""
        faiss_indexer.add_texts([])
        assert faiss_indexer.size == 0
    
    def test_search_returns_results(self, faiss_indexer, sample_texts, sample_metadata):
        """Test search returns relevant results"""
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        
        results = faiss_indexer.search("POCT1 message format", k=3)
        
        assert len(results) > 0
        assert len(results) <= 3
        assert all(hasattr(r, "text") for r in results)
        assert all(hasattr(r, "score") for r in results)
        assert all(hasattr(r, "metadata") for r in results)
    
    def test_search_empty_index(self, faiss_indexer):
        """Test searching empty index returns empty list"""
        results = faiss_indexer.search("test query", k=5)
        assert len(results) == 0
    
    def test_search_ranks_results(self, faiss_indexer, sample_texts, sample_metadata):
        """Test search results are ranked"""
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        
        results = faiss_indexer.search("POCT1 specification", k=5)
        
        # Check ranks are sequential
        for i, result in enumerate(results):
            assert result.rank == i + 1
    
    def test_search_with_filter(self, faiss_indexer, sample_texts, sample_metadata):
        """Test search with metadata filter"""
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        
        # Filter to only page 1
        results = faiss_indexer.search(
            "POCT1",
            k=5,
            filter_fn=lambda m: m.get("page") == 1
        )
        
        assert all(r.metadata["page"] == 1 for r in results)
    
    def test_search_top_result_is_most_relevant(self, faiss_indexer, sample_texts, sample_metadata):
        """Test top result has highest score"""
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        
        results = faiss_indexer.search("POCT1 specification message", k=3)
        
        assert len(results) > 1
        # Scores should be descending
        assert results[0].score >= results[1].score
    
    def test_save_and_load(self, faiss_indexer, sample_texts, sample_metadata, tmp_path):
        """Test saving and loading index"""
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        
        # Save
        index_path = tmp_path / "test_index"
        faiss_indexer.save(index_path)
        
        # Check files exist
        assert (tmp_path / "test_index.faiss").exists()
        assert (tmp_path / "test_index.metadata.json").exists()
        
        # Load
        loaded_indexer = FAISSIndexer.load(
            index_path,
            faiss_indexer.embedding_model
        )
        
        assert loaded_indexer.size == 5
        assert len(loaded_indexer.metadata) == 5
        
        # Search should work the same
        original_results = faiss_indexer.search("POCT1", k=3)
        loaded_results = loaded_indexer.search("POCT1", k=3)
        
        assert len(original_results) == len(loaded_results)
        # Scores should be very close (floating point precision)
        for orig, loaded in zip(original_results, loaded_results):
            assert abs(orig.score - loaded.score) < 0.001
    
    def test_metadata_preserved(self, faiss_indexer, sample_texts, sample_metadata):
        """Test metadata is preserved correctly"""
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        
        results = faiss_indexer.search("POCT1", k=1)
        
        result = results[0]
        assert "page" in result.metadata
        assert "citation" in result.metadata
        assert "type" in result.metadata
    
    def test_size_property(self, faiss_indexer, sample_texts):
        """Test size property works"""
        assert faiss_indexer.size == 0
        
        faiss_indexer.add_texts(sample_texts[:3])
        assert faiss_indexer.size == 3
        
        faiss_indexer.add_texts(sample_texts[3:])
        assert faiss_indexer.size == 5
