"""
Unit tests for spec diff detector.

Tests spec version comparison and change report generation.
"""

import pytest
import json
from pathlib import Path
from src.spec_parser.validation.spec_diff import (
    SpecChangeDetector,
    SpecDiff,
    BlockChange,
    RebuildDecision
)
from src.spec_parser.validation.impact_classifier import ImpactLevel
from src.spec_parser.utils.hashing import compute_content_hash


@pytest.fixture
def sample_json_v1(tmp_path):
    """Create version 1 JSON sidecar."""
    doc_data = [
        {
            "page": 1,
            "blocks": [
                {
                    "type": "text",
                    "block_id": 1,
                    "markdown": "Message OBS.R01 definition",
                    "bbox": [100, 200, 500, 250],
                    "source": "text",
                    "content_hash": compute_content_hash("Message OBS.R01 definition")
                }
            ]
        }
    ]
    
    json_path = tmp_path / "v1" / "document.json"
    json_path.parent.mkdir(parents=True)
    with open(json_path, 'w') as f:
        json.dump(doc_data, f)
    
    return json_path


@pytest.fixture
def sample_json_v2_doc_change(tmp_path):
    """Create version 2 with LOW impact documentation change."""
    doc_data = [
        {
            "page": 1,
            "blocks": [
                {
                    "type": "text",
                    "block_id": 1,
                    "markdown": "Message OBS.R01 definition - updated documentation",
                    "bbox": [100, 200, 500, 250],
                    "source": "text",
                    "content_hash": compute_content_hash("Message OBS.R01 definition - updated documentation")
                }
            ]
        }
    ]
    
    json_path = tmp_path / "v2_doc" / "document.json"
    json_path.parent.mkdir(parents=True)
    with open(json_path, 'w') as f:
        json.dump(doc_data, f)
    
    return json_path


@pytest.fixture
def sample_json_v2_breaking(tmp_path):
    """Create version 2 with HIGH impact breaking change."""
    doc_data = [
        {
            "page": 1,
            "blocks": []  # Message removed - breaking change
        },
        {
            "page": 2,
            "blocks": [
                {
                    "type": "text",
                    "block_id": 2,
                    "markdown": "New message QRY.R02 added",
                    "bbox": [100, 100, 500, 150],
                    "source": "text",
                    "content_hash": compute_content_hash("New message QRY.R02 added")
                }
            ]
        }
    ]
    
    json_path = tmp_path / "v2_break" / "document.json"
    json_path.parent.mkdir(parents=True)
    with open(json_path, 'w') as f:
        json.dump(doc_data, f)
    
    return json_path


@pytest.fixture
def sample_pdf(tmp_path):
    """Create dummy PDF for hashing."""
    pdf_path = tmp_path / "spec.pdf"
    pdf_path.write_text("dummy pdf content")
    return pdf_path


class TestBaselineCreation:
    """Test baseline diff creation for first version."""
    
    def test_creates_baseline_diff(self, tmp_path, sample_json_v1, sample_pdf):
        detector = SpecChangeDetector(tmp_path)
        diff = detector.compare_specs(
            old_pdf_path=None,
            new_pdf_path=sample_pdf,
            old_json_path=None,
            new_json_path=sample_json_v1,
            old_version="none",
            new_version="1.0",
            device_type="TestDevice"
        )
        
        assert diff.is_baseline
        assert not diff.rebuild_required
        assert diff.new_inventory is not None
        assert diff.old_inventory is None
    
    def test_baseline_has_no_changes(self, tmp_path, sample_json_v1, sample_pdf):
        detector = SpecChangeDetector(tmp_path)
        diff = detector.compare_specs(
            old_pdf_path=None,
            new_pdf_path=sample_pdf,
            old_json_path=None,
            new_json_path=sample_json_v1,
            old_version="none",
            new_version="1.0",
            device_type="TestDevice"
        )
        
        assert len(diff.changes) == 0


class TestPDFHashComparison:
    """Test PDF hash-based change detection."""
    
    def test_identical_pdfs_no_changes(self, tmp_path, sample_json_v1):
        detector = SpecChangeDetector(tmp_path)
        
        # Same PDF for both versions
        pdf_path = tmp_path / "spec.pdf"
        pdf_path.write_text("same content")
        
        diff = detector.compare_specs(
            old_pdf_path=pdf_path,
            new_pdf_path=pdf_path,
            old_json_path=sample_json_v1,
            new_json_path=sample_json_v1,
            old_version="1.0",
            new_version="1.1",
            device_type="TestDevice"
        )
        
        assert not diff.pdf_hash_changed
        assert not diff.rebuild_required
        assert len(diff.changes) == 0


