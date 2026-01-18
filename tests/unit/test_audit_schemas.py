"""
Unit tests for audit and compliance schemas.

Tests Pydantic models for extraction metadata, processing stats,
confidence classification, and feedback records.
"""

from datetime import datetime

import pytest

from spec_parser.schemas.audit import (
    ConfidenceLevel,
    ErrorSeverity,
    ErrorRecord,
    OCRStats,
    ProcessingStats,
    ExtractionMetadata,
    FeedbackType,
    FeedbackRecord,
    ComplianceReport,
    classify_confidence,
)


class TestConfidenceClassification:
    """Tests for confidence level classification."""

    def test_classify_high_confidence(self):
        """Test classification of high confidence (>= 0.8)."""
        assert classify_confidence(0.8) == ConfidenceLevel.ACCEPTED
        assert classify_confidence(0.9) == ConfidenceLevel.ACCEPTED
        assert classify_confidence(1.0) == ConfidenceLevel.ACCEPTED
        assert classify_confidence(0.85) == ConfidenceLevel.ACCEPTED

    def test_classify_medium_confidence(self):
        """Test classification of medium confidence (0.5 - 0.8)."""
        assert classify_confidence(0.5) == ConfidenceLevel.REVIEW
        assert classify_confidence(0.6) == ConfidenceLevel.REVIEW
        assert classify_confidence(0.7) == ConfidenceLevel.REVIEW
        assert classify_confidence(0.79) == ConfidenceLevel.REVIEW

    def test_classify_low_confidence(self):
        """Test classification of low confidence (< 0.5)."""
        assert classify_confidence(0.0) == ConfidenceLevel.REJECTED
        assert classify_confidence(0.3) == ConfidenceLevel.REJECTED
        assert classify_confidence(0.49) == ConfidenceLevel.REJECTED

    def test_boundary_values(self):
        """Test exact boundary values."""
        assert classify_confidence(0.5) == ConfidenceLevel.REVIEW  # Lower boundary of review
        assert classify_confidence(0.8) == ConfidenceLevel.ACCEPTED  # Lower boundary of accepted


class TestErrorRecord:
    """Tests for ErrorRecord model."""

    def test_create_error_record(self):
        """Test creating an error record."""
        error = ErrorRecord(
            severity=ErrorSeverity.ERROR,
            page=5,
            block_index=10,
            error_type="OCRError",
            message="Failed to process region",
        )
        
        assert error.severity == ErrorSeverity.ERROR
        assert error.page == 5
        assert error.block_index == 10
        assert error.error_type == "OCRError"
        assert isinstance(error.timestamp, datetime)

    def test_error_with_context(self):
        """Test error record with context."""
        error = ErrorRecord(
            severity=ErrorSeverity.WARNING,
            error_type="LowConfidence",
            message="OCR confidence below threshold",
            context={"confidence": 0.3, "threshold": 0.5},
        )
        
        assert error.context == {"confidence": 0.3, "threshold": 0.5}


class TestOCRStats:
    """Tests for OCRStats model."""

    def test_default_values(self):
        """Test default OCR stats values."""
        stats = OCRStats()
        
        assert stats.total_regions == 0
        assert stats.accepted_count == 0
        assert stats.review_count == 0
        assert stats.rejected_count == 0
        assert stats.average_confidence == 0.0
        assert stats.min_confidence == 1.0
        assert stats.max_confidence == 0.0

    def test_populated_stats(self):
        """Test populated OCR stats."""
        stats = OCRStats(
            total_regions=100,
            accepted_count=70,
            review_count=20,
            rejected_count=10,
            average_confidence=0.75,
            min_confidence=0.3,
            max_confidence=0.98,
        )
        
        assert stats.total_regions == 100
        assert stats.accepted_count + stats.review_count + stats.rejected_count == 100


class TestProcessingStats:
    """Tests for ProcessingStats model."""

    def test_default_values(self):
        """Test default processing stats."""
        stats = ProcessingStats()
        
        assert stats.total_pages == 0
        assert stats.processed_pages == 0
        assert stats.total_blocks == 0
        assert isinstance(stats.ocr_stats, OCRStats)
        assert stats.errors == []

    def test_with_errors(self):
        """Test processing stats with errors."""
        error = ErrorRecord(
            severity=ErrorSeverity.ERROR,
            error_type="TestError",
            message="Test message",
        )
        stats = ProcessingStats(
            total_pages=10,
            processed_pages=9,
            errors=[error],
        )
        
        assert len(stats.errors) == 1
        assert stats.errors[0].error_type == "TestError"


