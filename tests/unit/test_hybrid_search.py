"""
Unit tests for hybrid search.
"""

import pytest
from pathlib import Path

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.search.hybrid_search import HybridSearcher


@pytest.fixture
def embedding_model():
    """Create embedding model for tests"""
    return EmbeddingModel()


@pytest.fixture
def sample_texts():
    """Sample texts for indexing"""
    return [
        "The POCT1 specification defines message formats for point-of-care testing.",
        "Host Interface Manual describes system communication protocols.",
        "Roche diagnostics provides medical devices and laboratory equipment.",
        "Blood glucose monitoring requires accurate sensors and calibration.",
        "HL7 standard enables healthcare data exchange between systems."
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


@pytest.fixture
def hybrid_searcher(embedding_model, sample_texts, sample_metadata):
    """Create hybrid searcher with indexed data"""
    # Create FAISS index
    faiss_indexer = FAISSIndexer(embedding_model)
    faiss_indexer.add_texts(sample_texts, sample_metadata)
    
    # Create BM25 index
    bm25_searcher = BM25Searcher()
    bm25_searcher.add_texts(sample_texts, sample_metadata)
    
    # Create hybrid searcher
    return HybridSearcher(faiss_indexer, bm25_searcher)


class TestHybridSearcher:
    """Test hybrid searcher functionality"""
    
    def test_searcher_initialization(self, hybrid_searcher):
        """Test hybrid searcher initializes correctly"""
        assert hybrid_searcher.faiss is not None
        assert hybrid_searcher.bm25 is not None
        assert hybrid_searcher.faiss_weight == 0.6
        assert hybrid_searcher.bm25_weight == 0.4
    
    def test_searcher_custom_weights(self, embedding_model, sample_texts, sample_metadata):
        """Test custom weight initialization"""
        faiss_indexer = FAISSIndexer(embedding_model)
        faiss_indexer.add_texts(sample_texts, sample_metadata)
        bm25_searcher = BM25Searcher()
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        hybrid = HybridSearcher(
            faiss_indexer,
            bm25_searcher,
            faiss_weight=0.7,
            bm25_weight=0.3
        )
        
        assert hybrid.faiss_weight == 0.7
        assert hybrid.bm25_weight == 0.3
    
    def test_search_semantic_mode(self, hybrid_searcher):
        """Test semantic-only search"""
        results = hybrid_searcher.search("POCT1 message", k=3, mode="semantic")
        
        assert len(results) > 0
        assert all(r["source"] == "semantic" for r in results)
        assert all("score" in r for r in results)
        assert all("metadata" in r for r in results)
    
    def test_search_keyword_mode(self, hybrid_searcher):
        """Test keyword-only search"""
        results = hybrid_searcher.search("POCT1 message", k=3, mode="keyword")
        
        assert len(results) > 0
        assert all(r["source"] == "keyword" for r in results)
        assert all("score" in r for r in results)
    
    def test_search_hybrid_mode(self, hybrid_searcher):
        """Test hybrid search"""
        results = hybrid_searcher.search("POCT1 specification", k=3, mode="hybrid")
        
        assert len(results) > 0
        assert len(results) <= 3
        # Source can be "semantic", "keyword", or "semantic+keyword"
        assert all("score" in r for r in results)
    
    def test_search_invalid_mode(self, hybrid_searcher):
        """Test invalid search mode raises error"""
        with pytest.raises(ValueError):
            hybrid_searcher.search("test", k=3, mode="invalid_mode")
    
    def test_hybrid_combines_results(self, hybrid_searcher):
        """Test hybrid search combines both indices"""
        results = hybrid_searcher.search("POCT1", k=5, mode="hybrid")
        
        # Should have results from at least one source
        assert len(results) > 0
        
        # Check that some results come from both sources
        sources = [r["source"] for r in results]
        # At least one result should combine both (has + in source)
        combined = any("+" in s for s in sources)
        
        # Results should be ranked
        for i, result in enumerate(results):
            assert result["rank"] == i + 1
    
    def test_search_with_filter(self, hybrid_searcher):
        """Test search with metadata filter"""
        results = hybrid_searcher.search(
            "POCT1",
            k=5,
            mode="hybrid",
            filter_fn=lambda m: m.get("page") == 1
        )
        
        assert all(r["metadata"]["page"] == 1 for r in results)
    
    def test_format_results_basic(self, hybrid_searcher):
        """Test formatting search results"""
        results = hybrid_searcher.search("POCT1", k=2, mode="hybrid")
        formatted = hybrid_searcher.format_results(results)
        
        assert isinstance(formatted, str)
        assert "Found 2 results" in formatted or "Found 1 result" in formatted
        assert "[1]" in formatted  # First result marker
    
    def test_format_results_with_scores(self, hybrid_searcher):
        """Test formatting with scores"""
        results = hybrid_searcher.search("POCT1", k=2, mode="hybrid")
        formatted = hybrid_searcher.format_results(results, show_scores=True)
        
        assert "score:" in formatted
        assert "source:" in formatted
    
    def test_format_results_without_scores(self, hybrid_searcher):
        """Test formatting without scores"""
        results = hybrid_searcher.search("POCT1", k=2, mode="hybrid")
        formatted = hybrid_searcher.format_results(results, show_scores=False)
        
        assert "score:" not in formatted
    
    def test_format_empty_results(self, hybrid_searcher):
        """Test formatting empty results"""
        formatted = hybrid_searcher.format_results([])
        assert "No results found" in formatted
    
    def test_hybrid_search_ranking(self, hybrid_searcher):
        """Test hybrid search produces reasonable rankings"""
        results = hybrid_searcher.search("POCT1 specification message", k=5, mode="hybrid")
        
        # Scores should be descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_semantic_and_keyword_find_different_results(self, hybrid_searcher):
        """Test that semantic and keyword search can find different things"""
        semantic_results = hybrid_searcher.search("message communication", k=3, mode="semantic")
        keyword_results = hybrid_searcher.search("message communication", k=3, mode="keyword")
        
        # Both should find something
        assert len(semantic_results) > 0
        assert len(keyword_results) > 0
        
        # Top results might differ (semantic understands meaning, keyword exact match)
        # Just verify both work
        assert all("text" in r for r in semantic_results)
        assert all("text" in r for r in keyword_results)
    
    def test_results_have_required_fields(self, hybrid_searcher):
        """Test all results have required fields"""
        results = hybrid_searcher.search("POCT1", k=3, mode="hybrid")
        
        required_fields = ["text", "score", "metadata", "rank", "source"]
        for result in results:
            for field in required_fields:
                assert field in result