class TestBlockComparison:
    """Test block-by-block comparison."""
    
    def test_detects_removed_blocks(self, tmp_path, sample_json_v1, sample_json_v2_breaking, sample_pdf):
        detector = SpecChangeDetector(tmp_path)
        
        old_pdf = tmp_path / "v1.pdf"
        new_pdf = tmp_path / "v2.pdf"
        old_pdf.write_text("v1")
        new_pdf.write_text("v2")
        
        diff = detector.compare_specs(
            old_pdf_path=old_pdf,
            new_pdf_path=new_pdf,
            old_json_path=sample_json_v1,
            new_json_path=sample_json_v2_breaking,
            old_version="1.0",
            new_version="2.0",
            device_type="TestDevice"
        )
        
        # Should detect removed block
        assert len(diff.changes) > 0
        removed_changes = [c for c in diff.changes if c.old_content is not None and c.new_content is None]
        assert len(removed_changes) > 0
    
    def test_detects_added_blocks(self, tmp_path, sample_json_v1, sample_json_v2_breaking, sample_pdf):
        detector = SpecChangeDetector(tmp_path)
        
        old_pdf = tmp_path / "v1.pdf"
        new_pdf = tmp_path / "v2.pdf"
        old_pdf.write_text("v1")
        new_pdf.write_text("v2")
        
        diff = detector.compare_specs(
            old_pdf_path=old_pdf,
            new_pdf_path=new_pdf,
            old_json_path=sample_json_v1,
            new_json_path=sample_json_v2_breaking,
            old_version="1.0",
            new_version="2.0",
            device_type="TestDevice"
        )
        
        # Should detect added block
        added_changes = [c for c in diff.changes if c.old_content is None and c.new_content is not None]
        assert len(added_changes) > 0


class TestRebuildDecision:
    """Test rebuild decision logic."""
    
    def test_low_impact_no_rebuild(self, tmp_path, sample_json_v1, sample_json_v2_doc_change):
        detector = SpecChangeDetector(tmp_path)
        
        old_pdf = tmp_path / "v1.pdf"
        new_pdf = tmp_path / "v2.pdf"
        old_pdf.write_text("v1")
        new_pdf.write_text("v2 documentation update")
        
        diff = detector.compare_specs(
            old_pdf_path=old_pdf,
            new_pdf_path=new_pdf,
            old_json_path=sample_json_v1,
            new_json_path=sample_json_v2_doc_change,
            old_version="1.0",
            new_version="1.1",
            device_type="TestDevice"
        )
        
        # Documentation changes should not require rebuild
        assert not diff.rebuild_required
    
    def test_high_impact_requires_rebuild(self, tmp_path, sample_json_v1, sample_json_v2_breaking):
        detector = SpecChangeDetector(tmp_path)
        
        old_pdf = tmp_path / "v1.pdf"
        new_pdf = tmp_path / "v2.pdf"
        old_pdf.write_text("v1")
        new_pdf.write_text("v2 breaking changes")
        
        diff = detector.compare_specs(
            old_pdf_path=old_pdf,
            new_pdf_path=new_pdf,
            old_json_path=sample_json_v1,
            new_json_path=sample_json_v2_breaking,
            old_version="1.0",
            new_version="2.0",
            device_type="TestDevice"
        )
        
        # Breaking changes should require rebuild
        assert diff.rebuild_required