class TestExtractionMetadata:
    """Tests for ExtractionMetadata model."""

    def test_required_fields(self):
        """Test creating metadata with required fields."""
        metadata = ExtractionMetadata(
            source_pdf_path="/path/to/file.pdf",
            source_pdf_hash="abc123def456",
            source_pdf_size_bytes=1024000,
            source_pdf_pages=50,
            extraction_id="ext_12345",
        )
        
        assert metadata.source_pdf_path == "/path/to/file.pdf"
        assert metadata.source_pdf_hash == "abc123def456"
        assert metadata.source_pdf_size_bytes == 1024000
        assert isinstance(metadata.extraction_timestamp, datetime)

    def test_with_review_required(self):
        """Test metadata with review flags."""
        metadata = ExtractionMetadata(
            source_pdf_path="/path/to/file.pdf",
            source_pdf_hash="abc123",
            source_pdf_size_bytes=1000,
            source_pdf_pages=10,
            extraction_id="ext_123",
            requires_human_review=True,
            review_reason="5 OCR blocks need review",
        )
        
        assert metadata.requires_human_review is True
        assert metadata.review_reason == "5 OCR blocks need review"


class TestFeedbackRecord:
    """Tests for FeedbackRecord model."""

    def test_correction_feedback(self):
        """Test creating a correction feedback record."""
        feedback = FeedbackRecord(
            feedback_id="fb_123",
            extraction_id="ext_456",
            block_hash="hash789",
            page=5,
            bbox=[10.0, 20.0, 100.0, 200.0],
            original_content="Incorect text",
            original_confidence=0.65,
            source_type="ocr",
            feedback_type=FeedbackType.CORRECTION,
            corrected_content="Incorrect text",
            reviewer_id="user_abc",
        )
        
        assert feedback.feedback_type == FeedbackType.CORRECTION
        assert feedback.corrected_content == "Incorrect text"
        assert feedback.include_in_training is True

    def test_confirmation_feedback(self):
        """Test creating a confirmation feedback record."""
        feedback = FeedbackRecord(
            feedback_id="fb_456",
            extraction_id="ext_789",
            block_hash="hash123",
            page=1,
            bbox=[0, 0, 50, 50],
            original_content="Correct text",
            original_confidence=0.75,
            source_type="ocr",
            feedback_type=FeedbackType.CONFIRMATION,
        )
        
        assert feedback.feedback_type == FeedbackType.CONFIRMATION
        assert feedback.corrected_content is None


class TestComplianceReport:
    """Tests for ComplianceReport model."""

    def test_compliant_report(self):
        """Test creating a compliant report."""
        report = ComplianceReport(
            report_id="compliance_123",
            source_verified=True,
            source_hash_match=True,
            source_pdf_hash="abc123",
            extraction_id="ext_456",
            extraction_hash="def789",
            total_blocks=100,
            blocks_with_provenance=100,
            provenance_coverage=1.0,
            ocr_quality_score=0.9,
            blocks_needing_review=0,
            blocks_rejected=0,
            total_errors=0,
            critical_errors=0,
            compliance_score=0.95,
            is_compliant=True,
            review_required=False,
        )
        
        assert report.is_compliant is True
        assert report.review_required is False
        assert report.compliance_score == 0.95

    def test_non_compliant_report(self):
        """Test creating a non-compliant report."""
        report = ComplianceReport(
            report_id="compliance_456",
            source_verified=False,
            source_hash_match=False,
            source_pdf_hash="abc123",
            extraction_id="ext_789",
            extraction_hash="def012",
            total_blocks=50,
            blocks_with_provenance=40,
            provenance_coverage=0.8,
            ocr_quality_score=0.6,
            blocks_needing_review=10,
            blocks_rejected=5,
            total_errors=3,
            critical_errors=1,
            compliance_score=0.65,
            is_compliant=False,
            review_required=True,
            issues=["Source PDF hash verification failed", "Low provenance coverage"],
            recommendations=["Re-verify source document", "Review 10 blocks"],
        )
        
        assert report.is_compliant is False
        assert report.review_required is True
        assert len(report.issues) == 2
        assert len(report.recommendations) == 2


class TestEnumValues:
    """Tests for enum values."""

    def test_confidence_level_values(self):
        """Test ConfidenceLevel enum values."""
        assert ConfidenceLevel.REJECTED.value == "rejected"
        assert ConfidenceLevel.REVIEW.value == "review"
        assert ConfidenceLevel.ACCEPTED.value == "accepted"

    def test_error_severity_values(self):
        """Test ErrorSeverity enum values."""
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.FATAL.value == "fatal"

    def test_feedback_type_values(self):
        """Test FeedbackType enum values."""
        assert FeedbackType.CORRECTION.value == "correction"
        assert FeedbackType.CONFIRMATION.value == "confirmation"
        assert FeedbackType.REJECTION.value == "rejection"
        assert FeedbackType.CLASSIFICATION.value == "classification"
