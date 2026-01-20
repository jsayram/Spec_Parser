"""
Tests for parallel page processing in PyMuPDFExtractor.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.schemas.page_bundle import PageBundle


class TestParallelExtraction:
    """Tests for parallel page extraction."""
    
    @pytest.fixture
    def mock_pdf_path(self, tmp_path):
        """Create a mock PDF path."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        return pdf_path
    
    @pytest.fixture
    def mock_extractor(self, mock_pdf_path):
        """Create a mock extractor with mocked internals."""
        with patch('pymupdf.open') as mock_open:
            mock_doc = MagicMock()
            mock_doc.__len__ = Mock(return_value=10)
            mock_doc.__getitem__ = Mock(return_value=MagicMock())
            mock_open.return_value.__enter__ = Mock(return_value=mock_doc)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            
            extractor = PyMuPDFExtractor(mock_pdf_path)
            extractor.doc = mock_doc
            
            yield extractor
    
    def test_extract_all_pages_default_parallel(self, mock_extractor):
        """Test that parallel extraction is enabled by default."""
        # Mock extract_page to return dummy bundles
        mock_bundle = Mock(spec=PageBundle)
        mock_bundle.page_number = 1
        mock_extractor.extract_page = Mock(return_value=mock_bundle)
        
        with patch.object(mock_extractor, '_extract_pages_parallel') as mock_parallel:
            mock_parallel.return_value = ([mock_bundle], [])
            
            bundles = mock_extractor.extract_all_pages(max_pages=5)
            
            # Should use parallel extraction by default
            mock_parallel.assert_called_once()
    
    def test_extract_all_pages_sequential_mode(self, mock_extractor):
        """Test sequential extraction when parallel=False."""
        mock_bundle = Mock(spec=PageBundle)
        mock_bundle.page_number = 1
        mock_extractor.extract_page = Mock(return_value=mock_bundle)
        
        with patch.object(mock_extractor, '_extract_pages_sequential') as mock_seq:
            mock_seq.return_value = ([mock_bundle], [])
            
            bundles = mock_extractor.extract_all_pages(max_pages=5, parallel=False)
            
            mock_seq.assert_called_once()
    
    def test_extract_all_pages_single_page_uses_sequential(self, mock_extractor):
        """Test that single page extraction uses sequential mode."""
        mock_bundle = Mock(spec=PageBundle)
        mock_bundle.page_number = 1
        mock_extractor.extract_page = Mock(return_value=mock_bundle)
        
        with patch.object(mock_extractor, '_extract_pages_sequential') as mock_seq:
            mock_seq.return_value = ([mock_bundle], [])
            
            # Only 1 page - should use sequential
            bundles = mock_extractor.extract_all_pages(max_pages=1)
            
            mock_seq.assert_called_once()
    
    def test_extract_all_pages_max_workers(self, mock_extractor):
        """Test max_workers parameter is passed correctly."""
        mock_bundle = Mock(spec=PageBundle)
        mock_bundle.page_number = 1
        
        with patch.object(mock_extractor, '_extract_pages_parallel') as mock_parallel:
            mock_parallel.return_value = ([mock_bundle], [])
            
            mock_extractor.extract_all_pages(max_pages=5, max_workers=8)
            
            # Check max_workers was passed
            call_args = mock_parallel.call_args
            assert call_args[0][1] == 8  # max_workers is second positional arg
    
    def test_bundles_sorted_by_page_number(self, mock_extractor):
        """Test that bundles are sorted by page number after parallel extraction."""
        # Create bundles out of order (as might happen with parallel)
        bundle1 = Mock(spec=PageBundle)
        bundle1.page_number = 1
        bundle3 = Mock(spec=PageBundle)
        bundle3.page_number = 3
        bundle2 = Mock(spec=PageBundle)
        bundle2.page_number = 2
        
        with patch.object(mock_extractor, '_extract_pages_parallel') as mock_parallel:
            # Return bundles out of order
            mock_parallel.return_value = ([bundle3, bundle1, bundle2], [])
            
            bundles = mock_extractor.extract_all_pages(max_pages=3)
            
            # Should be sorted
            assert bundles[0].page_number == 1
            assert bundles[1].page_number == 2
            assert bundles[2].page_number == 3
    
    def test_failed_pages_tracked(self, mock_extractor):
        """Test that failed pages are tracked and logged."""
        mock_bundle = Mock(spec=PageBundle)
        mock_bundle.page_number = 1
        
        with patch.object(mock_extractor, '_extract_pages_parallel') as mock_parallel:
            # Simulate some failed pages
            mock_parallel.return_value = ([mock_bundle], [2, 4, 5])
            
            with patch('spec_parser.parsers.pymupdf_extractor.logger') as mock_logger:
                bundles = mock_extractor.extract_all_pages(max_pages=5)
                
                # Should log warning about failed pages
                mock_logger.warning.assert_called()
    
    def test_progress_callback(self, mock_extractor):
        """Test progress callback is called."""
        mock_bundle = Mock(spec=PageBundle)
        mock_bundle.page_number = 1
        
        progress_calls = []
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        with patch.object(mock_extractor, '_extract_pages_sequential') as mock_seq:
            mock_seq.return_value = ([mock_bundle], [])
            
            mock_extractor.extract_all_pages(
                max_pages=1, 
                parallel=False,
                progress_callback=progress_callback
            )
            
            # Callback should be passed to sequential method
            call_args = mock_seq.call_args
            assert call_args[0][1] == progress_callback