class TestReportGeneration:
    """Test change report generation."""
    
    def test_generates_baseline_report(self, tmp_path, sample_json_v1, sample_pdf):
        detector = SpecChangeDetector(tmp_path / "output")
        
        diff = detector.compare_specs(
            old_pdf_path=None,
            new_pdf_path=sample_pdf,
            old_json_path=None,
            new_json_path=sample_json_v1,
            old_version="none",
            new_version="1.0",
            device_type="TestDevice"
        )
        
        report_path = detector.generate_report(diff, "TestDevice", "TestVendor", "TestModel")
        
        assert report_path.exists()
        assert "BASELINE" in report_path.name
        assert "v1.0" in report_path.name
        
        content = report_path.read_text()
        assert "Baseline Report" in content
        assert "Initial onboarding" in content or "No Comparison" in content
    
    def test_generates_change_report(self, tmp_path, sample_json_v1, sample_json_v2_doc_change):
        detector = SpecChangeDetector(tmp_path / "output")
        
        old_pdf = tmp_path / "v1.pdf"
        new_pdf = tmp_path / "v2.pdf"
        old_pdf.write_text("v1")
        new_pdf.write_text("v2")
        
        diff = detector.compare_specs(
            old_pdf_path=old_pdf,
            new_pdf_path=new_pdf,
            old_json_path=sample_json_v1,
            new_json_path=sample_json_v2_doc_change,
            old_version="1.0",
            new_version="1.1",
            device_type="TestDevice"
        )
        
        report_path = detector.generate_report(diff, "TestDevice", "TestVendor", "TestModel")
        
        assert report_path.exists()
        assert "CHANGES" in report_path.name
        assert "v1.0" in report_path.name
        assert "v1.1" in report_path.name
        
        content = report_path.read_text()
        assert "Change Report" in content
    
    def test_generates_no_change_report(self, tmp_path, sample_json_v1):
        detector = SpecChangeDetector(tmp_path / "output")
        
        pdf_path = tmp_path / "spec.pdf"
        pdf_path.write_text("same")
        
        diff = detector.compare_specs(
            old_pdf_path=pdf_path,
            new_pdf_path=pdf_path,
            old_json_path=sample_json_v1,
            new_json_path=sample_json_v1,
            old_version="1.0",
            new_version="1.1",
            device_type="TestDevice"
        )
        
        report_path = detector.generate_report(diff, "TestDevice", "TestVendor", "TestModel")
        
        assert report_path.exists()
        content = report_path.read_text()
        assert "No Changes Detected" in content or "identical" in content.lower()
    
    def test_report_has_timestamp(self, tmp_path, sample_json_v1, sample_pdf):
        detector = SpecChangeDetector(tmp_path / "output")
        
        diff = detector.compare_specs(
            old_pdf_path=None,
            new_pdf_path=sample_pdf,
            old_json_path=None,
            new_json_path=sample_json_v1,
            old_version="none",
            new_version="1.0",
            device_type="TestDevice"
        )
        
        report_path = detector.generate_report(diff, "TestDevice", "TestVendor", "TestModel")
        
        # Filename should have timestamp (YYYYMMDD_HHMMSS)
        assert len([part for part in report_path.stem.split('_') if part.isdigit()]) >= 2


class TestMessageInventoryComparison:
    """Test message inventory analysis."""
    
    def test_detects_message_additions(self, tmp_path):
        # Create JSON with different messages
        v1_data = [{"page": 1, "blocks": [
            {"type": "text", "block_id": 1, "markdown": "OBS.R01 message", 
             "bbox": [0,0,100,100], "source": "text", 
             "content_hash": compute_content_hash("OBS.R01 message")}
        ]}]
        
        v2_data = [{"page": 1, "blocks": [
            {"type": "text", "block_id": 1, "markdown": "OBS.R01 message", 
             "bbox": [0,0,100,100], "source": "text",
             "content_hash": compute_content_hash("OBS.R01 message")},
            {"type": "text", "block_id": 2, "markdown": "QCN.R01 message added", 
             "bbox": [0,100,100,200], "source": "text",
             "content_hash": compute_content_hash("QCN.R01 message added")}
        ]}]
        
        v1_path = tmp_path / "v1.json"
        v2_path = tmp_path / "v2.json"
        with open(v1_path, 'w') as f:
            json.dump(v1_data, f)
        with open(v2_path, 'w') as f:
            json.dump(v2_data, f)
        
        detector = SpecChangeDetector(tmp_path)
        
        old_pdf = tmp_path / "v1.pdf"
        new_pdf = tmp_path / "v2.pdf"
        old_pdf.write_text("v1")
        new_pdf.write_text("v2")
        
        diff = detector.compare_specs(
            old_pdf_path=old_pdf,
            new_pdf_path=new_pdf,
            old_json_path=v1_path,
            new_json_path=v2_path,
            old_version="1.0",
            new_version="2.0",
            device_type="TestDevice"
        )
        
        # Should detect message addition
        assert diff.new_inventory is not None
        assert diff.old_inventory is not None
