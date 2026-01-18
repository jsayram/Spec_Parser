#!/usr/bin/env python
"""
Simple CLI to test Phase 2 PDF parsing pipeline.

Usage:
    python test_phase2.py <pdf_path> [--pages N]
"""

import sys
from pathlib import Path
from loguru import logger

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.parsers.ocr_processor import OCRProcessor
from spec_parser.parsers.md_merger import MarkdownMerger
from spec_parser.parsers.document_assembler import DocumentAssembler
from spec_parser.parsers.json_sidecar import JSONSidecarWriter
from spec_parser.config import settings
from spec_parser.utils.logger import setup_logger


def parse_pdf(pdf_path: Path, max_pages: int = 3):
    """
    Parse PDF and create output artifacts.
    
    Args:
        pdf_path: Path to PDF file
        max_pages: Maximum number of pages to process (for testing)
    """
    logger.info(f"Starting Phase 2 pipeline for: {pdf_path.name}")
    
    # Create output session
    output_dir = settings.create_output_session(pdf_path)
    logger.info(f"Output directory: {output_dir}")
    
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
    ocr_processor = OCRProcessor(dpi=300, confidence_threshold=0.7)
    
    with PyMuPDFExtractor(pdf_path) as extractor:
        for bundle in bundles:
            pdf_page = extractor.doc[bundle.page - 1]
            ocr_results = ocr_processor.process_page(bundle, pdf_page)
            
            # Add OCR results to bundle
            for idx, ocr in enumerate(ocr_results):
                citation_id = f"p{bundle.page}_ocr{idx+1}"
                ocr.citation = citation_id
                bundle.add_ocr(ocr)
            
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
    json_writer = JSONSidecarWriter()
    json_path = settings.json_dir / f"{pdf_path.stem}.json"
    json_writer.write_document(bundles, json_path, pdf_path.stem)
    
    logger.success(f"\n✅ Phase 2 Complete!")
    logger.success(f"   Output: {output_dir}")
    logger.success(f"   Pages: {len(bundles)}")
    logger.success(f"   Blocks: {sum(len(b.blocks) for b in bundles)}")
    logger.success(f"   OCR Results: {sum(len(b.ocr) for b in bundles)}")
    logger.success(f"   Master Markdown: {master_md_path}")
    logger.success(f"   Per-Page Markdown: {settings.markdown_dir}")
    logger.success(f"   JSON: {json_path}")
    
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
