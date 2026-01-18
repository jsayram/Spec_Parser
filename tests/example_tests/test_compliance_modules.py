#!/usr/bin/env python
"""Quick test of medical compliance modules."""

from spec_parser.utils.hashing import (
    compute_file_hash, compute_content_hash, compute_block_hash
)
from spec_parser.schemas.audit import (
    classify_confidence, ConfidenceLevel, ExtractionMetadata, ProcessingStats
)
from spec_parser.validation.integrity import (
    verify_pdf_integrity, generate_compliance_report
)
from spec_parser.search.feedback import FeedbackStore


def main():
    # Test hashing
    hash1 = compute_content_hash('test content')
    print(f'✅ Hashing module: {hash1[:16]}...')
    
    # Test confidence classification
    assert classify_confidence(0.9) == ConfidenceLevel.ACCEPTED
    assert classify_confidence(0.6) == ConfidenceLevel.REVIEW
    assert classify_confidence(0.3) == ConfidenceLevel.REJECTED
    print('✅ Confidence classification: accepted >= 0.8, review 0.5-0.8, rejected < 0.5')
    
    # Test audit schemas
    metadata = ExtractionMetadata(
        source_pdf_path='/tmp/test.pdf',
        source_pdf_hash='abc123',
        source_pdf_size_bytes=1000,
        source_pdf_pages=10,
        extraction_id='test_123',
        stats=ProcessingStats(total_pages=10),
    )
    print(f'✅ Audit schemas: ExtractionMetadata created')
    
    print('\n✅ All medical compliance modules imported successfully!')


if __name__ == "__main__":
    main()
