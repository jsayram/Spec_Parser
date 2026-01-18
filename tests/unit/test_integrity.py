"""
Unit tests for integrity verification and compliance report generation.

Tests PDF verification, extraction completeness, and report generation.
"""

import json
from pathlib import Path
from datetime import datetime

import pytest

from spec_parser.schemas.audit import (
    ExtractionMetadata,
    ProcessingStats,
    OCRStats,
    ErrorRecord,
    ErrorSeverity,
)
from spec_parser.validation.integrity import (
    verify_pdf_integrity,
    verify_extraction_completeness,
    generate_compliance_report,
)
from spec_parser.utils.hashing import compute_file_hash


class TestVerifyPDFIntegrity:
    """Tests for verify_pdf_integrity function."""

    def test_verify_existing_file(self, tmp_path: Path):
        """Test verifying an existing file without expected hash."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\ntest content")
        
        is_valid, actual_hash = verify_pdf_integrity(test_file)
        
        assert is_valid is True
        assert len(actual_hash) == 64

    def test_verify_with_correct_hash(self, tmp_path: Path):
        """Test verifying with correct expected hash."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\ntest content")
        expected_hash = compute_file_hash(test_file)
        
        is_valid, actual_hash = verify_pdf_integrity(test_file, expected_hash)
        
        assert is_valid is True
        assert actual_hash == expected_hash

    def test_verify_with_wrong_hash(self, tmp_path: Path):
        """Test verifying with incorrect expected hash."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\ntest content")
        wrong_hash = "0" * 64
        
        is_valid, actual_hash = verify_pdf_integrity(test_file, wrong_hash)
        
        assert is_valid is False
        assert actual_hash != wrong_hash

    def test_verify_nonexistent_file(self, tmp_path: Path):
        """Test verifying a nonexistent file."""
        nonexistent = tmp_path / "nonexistent.pdf"
        
        is_valid, actual_hash = verify_pdf_integrity(nonexistent)
        
        assert is_valid is False
        assert actual_hash == ""


class TestVerifyExtractionCompleteness:
    """Tests for verify_extraction_completeness function."""

    def test_complete_extraction(self):
        """Test verification of complete extraction."""
        blocks = [
            {"page": 0, "bbox": [0, 0, 100, 100], "source": "text", "content": "Text 1"},
            {"page": 1, "bbox": [0, 0, 100, 100], "source": "text", "content": "Text 2"},
            {"page": 2, "bbox": [0, 0, 100, 100], "source": "ocr", "content": "OCR text"},
        ]
        
        is_complete, issues = verify_extraction_completeness(blocks, expected_pages=3)
        
        assert is_complete is True
        assert len(issues) == 0

    def test_missing_pages(self):
        """Test verification with missing pages."""
        blocks = [
            {"page": 0, "bbox": [0, 0, 100, 100], "source": "text"},
            {"page": 2, "bbox": [0, 0, 100, 100], "source": "text"},
            # Page 1 is missing
        ]
        
        is_complete, issues = verify_extraction_completeness(blocks, expected_pages=3)
        
        assert is_complete is False
        assert any("Missing content from pages" in issue for issue in issues)

    def test_missing_bbox(self):
        """Test verification with blocks missing bbox."""
        blocks = [
            {"page": 0, "source": "text"},  # Missing bbox
            {"page": 1, "bbox": [0, 0, 100, 100], "source": "text"},
        ]
        
        is_complete, issues = verify_extraction_completeness(blocks, expected_pages=2)
        
        assert is_complete is False
        assert any("missing bbox" in issue for issue in issues)

    def test_missing_source(self):
        """Test verification with blocks missing source."""
        blocks = [
            {"page": 0, "bbox": [0, 0, 100, 100]},  # Missing source
            {"page": 1, "bbox": [0, 0, 100, 100], "source": "text"},
        ]
        
        is_complete, issues = verify_extraction_completeness(blocks, expected_pages=2)
        
        assert is_complete is False
        assert any("missing source" in issue for issue in issues)

    def test_empty_extraction(self):
        """Test verification of empty extraction."""
        blocks = []
        
        is_complete, issues = verify_extraction_completeness(blocks, expected_pages=5)
        
        assert is_complete is False
        assert "No blocks extracted" in issues


class TestGenerateComplianceReport:
    """Tests for generate_compliance_report function."""

    @pytest.fixture
    def sample_metadata(self, tmp_path: Path) -> ExtractionMetadata:
        """Create sample extraction metadata."""
        # Create a test PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\ntest content for hashing")
        
        return ExtractionMetadata(
            source_pdf_path=str(pdf_file),
            source_pdf_hash=compute_file_hash(pdf_file),
            source_pdf_size_bytes=pdf_file.stat().st_size,
            source_pdf_pages=10,
            extraction_id="ext_test_123",
            stats=ProcessingStats(
                total_pages=10,
                processed_pages=10,
                total_blocks=50,
                text_blocks=40,
                image_blocks=10,
                ocr_stats=OCRStats(
                    total_regions=10,
                    accepted_count=7,
                    review_count=2,
                    rejected_count=1,
                    average_confidence=0.82,
                ),
            ),
        )

    @pytest.fixture
    def sample_blocks(self):
        """Create sample blocks for testing."""
        blocks = []
        for i in range(10):
            blocks.append({
                "page": i,
                "bbox": [0, 0, 100, 100],
                "source": "text" if i < 8 else "ocr",
                "content": f"Block {i}",
                "confidence": 0.85 if i >= 8 else None,
            })
        return blocks

    def test_generate_report_success(
        self, tmp_path: Path, sample_metadata: ExtractionMetadata, sample_blocks
    ):
        """Test generating a compliance report successfully."""
        output_dir = tmp_path / "compliance"
        
        report = generate_compliance_report(
            metadata=sample_metadata,
            blocks=sample_blocks,
            output_dir=output_dir,
        )
        
        assert report.report_id.startswith("compliance_")
        assert report.source_verified is True
        assert report.total_blocks == 10
        assert report.blocks_with_provenance == 10
        assert report.provenance_coverage == 1.0
        assert 0 <= report.compliance_score <= 1

    def test_report_saved_to_disk(
        self, tmp_path: Path, sample_metadata: ExtractionMetadata, sample_blocks
    ):
        """Test that report is saved to disk."""
        output_dir = tmp_path / "compliance"
        
        report = generate_compliance_report(
            metadata=sample_metadata,
            blocks=sample_blocks,
            output_dir=output_dir,
        )
        
        report_path = output_dir / f"{report.report_id}.json"
        assert report_path.exists()
        
        with open(report_path) as f:
            saved_report = json.load(f)
        
        assert saved_report["report_id"] == report.report_id
        assert saved_report["total_blocks"] == 10

    def test_timestamped_reports_no_overwrite(
        self, tmp_path: Path, sample_metadata: ExtractionMetadata, sample_blocks
    ):
        """Test that multiple reports don't overwrite each other."""
        output_dir = tmp_path / "compliance"
        
        report1 = generate_compliance_report(
            metadata=sample_metadata,
            blocks=sample_blocks,
            output_dir=output_dir,
        )
        
        report2 = generate_compliance_report(
            metadata=sample_metadata,
            blocks=sample_blocks,
            output_dir=output_dir,
        )
        
        # Different report IDs
        assert report1.report_id != report2.report_id
        
        # Both files exist
        assert (output_dir / f"{report1.report_id}.json").exists()
        assert (output_dir / f"{report2.report_id}.json").exists()

    def test_report_with_low_confidence_blocks(self, tmp_path: Path):
        """Test report generation with low confidence OCR blocks."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\ntest")
        
        metadata = ExtractionMetadata(
            source_pdf_path=str(pdf_file),
            source_pdf_hash=compute_file_hash(pdf_file),
            source_pdf_size_bytes=100,
            source_pdf_pages=3,
            extraction_id="ext_low_conf",
            stats=ProcessingStats(total_pages=3, processed_pages=3),
        )
        
        blocks = [
            {"page": 0, "bbox": [0, 0, 100, 100], "source": "ocr", "confidence": 0.3},  # Rejected
            {"page": 1, "bbox": [0, 0, 100, 100], "source": "ocr", "confidence": 0.6},  # Review
            {"page": 2, "bbox": [0, 0, 100, 100], "source": "ocr", "confidence": 0.9},  # Accepted
        ]
        
        output_dir = tmp_path / "compliance"
        report = generate_compliance_report(
            metadata=metadata,
            blocks=blocks,
            output_dir=output_dir,
        )
        
        assert report.blocks_needing_review == 1  # 0.6 confidence
        assert report.blocks_rejected == 1  # 0.3 confidence
        assert report.review_required is True

    def test_report_with_errors(self, tmp_path: Path):
        """Test report generation when extraction had errors."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\ntest")
        
        error = ErrorRecord(
            severity=ErrorSeverity.ERROR,
            error_type="OCRError",
            message="Failed to process",
        )
        
        metadata = ExtractionMetadata(
            source_pdf_path=str(pdf_file),
            source_pdf_hash=compute_file_hash(pdf_file),
            source_pdf_size_bytes=100,
            source_pdf_pages=1,
            extraction_id="ext_errors",
            stats=ProcessingStats(
                total_pages=1,
                processed_pages=1,
                errors=[error],
            ),
        )
        
        blocks = [{"page": 0, "bbox": [0, 0, 100, 100], "source": "text"}]
        
        output_dir = tmp_path / "compliance"
        report = generate_compliance_report(
            metadata=metadata,
            blocks=blocks,
            output_dir=output_dir,
        )
        
        assert report.total_errors == 1
        assert report.critical_errors == 1
