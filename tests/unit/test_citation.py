"""
Unit tests for Citation model.
"""

import pytest
from pydantic import ValidationError

from spec_parser.schemas.citation import Citation


class TestCitation:
    """Test Citation model"""
    
    def test_citation_creation(self, sample_citation):
        """Test creating a valid citation"""
        assert sample_citation.citation_id == "p1_txt1"
        assert sample_citation.page == 1
        assert sample_citation.source == "text"
        assert sample_citation.content_type == "text"
    
    def test_citation_bbox_validation_invalid(self):
        """Test bbox validation with invalid bbox"""
        with pytest.raises(ValidationError):
            Citation(
                citation_id="p1_txt1",
                page=1,
                bbox=(500.0, 200.0, 100.0, 300.0),  # Invalid: x1 < x0
                source="text",
                content_type="text"
            )
    
    def test_citation_bbox_validation_invalid_y(self):
        """Test bbox validation with invalid y coordinates"""
        with pytest.raises(ValidationError):
            Citation(
                citation_id="p1_txt1",
                page=1,
                bbox=(100.0, 300.0, 500.0, 200.0),  # Invalid: y1 < y0
                source="text",
                content_type="text"
            )
    
    def test_citation_invalid_source(self):
        """Test invalid source type"""
        with pytest.raises(ValidationError):
            Citation(
                citation_id="p1_txt1",
                page=1,
                bbox=(100.0, 200.0, 500.0, 300.0),
                source="invalid",  # Invalid source
                content_type="text"
            )
    
    def test_citation_to_markdown_footnote(self, sample_citation):
        """Test markdown footnote generation"""
        footnote = sample_citation.to_markdown_footnote()
        
        assert "[^p1_txt1]:" in footnote
        assert "Page 1" in footnote
        assert "bbox [100.0, 200.0, 500.0, 300.0]" in footnote
        assert "source: text" in footnote
    
    def test_citation_with_confidence(self):
        """Test citation with OCR confidence"""
        citation = Citation(
            citation_id="p1_ocr1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="ocr",
            content_type="picture",
            confidence=0.87
        )
        
        footnote = citation.to_markdown_footnote()
        assert "confidence: 0.87" in footnote
    
    def test_citation_with_file_reference(self):
        """Test citation with file reference"""
        citation = Citation(
            citation_id="p1_img1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",  # Changed from "pdf" to valid source
            content_type="picture",
            file_reference="page1_img1.png"
        )
        
        footnote = citation.to_markdown_footnote()
        assert "file: page1_img1.png" in footnote
    
    def test_citation_overlaps_same_page(self):
        """Test overlap detection for same page"""
        citation1 = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",
            content_type="text"
        )
        
        citation2 = Citation(
            citation_id="p1_txt2",
            page=1,
            bbox=(400.0, 250.0, 600.0, 350.0),
            source="text",
            content_type="text"
        )
        
        assert citation1.overlaps(citation2)
        assert citation2.overlaps(citation1)
    
    def test_citation_no_overlap_different_page(self):
        """Test no overlap for different pages"""
        citation1 = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",
            content_type="text"
        )
        
        citation2 = Citation(
            citation_id="p2_txt1",
            page=2,
            bbox=(100.0, 200.0, 500.0, 300.0),
            source="text",
            content_type="text"
        )
        
        assert not citation1.overlaps(citation2)
    
    def test_citation_distance(self):
        """Test distance calculation"""
        citation1 = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(0.0, 0.0, 100.0, 100.0),
            source="text",
            content_type="text"
        )
        
        citation2 = Citation(
            citation_id="p1_txt2",
            page=1,
            bbox=(200.0, 200.0, 300.0, 300.0),
            source="text",
            content_type="text"
        )
        
        distance = citation1.distance_to(citation2)
        assert distance > 0
        
        # Distance should be symmetric
        assert citation1.distance_to(citation2) == citation2.distance_to(citation1)
    
    def test_citation_distance_infinite_different_pages(self):
        """Test distance is infinite for different pages"""
        citation1 = Citation(
            citation_id="p1_txt1",
            page=1,
            bbox=(0.0, 0.0, 100.0, 100.0),
            source="text",
            content_type="text"
        )
        
        citation2 = Citation(
            citation_id="p2_txt1",
            page=2,
            bbox=(0.0, 0.0, 100.0, 100.0),
            source="text",
            content_type="text"
        )
        
        distance = citation1.distance_to(citation2)
        assert distance == float('inf')
