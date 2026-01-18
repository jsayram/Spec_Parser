"""
Integrity verification and compliance report generation.

Provides functions to verify extraction integrity and generate
compliance reports for medical-grade audit trails.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from loguru import logger

from ..schemas.audit import (
    ComplianceReport,
    ExtractionMetadata,
    ConfidenceLevel,
    classify_confidence,
)
from ..utils.hashing import (
    compute_file_hash,
    compute_extraction_hash,
    verify_file_hash,
)


def verify_pdf_integrity(
    pdf_path: Path,
    expected_hash: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Verify PDF file integrity.
    
    Args:
        pdf_path: Path to PDF file.
        expected_hash: Optional expected hash to verify against.
        
    Returns:
        Tuple of (is_valid, actual_hash).
    """
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return False, ""
    
    actual_hash = compute_file_hash(pdf_path)
    
    if expected_hash is None:
        return True, actual_hash
    
    is_valid = actual_hash.lower() == expected_hash.lower()
    if not is_valid:
        logger.warning(
            f"Hash mismatch for {pdf_path.name}: "
            f"expected {expected_hash[:16]}..., got {actual_hash[:16]}..."
        )
    
    return is_valid, actual_hash


def verify_extraction_completeness(
    blocks: List[Dict[str, Any]],
    expected_pages: int
) -> Tuple[bool, List[str]]:
    """
    Verify extraction completeness.
    
    Args:
        blocks: List of extracted blocks.
        expected_pages: Expected number of pages.
        
    Returns:
        Tuple of (is_complete, issues).
    """
    issues = []
    
    if not blocks:
        issues.append("No blocks extracted")
        return False, issues
    
    # Check page coverage
    pages_with_content = set()
    for block in blocks:
        page = block.get("page")
        if page is not None:
            pages_with_content.add(page)
    
    missing_pages = set(range(expected_pages)) - pages_with_content
    if missing_pages:
        issues.append(f"Missing content from pages: {sorted(missing_pages)[:10]}")
    
    # Check provenance
    blocks_without_bbox = 0
    blocks_without_source = 0
    
    for block in blocks:
        if not block.get("bbox"):
            blocks_without_bbox += 1
        if not block.get("source"):
            blocks_without_source += 1
    
    if blocks_without_bbox > 0:
        issues.append(f"{blocks_without_bbox} blocks missing bbox")
    
    if blocks_without_source > 0:
        issues.append(f"{blocks_without_source} blocks missing source type")
    
    is_complete = len(issues) == 0
    return is_complete, issues


def generate_compliance_report(
    metadata: ExtractionMetadata,
    blocks: List[Dict[str, Any]],
    output_dir: Path,
) -> ComplianceReport:
    """
    Generate compliance report for an extraction.
    
    Report is timestamped and never overwrites previous reports.
    
    Args:
        metadata: Extraction metadata.
        blocks: List of extracted blocks.
        output_dir: Directory to save report.
        
    Returns:
        Generated ComplianceReport.
    """
    report_id = f"compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Verify source
    pdf_path = Path(metadata.source_pdf_path)
    source_verified, actual_hash = verify_pdf_integrity(
        pdf_path, 
        metadata.source_pdf_hash
    )
    
    # Count blocks by type and confidence
    blocks_with_provenance = 0
    blocks_needing_review = 0
    blocks_rejected = 0
    confidence_sum = 0.0
    confidence_count = 0
    
    for block in blocks:
        # Check provenance
        if block.get("bbox") and block.get("source"):
            blocks_with_provenance += 1
        
        # Check OCR confidence
        confidence = block.get("confidence")
        if confidence is not None:
            confidence_sum += confidence
            confidence_count += 1
            
            level = classify_confidence(confidence)
            if level == ConfidenceLevel.REVIEW:
                blocks_needing_review += 1
            elif level == ConfidenceLevel.REJECTED:
                blocks_rejected += 1
    
    # Calculate scores
    total_blocks = len(blocks)
    provenance_coverage = (
        blocks_with_provenance / total_blocks if total_blocks > 0 else 0.0
    )
    ocr_quality_score = (
        confidence_sum / confidence_count if confidence_count > 0 else 1.0
    )
    
    # Count errors
    total_errors = len(metadata.stats.errors)
    critical_errors = sum(
        1 for e in metadata.stats.errors 
        if e.severity.value in ("error", "fatal")
    )
    
    # Calculate compliance score
    # Weighted: 40% provenance, 30% OCR quality, 20% no critical errors, 10% completeness
    error_score = 1.0 if critical_errors == 0 else max(0, 1 - (critical_errors / 10))
    completeness_score = (
        metadata.stats.processed_pages / metadata.stats.total_pages
        if metadata.stats.total_pages > 0 else 1.0
    )
    
    compliance_score = (
        0.4 * provenance_coverage +
        0.3 * ocr_quality_score +
        0.2 * error_score +
        0.1 * completeness_score
    )
    
    # Determine if compliant and review needed
    is_compliant = (
        compliance_score >= 0.8 and
        critical_errors == 0 and
        provenance_coverage >= 0.95
    )
    
    review_required = (
        blocks_needing_review > 0 or
        blocks_rejected > 0 or
        not source_verified
    )
    
    # Build issues list
    issues = []
    if not source_verified:
        issues.append("Source PDF hash verification failed")
    if provenance_coverage < 0.95:
        issues.append(f"Provenance coverage below 95%: {provenance_coverage:.1%}")
    if blocks_rejected > 0:
        issues.append(f"{blocks_rejected} blocks with low OCR confidence (rejected)")
    if critical_errors > 0:
        issues.append(f"{critical_errors} critical errors during extraction")
    
    # Build recommendations
    recommendations = []
    if blocks_needing_review > 0:
        recommendations.append(
            f"Review {blocks_needing_review} blocks with medium OCR confidence"
        )
    if blocks_rejected > 0:
        recommendations.append(
            f"Re-scan or manually transcribe {blocks_rejected} low-confidence blocks"
        )
    if ocr_quality_score < 0.8:
        recommendations.append("Consider improving source document quality")
    
    # Create report
    report = ComplianceReport(
        report_id=report_id,
        source_verified=source_verified,
        source_hash_match=source_verified,
        source_pdf_hash=actual_hash or metadata.source_pdf_hash,
        extraction_id=metadata.extraction_id,
        extraction_hash=compute_extraction_hash(blocks),
        total_blocks=total_blocks,
        blocks_with_provenance=blocks_with_provenance,
        provenance_coverage=provenance_coverage,
        ocr_quality_score=ocr_quality_score,
        blocks_needing_review=blocks_needing_review,
        blocks_rejected=blocks_rejected,
        total_errors=total_errors,
        critical_errors=critical_errors,
        compliance_score=compliance_score,
        is_compliant=is_compliant,
        review_required=review_required,
        issues=issues,
        recommendations=recommendations,
    )
    
    # Save report (timestamped, never overwrites)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{report_id}.json"
    
    with open(report_path, "w") as f:
        json.dump(report.model_dump(mode="json"), f, indent=2, default=str)
    
    logger.info(f"Compliance report saved: {report_path}")
    logger.info(
        f"Compliance score: {compliance_score:.1%}, "
        f"Compliant: {is_compliant}, Review required: {review_required}"
    )
    
    return report
