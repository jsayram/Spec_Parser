#!/usr/bin/env python
"""
Simple CLI to test Phase 2 PDF parsing pipeline.

Usage:
    python test_phase2.py <pdf_path> [--pages N]
    
Generates timestamped compliance reports that never overwrite previous ones.
"""

import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from loguru import logger

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.parsers.ocr_processor import OCRProcessor
from spec_parser.parsers.md_merger import MarkdownMerger
from spec_parser.parsers.document_assembler import DocumentAssembler
from spec_parser.parsers.json_sidecar import JSONSidecarWriter
from spec_parser.schemas.audit import (
    ExtractionMetadata, ProcessingStats, OCRStats,
    classify_confidence, ConfidenceLevel,
)
from spec_parser.utils.hashing import compute_file_hash
from spec_parser.validation.integrity import generate_compliance_report
from spec_parser.config import settings
from spec_parser.utils.logger import setup_logger


def parse_pdf(pdf_path: Path, max_pages: int = 3):
    """
    Parse PDF and create output artifacts.
    
    Args:
        pdf_path: Path to PDF file
        max_pages: Maximum number of pages to process (for testing)
    """
    start_time = time.time()
    extraction_id = f"ext_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Starting Phase 2 pipeline for: {pdf_path.name}")
    logger.info(f"Extraction ID: {extraction_id}")
    
    # Compute source PDF hash for integrity
    pdf_hash = compute_file_hash(pdf_path)
    pdf_size = pdf_path.stat().st_size
    logger.info(f"Source PDF hash: {pdf_hash[:16]}...")
    
    # Create output session
    output_dir = settings.create_output_session(pdf_path)
    logger.info(f"Output directory: {output_dir}")
    
    # Initialize stats tracking
    ocr_stats = OCRStats()
    
    # Extract PDF
    logger.info(f"Extracting PDF...")
    with PyMuPDFExtractor(pdf_path) as extractor:
        total_pages = len(extractor.doc)
        
        # max_pages=0 means "all pages"
        if max_pages == 0:
            pages_to_process = total_pages
        else:
            pages_to_process = min(max_pages, total_pages)
        
        logger.info(f"PDF has {total_pages} pages, processing {pages_to_process}")
        
        bundles = []
        for page_num in range(1, pages_to_process + 1):
            bundle = extractor.extract_page(page_num)
            bundles.append(bundle)
            
            logger.info(
                f"Page {page_num}: {len(bundle.blocks)} blocks "
                f"({len(bundle.get_blocks_by_type('text'))} text, "
                f"{len(bundle.get_blocks_by_type('picture'))} images, "
                f"{len(bundle.get_blocks_by_type('table'))} tables, "
                f"{len(bundle.get_blocks_by_type('graphics'))} graphics)"
            )
    
    # Run OCR
    logger.info("Running OCR on extracted content...")
    ocr_processor = OCRProcessor(dpi=300, confidence_threshold=0.5)  # Lower threshold to capture review items
    
    with PyMuPDFExtractor(pdf_path) as extractor:
        for bundle in bundles:
            pdf_page = extractor.doc[bundle.page - 1]
            ocr_results = ocr_processor.process_page(bundle, pdf_page)
            
            # Add OCR results to bundle and track stats
            for idx, ocr in enumerate(ocr_results):
                citation_id = f"p{bundle.page}_ocr{idx+1}"
                ocr.citation = citation_id
                bundle.add_ocr(ocr)
                
                # Track OCR stats for compliance
                ocr_stats.total_regions += 1
                conf_level = classify_confidence(ocr.confidence)
                if conf_level == ConfidenceLevel.ACCEPTED:
                    ocr_stats.accepted_count += 1
                elif conf_level == ConfidenceLevel.REVIEW:
                    ocr_stats.review_count += 1
                else:
                    ocr_stats.rejected_count += 1
                
                ocr_stats.min_confidence = min(ocr_stats.min_confidence, ocr.confidence)
                ocr_stats.max_confidence = max(ocr_stats.max_confidence, ocr.confidence)
            
            if ocr_results:
                logger.info(f"Page {bundle.page}: {len(ocr_results)} OCR results")
    
    # Merge markdown
    logger.info("Creating enhanced markdown files...")
    merger = MarkdownMerger()
    
    for bundle in bundles:
        enhanced_md = merger.merge(bundle)
        
        # Write per-page markdown
        md_path = settings.markdown_dir / f"page_{bundle.page}.md"
        md_path.write_text(enhanced_md, encoding="utf-8")
        
        logger.info(f"Wrote: {md_path.name} ({len(enhanced_md)} chars)")
    
    # Create master markdown (1:1 with PDF)
    logger.info("Creating master markdown document...")
    assembler = DocumentAssembler()
    master_md_path = settings.markdown_dir / f"{pdf_path.stem}_MASTER.md"
    assembler.write_master_markdown(bundles, pdf_path.stem, master_md_path)
    
    # Write JSON sidecar
    logger.info("Writing JSON sidecar...")
    
    # Calculate final stats
    processing_time = time.time() - start_time
    total_blocks = sum(len(b.blocks) for b in bundles)
    text_blocks = sum(len(b.get_blocks_by_type('text')) for b in bundles)
    image_blocks = sum(len(b.get_blocks_by_type('picture')) for b in bundles)
    
    if ocr_stats.total_regions > 0:
        total_conf = sum(
            ocr.confidence for b in bundles for ocr in b.ocr
        )
        ocr_stats.average_confidence = total_conf / ocr_stats.total_regions
    
    # Build extraction metadata
    stats = ProcessingStats(
        total_pages=pages_to_process,
        processed_pages=len(bundles),
        total_blocks=total_blocks,
        text_blocks=text_blocks,
        image_blocks=image_blocks,
        ocr_stats=ocr_stats,
        processing_time_seconds=processing_time,
    )
    
    extraction_metadata = ExtractionMetadata(
        source_pdf_path=str(pdf_path.absolute()),
        source_pdf_hash=pdf_hash,
        source_pdf_size_bytes=pdf_size,
        source_pdf_pages=pages_to_process,
        extraction_id=extraction_id,
        stats=stats,
        output_directory=str(output_dir),
        requires_human_review=ocr_stats.review_count > 0,
        review_reason=f"{ocr_stats.review_count} OCR blocks need review" if ocr_stats.review_count > 0 else None,
    )
    
    json_writer = JSONSidecarWriter()
    json_path = settings.json_dir / f"{pdf_path.stem}.json"
    json_writer.write_document(
        bundles, json_path, pdf_path.stem,
        pdf_path=pdf_path,
        extraction_metadata=extraction_metadata,
    )
    
    # Generate compliance report (timestamped, never overwrites)
    logger.info("Generating compliance report...")
    compliance_dir = output_dir / "compliance"
    
    # Collect all blocks for compliance check
    all_blocks = []
    for bundle in bundles:
        for block in bundle.blocks:
            block_dict = {
                "page": bundle.page,
                "bbox": block.bbox,
                "source": getattr(block, "source", "text"),
                "content": getattr(block, "content", ""),
            }
            all_blocks.append(block_dict)
        
        for ocr in bundle.ocr:
            block_dict = {
                "page": bundle.page,
                "bbox": ocr.bbox,
                "source": "ocr",
                "content": ocr.text,
                "confidence": ocr.confidence,
            }
            all_blocks.append(block_dict)
    
    compliance_report = generate_compliance_report(
        metadata=extraction_metadata,
        blocks=all_blocks,
        output_dir=compliance_dir,
    )
    
    logger.success(f"\n✅ Phase 2 Complete!")
    logger.success(f"   Extraction ID: {extraction_id}")
    logger.success(f"   Output: {output_dir}")
    logger.success(f"   Pages: {len(bundles)}")
    logger.success(f"   Blocks: {sum(len(b.blocks) for b in bundles)}")
    logger.success(f"   OCR Results: {sum(len(b.ocr) for b in bundles)}")
    logger.success(f"     - Accepted (≥0.8): {ocr_stats.accepted_count}")
    logger.success(f"     - Review (0.5-0.8): {ocr_stats.review_count}")
    logger.success(f"     - Rejected (<0.5): {ocr_stats.rejected_count}")
    logger.success(f"   Master Markdown: {master_md_path}")
    logger.success(f"   Per-Page Markdown: {settings.markdown_dir}")
    logger.success(f"   JSON: {json_path}")
    logger.success(f"   Compliance Report: {compliance_report.report_id}")
    logger.success(f"     - Score: {compliance_report.compliance_score:.1%}")
    logger.success(f"     - Compliant: {compliance_report.is_compliant}")
    logger.success(f"     - Review Required: {compliance_report.review_required}")
    logger.success(f"   Processing Time: {processing_time:.2f}s")
    
    return output_dir


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python test_phase2.py <pdf_path> [--pages N]")
        print("\nExample:")
        print("  python test_phase2.py data/specs/my_spec.pdf --pages 5")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    # Parse --pages argument
    max_pages = 3
    if "--pages" in sys.argv:
        pages_idx = sys.argv.index("--pages")
        if pages_idx + 1 < len(sys.argv):
            max_pages = int(sys.argv[pages_idx + 1])
    
    try:
        parse_pdf(pdf_path, max_pages)
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