class TestExtractPageSafe:
    """Tests for thread-safe page extraction wrapper."""
    
    @pytest.fixture
    def extractor_with_mock(self, tmp_path):
        """Create extractor with mocked extract_page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        with patch('pymupdf.open') as mock_open:
            mock_doc = MagicMock()
            mock_doc.__len__ = Mock(return_value=10)
            mock_open.return_value.__enter__ = Mock(return_value=mock_doc)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            
            extractor = PyMuPDFExtractor(pdf_path)
            extractor.doc = mock_doc
            
            yield extractor
    
    def test_extract_page_safe_success(self, extractor_with_mock):
        """Test _extract_page_safe returns bundle on success."""
        mock_bundle = Mock(spec=PageBundle)
        extractor_with_mock.extract_page = Mock(return_value=mock_bundle)
        
        result = extractor_with_mock._extract_page_safe(1)
        
        assert result == mock_bundle
    
    def test_extract_page_safe_failure(self, extractor_with_mock):
        """Test _extract_page_safe returns None on failure."""
        extractor_with_mock.extract_page = Mock(side_effect=Exception("Test error"))
        
        result = extractor_with_mock._extract_page_safe(1)
        
        assert result is None


class TestSequentialExtraction:
    """Tests for sequential page extraction."""
    
    @pytest.fixture
    def extractor(self, tmp_path):
        """Create extractor for testing."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        with patch('pymupdf.open') as mock_open:
            mock_doc = MagicMock()
            mock_doc.__len__ = Mock(return_value=5)
            mock_open.return_value.__enter__ = Mock(return_value=mock_doc)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            
            extractor = PyMuPDFExtractor(pdf_path)
            extractor.doc = mock_doc
            
            yield extractor
    
    def test_sequential_extracts_all_pages(self, extractor):
        """Test sequential extraction processes all pages."""
        bundles = []
        for i in range(1, 4):
            b = Mock(spec=PageBundle)
            b.page_number = i
            bundles.append(b)
        
        extractor.extract_page = Mock(side_effect=bundles)
        
        result, failed = extractor._extract_pages_sequential([1, 2, 3])
        
        assert len(result) == 3
        assert len(failed) == 0
    
    def test_sequential_continues_on_error(self, extractor):
        """Test sequential extraction continues after error."""
        bundle1 = Mock(spec=PageBundle)
        bundle1.page_number = 1
        bundle3 = Mock(spec=PageBundle)
        bundle3.page_number = 3
        
        # Page 2 fails
        extractor.extract_page = Mock(side_effect=[
            bundle1,
            Exception("Page 2 failed"),
            bundle3
        ])
        
        result, failed = extractor._extract_pages_sequential([1, 2, 3])
        
        assert len(result) == 2
        assert failed == [2]
