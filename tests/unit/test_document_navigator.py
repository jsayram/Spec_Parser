"""
Unit tests for RLM DocumentNavigator.
"""

import pytest

from spec_parser.rlm.document_navigator import DocumentNavigator
from spec_parser.schemas.rlm_models import SearchResult, DocumentSpan
from spec_parser.exceptions import RLMError


class TestDocumentNavigator:
    """Test RLM DocumentNavigator"""
    
    def test_navigator_initialization(self, document_navigator):
        """Test navigator initializes correctly"""
        assert len(document_navigator.pages) == 2
        assert 1 in document_navigator.pages
        assert 2 in document_navigator.pages
    
    def test_search_regex_finds_matches(self, document_navigator):
        """Test search with regex finds matches"""
        result = document_navigator.search(r"OBS\.R01", method="regex")
        
        assert isinstance(result, SearchResult)
        assert result.method == "regex"
        assert result.total_results > 0
        assert len(result.spans) > 0
        assert all(isinstance(span, DocumentSpan) for span in result.spans)
    
    def test_search_keyword_finds_matches(self, document_navigator):
        """Test keyword search finds matches"""
        result = document_navigator.search("POCT1", method="keyword")
        
        assert result.total_results > 0
        assert len(result.spans) > 0
        assert "POCT1" in result.spans[0].text
    
    def test_search_case_insensitive(self, document_navigator):
        """Test search is case-insensitive"""
        result = document_navigator.search("poct1", method="keyword")
        
        assert result.total_results > 0
    
    def test_search_no_matches(self, document_navigator):
        """Test search with no matches"""
        result = document_navigator.search("nonexistent_pattern", method="keyword")
        
        assert result.total_results == 0
        assert len(result.spans) == 0
    
    def test_get_span_valid(self, document_navigator):
        """Test get_span with valid parameters"""
        span = document_navigator.get_span(page=1, start=0, end=20)
        
        assert isinstance(span, DocumentSpan)
        assert span.page == 1
        assert span.start == 0
        assert span.end == 20
        assert len(span.text) == 20
    
    def test_get_span_invalid_page(self, document_navigator):
        """Test get_span with invalid page"""
        with pytest.raises(RLMError):
            document_navigator.get_span(page=999, start=0, end=10)
    
    def test_get_span_exceeds_length(self, document_navigator):
        """Test get_span with end exceeding page length"""
        with pytest.raises(RLMError):
            document_navigator.get_span(page=1, start=0, end=999999)
    
    def test_neighbors_returns_context(self, document_navigator):
        """Test neighbors returns context window"""
        context = document_navigator.neighbors(page=1, position=50)
        
        assert context.target_page == 1
        assert context.target_position == 50
        assert len(context.before) > 0
        assert len(context.after) > 0
    
    def test_neighbors_invalid_page(self, document_navigator):
        """Test neighbors with invalid page"""
        with pytest.raises(RLMError):
            document_navigator.neighbors(page=999, position=0)
    
    def test_list_headings_all(self, document_navigator):
        """Test listing all headings"""
        headings = document_navigator.list_headings()
        
        assert len(headings) > 0
        assert any("POCT1" in h.text for h in headings)
        assert any("Overview" in h.text for h in headings)
    
    def test_list_headings_by_page(self, document_navigator):
        """Test listing headings for specific page"""
        headings = document_navigator.list_headings(page=1)
        
        assert all(h.page == 1 for h in headings)
    
    def test_toc_map_returns_toc(self, document_navigator):
        """Test toc_map returns table of contents"""
        toc = document_navigator.toc_map()
        
        assert len(toc) > 0
        assert all(hasattr(entry, 'heading') for entry in toc)
        assert all(hasattr(entry, 'page') for entry in toc)
    
    def test_find_section_matches(self, document_navigator):
        """Test find_section finds matching sections"""
        sections = document_navigator.find_section("OBS")
        
        assert len(sections) > 0
        assert any("OBS" in s.text for s in sections)
    
    def test_find_section_case_insensitive(self, document_navigator):
        """Test find_section is case-insensitive"""
        sections = document_navigator.find_section("obs")
        
        assert len(sections) > 0
    
    def test_find_section_no_matches(self, document_navigator):
        """Test find_section with no matches"""
        sections = document_navigator.find_section("nonexistent")
        
        assert len(sections) == 0
    
    def test_get_page_bundle_valid(self, document_navigator):
        """Test get_page_bundle returns correct bundle"""
        bundle = document_navigator.get_page_bundle(1)
        
        assert bundle is not None
        assert bundle.page == 1
    
    def test_get_page_bundle_invalid(self, document_navigator):
        """Test get_page_bundle with invalid page"""
        bundle = document_navigator.get_page_bundle(999)
        
        assert bundle is None
    
    def test_search_result_top_k(self, document_navigator):
        """Test SearchResult top_k method"""
        result = document_navigator.search("message", method="keyword")
        
        if result.total_results > 2:
            top_results = result.top_k(2)
            assert len(top_results) == 2
    
    def test_search_result_by_page(self, document_navigator):
        """Test SearchResult by_page grouping"""
        result = document_navigator.search("POCT1", method="keyword")
        
        by_page = result.by_page()
        assert isinstance(by_page, dict)
        assert all(isinstance(page_num, int) for page_num in by_page.keys())
