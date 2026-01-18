"""
Unit tests for PyMuPDFExtractor.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pymupdf

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.schemas.page_bundle import PageBundle
from spec_parser.exceptions import PDFExtractionError


class TestPyMuPDFExtractor:
    """Test PyMuPDFExtractor"""

    def test_extractor_initialization_with_invalid_pdf(self):
        """Test that initializing with non-existent PDF raises error"""
        with pytest.raises(PDFExtractionError, match="PDF not found"):
            PyMuPDFExtractor(Path("/nonexistent/file.pdf"))

    def test_extractor_context_manager(self, tmp_path):
        """Test context manager opens and closes PDF"""
        # Create a minimal PDF for testing
        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        doc.save(str(pdf_path))
        doc.close()

        # Test context manager
        with PyMuPDFExtractor(pdf_path) as extractor:
            assert extractor.doc is not None
            assert extractor.pdf_name == "test"

    def test_extract_page_without_context_manager(self, tmp_path):
        """Test extracting page without context manager raises error"""
        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.save(str(pdf_path))
        doc.close()

        extractor = PyMuPDFExtractor(pdf_path)
        with pytest.raises(PDFExtractionError, match="PDF not opened"):
            extractor.extract_page(1)

    def test_extract_page_invalid_page_number(self, tmp_path):
        """Test extracting invalid page number raises error"""
        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.save(str(pdf_path))
        doc.close()

        with PyMuPDFExtractor(pdf_path) as extractor:
            with pytest.raises(PDFExtractionError, match="Invalid page number"):
                extractor.extract_page(0)

            with pytest.raises(PDFExtractionError, match="Invalid page number"):
                extractor.extract_page(999)

    def test_generate_citation(self, tmp_path):
        """Test citation generation"""
        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.save(str(pdf_path))
        doc.close()

        with PyMuPDFExtractor(pdf_path) as extractor:
            # Test text citation
            citation = extractor._generate_citation(1, "text", 0, (0, 0, 100, 100))
            assert citation.citation_id == "p1_txt1"
            assert citation.page == 1
            assert citation.source == "text"

            # Test image citation
            citation = extractor._generate_citation(2, "picture", 5, (0, 0, 100, 100))
            assert citation.citation_id == "p2_img6"
            assert citation.page == 2
            assert citation.source == "graphics"

            # Test table citation
            citation = extractor._generate_citation(3, "table", 2, (0, 0, 100, 100))
            assert citation.citation_id == "p3_tbl3"
            assert citation.source == "text"

            # Test graphics citation
            citation = extractor._generate_citation(4, "graphics", 1, (0, 0, 100, 100))
            assert citation.citation_id == "p4_gfx2"
            assert citation.source == "graphics"
