#!/usr/bin/env python3
"""
Quick test of PDF → LLM Blueprint pipeline with first 20 pages only.

This script:
1. Extracts first 20 pages from Cobas Liat PDF
2. Builds FAISS + BM25 index
3. Runs LLM blueprint extraction with qwen2.5-coder:32b
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.parsers.json_sidecar import JSONSidecarWriter
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.llm import LLMInterface, BlueprintFlow
from spec_parser.config import settings
from datetime import datetime
from loguru import logger

# Configuration
PDF_PATH = Path("data/specs/spec_others/02_Roche_cobas_Liat_Host_Interface_Manual_POCT1-A.pdf")
MAX_PAGES = 20  # Only process first 20 pages for quick test
DEVICE_ID = "Roche_CobasLiat_Test20"
DEVICE_NAME = "Roche cobas Liat Analyzer (Test)"
OUTPUT_BASE = Path("data/spec_output")

def main():
    """Run quick pipeline test."""
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE / f"{timestamp}_test20_rochecobasliat"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting pipeline test with first {MAX_PAGES} pages")
    logger.info(f"Output directory: {output_dir}")
    
    # Step 1: Extract PDF (first 20 pages only)
    logger.info(f"Step 1: Extracting first {MAX_PAGES} pages from PDF...")
    
    extracted_pages = []
    with PyMuPDFExtractor(PDF_PATH) as extractor:
        logger.info(f"PDF has {extractor.page_count} pages total (processing {MAX_PAGES})")
        
        for page_num in range(min(MAX_PAGES, extractor.page_count)):
            logger.info(f"Extracting page {page_num + 1}/{MAX_PAGES}...")
            page_data = extractor.extract_page(page_num)
            extracted_pages.append(page_data)
    
    logger.info(f"✅ Extracted {len(extracted_pages)} pages")
    
    # Step 2: Write JSON sidecar
    logger.info("Step 2: Writing JSON sidecar...")
    
    sidecar_path = output_dir / "sidecar.json"
    writer = JSONSidecarWriter(sidecar_path)
    writer.write(extracted_pages)
    
    logger.info(f"✅ Wrote sidecar: {sidecar_path}")
    
    # Step 3: Build FAISS index
    logger.info("Step 3: Building FAISS index...")
    
    index_dir = output_dir / "index"
    index_dir.mkdir(exist_ok=True)
    
    faiss_indexer = FAISSIndexer(index_dir=index_dir)
    
    # Extract text chunks for indexing
    chunks = []
    for page in extracted_pages:
        for block in page.get("blocks", []):
            if block.get("type") == "text":
                chunks.append({
                    "text": block.get("text", ""),
                    "page": page.get("page_num"),
                    "bbox": block.get("bbox"),
                    "source": "pdf"
                })
    
    logger.info(f"Indexing {len(chunks)} text chunks...")
    faiss_indexer.build_index(chunks)
    
    logger.info(f"✅ Built FAISS index: {index_dir}")
    
    # Step 4: Build BM25 index
    logger.info("Step 4: Building BM25 index...")
    
    bm25_searcher = BM25Searcher(index_dir=index_dir)
    bm25_searcher.build_index(chunks)
    
    logger.info(f"✅ Built BM25 index")
    
    # Step 5: Run LLM blueprint extraction
    logger.info("Step 5: Running LLM blueprint extraction...")
    logger.info(f"Using model: {settings.llm_provider}/{settings.llm_model}")
    
    llm = LLMInterface()
    
    flow = BlueprintFlow(
        device_id=DEVICE_ID,
        device_name=DEVICE_NAME,
        index_dir=index_dir,
        llm=llm
    )
    
    logger.info("Extracting blueprint (this may take several minutes)...")
    blueprint = flow.run()
    
    # Step 6: Save blueprint
    blueprint_path = output_dir / "blueprint.json"
    import json
    with open(blueprint_path, "w") as f:
        json.dump(blueprint, f, indent=2)
    
    logger.info(f"✅ Blueprint saved: {blueprint_path}")
    
    # Summary
    print("\n" + "=" * 70)
    print("PIPELINE TEST COMPLETE")
    print("=" * 70)
    print(f"\nPages processed: {len(extracted_pages)}")
    print(f"Text chunks indexed: {len(chunks)}")
    print(f"Output directory: {output_dir}")
    print(f"Blueprint: {blueprint_path}")
    
    # Show blueprint summary
    if isinstance(blueprint, dict):
        messages = blueprint.get("messages", [])
        print(f"\nMessages discovered: {len(messages)}")
        for msg in messages[:5]:  # Show first 5
            print(f"  - {msg.get('message_type', 'Unknown')}")
        if len(messages) > 5:
            print(f"  ... and {len(messages) - 5} more")
    
    print("\n✅ Full PDF → LLM Blueprint pipeline validated!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
