"""
Unit tests for BM25 searcher.
"""

import pytest
from pathlib import Path

from spec_parser.search.bm25_searcher import BM25Searcher


@pytest.fixture
def bm25_searcher():
    """Create BM25 searcher for tests"""
    return BM25Searcher()


@pytest.fixture
def sample_texts():
    """Sample texts for indexing"""
    return [
        "The POCT1 specification defines message formats for point-of-care testing.",
        "Host Interface Manual describes system communication protocols.",
        "Roche diagnostics provides medical devices and laboratory equipment.",
        "Blood glucose monitoring requires accurate sensors and calibration.",
        "POCT1 standard enables point-of-care testing device data exchange between systems."
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


class TestBM25Searcher:
    """Test BM25 searcher functionality"""
    
    def test_searcher_initialization(self, bm25_searcher):
        """Test searcher initializes correctly"""
        assert bm25_searcher.bm25 is None
        assert bm25_searcher.size == 0
        assert len(bm25_searcher.documents) == 0
    
    def test_tokenize_basic(self, bm25_searcher):
        """Test tokenization splits words"""
        tokens = bm25_searcher._tokenize("Hello World Test")
        assert tokens == ["hello", "world", "test"]
    
    def test_tokenize_lowercase(self, bm25_searcher):
        """Test tokenization lowercases"""
        tokens = bm25_searcher._tokenize("UPPERCASE lowercase MiXeD")
        assert all(t.islower() for t in tokens)
    
    def test_add_texts_increases_size(self, bm25_searcher, sample_texts, sample_metadata):
        """Test adding texts increases index size"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        assert bm25_searcher.size == 5
        assert len(bm25_searcher.documents) == 5
        assert len(bm25_searcher.metadata) == 5
        assert bm25_searcher.bm25 is not None
    
    def test_add_texts_without_metadata(self, bm25_searcher, sample_texts):
        """Test adding texts without metadata creates default metadata"""
        bm25_searcher.add_texts(sample_texts)
        
        assert bm25_searcher.size == 5
        assert "text" in bm25_searcher.metadata[0]
    
    def test_add_empty_texts(self, bm25_searcher):
        """Test adding empty list does nothing"""
        bm25_searcher.add_texts([])
        assert bm25_searcher.size == 0
    
    def test_search_returns_results(self, bm25_searcher, sample_texts, sample_metadata):
        """Test search returns relevant results"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        results = bm25_searcher.search("POCT1 message", k=3)
        
        assert len(results) > 0
        assert len(results) <= 3
        assert all("text" in r for r in results)
        assert all("score" in r for r in results)
        assert all("metadata" in r for r in results)
    
    def test_search_empty_index(self, bm25_searcher):
        """Test searching empty index returns empty list"""
        results = bm25_searcher.search("test query", k=5)
        assert len(results) == 0
    
    def test_search_ranks_results(self, bm25_searcher, sample_texts, sample_metadata):
        """Test search results are ranked"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        results = bm25_searcher.search("POCT1 specification", k=5)
        
        # Check ranks are sequential
        for i, result in enumerate(results):
            assert result["rank"] == i + 1
    
    def test_search_keyword_matching(self, bm25_searcher, sample_texts, sample_metadata):
        """Test keyword matching works"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        # Search for exact keyword
        results = bm25_searcher.search("POCT1", k=5)
        
        # Should find document with POCT1
        assert len(results) > 0
        assert "POCT1" in results[0]["text"]
    
    def test_search_multiple_keywords(self, bm25_searcher, sample_texts, sample_metadata):
        """Test searching with multiple keywords"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        results = bm25_searcher.search("specification message format", k=3)
        
        assert len(results) > 0
        # Top result should contain multiple query terms
        assert any(word in results[0]["text"].lower() for word in ["specification", "message", "format"])
    
    def test_search_with_filter(self, bm25_searcher, sample_texts, sample_metadata):
        """Test search with metadata filter"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        # Filter to only page 1
        results = bm25_searcher.search(
            "POCT1",
            k=5,
            filter_fn=lambda m: m.get("page") == 1
        )
        
        assert all(r["metadata"]["page"] == 1 for r in results)
    
    def test_search_no_matches(self, bm25_searcher, sample_texts, sample_metadata):
        """Test search with no matching keywords"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        # Search for term not in corpus
        results = bm25_searcher.search("xyzabc123notfound", k=5)
        
        assert len(results) == 0
    
    def test_save_and_load(self, bm25_searcher, sample_texts, sample_metadata, tmp_path):
        """Test saving and loading index"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        # Save
        index_path = tmp_path / "test_bm25"
        bm25_searcher.save(index_path)
        
        # Check files exist
        assert (tmp_path / "test_bm25.bm25.pkl").exists()
        assert (tmp_path / "test_bm25.bm25_metadata.json").exists()
        
        # Load
        loaded_searcher = BM25Searcher.load(index_path)
        
        assert loaded_searcher.size == 5
        assert len(loaded_searcher.metadata) == 5
        assert loaded_searcher.bm25 is not None
        
        # Search should work the same
        original_results = bm25_searcher.search("POCT1", k=3)
        loaded_results = loaded_searcher.search("POCT1", k=3)
        
        assert len(original_results) == len(loaded_results)
        # Scores should match
        for orig, loaded in zip(original_results, loaded_results):
            assert orig["score"] == loaded["score"]
    
    def test_metadata_preserved(self, bm25_searcher, sample_texts, sample_metadata):
        """Test metadata is preserved correctly"""
        bm25_searcher.add_texts(sample_texts, sample_metadata)
        
        results = bm25_searcher.search("POCT1", k=1)
        
        result = results[0]
        assert "page" in result["metadata"]
        assert "citation" in result["metadata"]
        assert "type" in result["metadata"]
    
    def test_size_property(self, bm25_searcher, sample_texts):
        """Test size property works"""
        assert bm25_searcher.size == 0
        
        bm25_searcher.add_texts(sample_texts[:3])
        assert bm25_searcher.size == 3
        
        bm25_searcher.add_texts(sample_texts[3:])
        assert bm25_searcher.size == 5  # Total: 3 + 2
