"""
Audit and compliance schemas for medical-grade extraction.

Provides Pydantic models for tracking extraction metadata,
processing statistics, errors, and human feedback.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """OCR confidence classification levels."""
    
    REJECTED = "rejected"      # < 0.5 - Not usable
    REVIEW = "review"          # 0.5 - 0.8 - Needs human review
    ACCEPTED = "accepted"      # >= 0.8 - High confidence


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    
    WARNING = "warning"        # Non-critical, extraction continued
    ERROR = "error"            # Critical, block skipped
    FATAL = "fatal"            # Extraction aborted


class ErrorRecord(BaseModel):
    """Record of an error during extraction."""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    severity: ErrorSeverity
    page: Optional[int] = None
    block_index: Optional[int] = None
    error_type: str
    message: str
    context: Optional[Dict[str, Any]] = None


class OCRStats(BaseModel):
    """OCR processing statistics."""
    
    total_regions: int = 0
    accepted_count: int = 0          # >= 0.8 confidence
    review_count: int = 0            # 0.5 - 0.8 confidence
    rejected_count: int = 0          # < 0.5 confidence
    average_confidence: float = 0.0
    min_confidence: float = 1.0
    max_confidence: float = 0.0


class ProcessingStats(BaseModel):
    """Statistics from extraction processing."""
    
    total_pages: int = 0
    processed_pages: int = 0
    skipped_pages: int = 0
    
    total_blocks: int = 0
    text_blocks: int = 0
    image_blocks: int = 0
    table_blocks: int = 0
    graphics_blocks: int = 0
    
    ocr_stats: OCRStats = Field(default_factory=OCRStats)
    
    processing_time_seconds: float = 0.0
    errors: List[ErrorRecord] = Field(default_factory=list)


class ExtractionMetadata(BaseModel):
    """Complete metadata for an extraction run."""
    
    # Source document info
    source_pdf_path: str
    source_pdf_hash: str
    source_pdf_size_bytes: int
    source_pdf_pages: int
    
    # Extraction run info
    extraction_id: str
    extraction_timestamp: datetime = Field(default_factory=datetime.now)
    extraction_version: str = "1.0.0"
    
    # Tool versions for reproducibility
    pymupdf_version: str = ""
    tesseract_version: str = ""
    parser_version: str = "1.0.0"
    
    # Processing stats
    stats: ProcessingStats = Field(default_factory=ProcessingStats)
    
    # Output info
    output_directory: str = ""
    extraction_hash: str = ""  # Hash of all extracted content
    
    # Compliance
    requires_human_review: bool = False
    review_reason: Optional[str] = None
    compliance_report_path: Optional[str] = None


class FeedbackType(str, Enum):
    """Types of human feedback."""
    
    CORRECTION = "correction"          # Content was wrong
    CONFIRMATION = "confirmation"      # Content verified correct
    REJECTION = "rejection"            # Content unusable
    CLASSIFICATION = "classification"  # Entity type correction


class FeedbackRecord(BaseModel):
    """Record of human feedback on extracted content."""
    
    feedback_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # What was reviewed
    extraction_id: str
    block_hash: str
    page: int
    bbox: List[float]
    
    # Original content
    original_content: str
    original_confidence: float
    source_type: str  # "text", "ocr", "graphics"
    
    # Feedback
    feedback_type: FeedbackType
    corrected_content: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewer_id: Optional[str] = None
    
    # For retraining
    include_in_training: bool = True


class ComplianceReport(BaseModel):
    """Compliance report for an extraction."""
    
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.now)
    
    # Source verification
    source_verified: bool
    source_hash_match: bool
    source_pdf_hash: str
    
    # Extraction verification
    extraction_id: str
    extraction_hash: str
    total_blocks: int
    blocks_with_provenance: int
    provenance_coverage: float  # Percentage
    
    # OCR quality
    ocr_quality_score: float  # 0-1
    blocks_needing_review: int
    blocks_rejected: int
    
    # Errors
    total_errors: int
    critical_errors: int
    
    # Overall
    compliance_score: float  # 0-1
    is_compliant: bool
    review_required: bool
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


def classify_confidence(confidence: float) -> ConfidenceLevel:
    """
    Classify OCR confidence into acceptance levels.
    
    Args:
        confidence: OCR confidence score (0-1).
        
    Returns:
        ConfidenceLevel enum value.
    """
    if confidence < 0.5:
        return ConfidenceLevel.REJECTED
    elif confidence < 0.8:
        return ConfidenceLevel.REVIEW
    else:
        return ConfidenceLevel.ACCEPTED
