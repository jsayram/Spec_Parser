"""
pytest configuration and shared fixtures.
"""

import pytest
from pathlib import Path
from typing import List

from spec_parser.models.citation import Citation
from spec_parser.models.page_bundle import PageBundle, TextBlock, PictureBlock, TableBlock
from spec_parser.models.rlm_models import DocumentSpan, TOCEntry
from spec_parser.rlm.document_navigator import DocumentNavigator


@pytest.fixture
def sample_citation():
    """Sample citation for testing"""
    return Citation(
        citation_id="p1_txt1",
        page=1,
        bbox=(100.0, 200.0, 500.0, 300.0),
        source="text",
        content_type="text"
    )


@pytest.fixture
def sample_text_block():
    """Sample text block for testing"""
    return TextBlock(
        type="text",
        bbox=(100.0, 200.0, 500.0, 300.0),
        citation="p1_txt1",
        md_slice=(0, 50),
        content="This is sample text content for testing."
    )


@pytest.fixture
def sample_page_bundle():
    """Sample page bundle for testing"""
    bundle = PageBundle(
        page=1,
        markdown="# Test Page\n\nThis is sample content.\n\n## Section 1\n\nMore content here.",
        blocks=[],
        ocr=[],
        citations={},
        metadata={"pdf_name": "test.pdf"}
    )
    
    # Add a text block
    text_block = TextBlock(
        type="text",
        bbox=(100.0, 200.0, 500.0, 300.0),
        citation="p1_txt1",
        md_slice=(0, 14),
        content="# Test Page"
    )
    
    citation = Citation(
        citation_id="p1_txt1",
        page=1,
        bbox=(100.0, 200.0, 500.0, 300.0),
        source="text",
        content_type="text"
    )
    
    bundle.add_block(text_block, citation)
    
    return bundle


@pytest.fixture
def sample_page_bundles() -> List[PageBundle]:
    """Multiple page bundles for navigator testing"""
    bundles = []
    
    # Page 1
    bundle1 = PageBundle(
        page=1,
        markdown="# POCT1 Specification\n\n## Overview\n\nThis document defines POCT1 interface.",
        blocks=[],
        ocr=[],
        citations={},
        metadata={"pdf_name": "spec.pdf"}
    )
    bundles.append(bundle1)
    
    # Page 2
    bundle2 = PageBundle(
        page=2,
        markdown="## Message Types\n\n### OBS.R01\n\nObservation result message.\n\n### QCN.R01\n\nQuery by parameter.",
        blocks=[],
        ocr=[],
        citations={},
        metadata={"pdf_name": "spec.pdf"}
    )
    bundles.append(bundle2)
    
    return bundles


@pytest.fixture
def document_navigator(sample_page_bundles) -> DocumentNavigator:
    """DocumentNavigator instance for testing"""
    return DocumentNavigator(sample_page_bundles)


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory for tests"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "images").mkdir()
    (output_dir / "markdown").mkdir()
    (output_dir / "json").mkdir()
    return output_dir


@pytest.fixture
def sample_pdf_path():
    """Path to sample PDF (if exists in fixtures)"""
    fixture_path = Path(__file__).parent / "fixtures" / "pdfs" / "simple_text.pdf"
    if fixture_path.exists():
        return fixture_path
    return None


@pytest.fixture
def sample_bbox():
    """Sample bounding box for testing"""
    return (100.0, 200.0, 500.0, 400.0)


@pytest.fixture
def overlapping_bbox():
    """Bounding box that overlaps with sample_bbox"""
    return (300.0, 300.0, 600.0, 500.0)


@pytest.fixture
def non_overlapping_bbox():
    """Bounding box that doesn't overlap with sample_bbox"""
    return (600.0, 600.0, 700.0, 700.0)
