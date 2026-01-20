#!/usr/bin/env python3
"""
Check if the TOC block from page 115 is in the index.
"""

from pathlib import Path
import sys
import json

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from loguru import logger
from spec_parser.search import FAISSIndexer, BM25Searcher
from spec_parser.embeddings.embedding_model import EmbeddingModel


def main():
    # Load the document JSON
    doc_path = Path("data/spec_output/20260119_165832_rochecobasliatfull_v2/json/document.json")
    with open(doc_path) as f:
        data = json.load(f)
    
    # Find page 115, block 6
    page115 = [p for p in data['pages'] if p['page'] == 115]
    if not page115:
        logger.error("Page 115 not found!")
        return
    
    target_block = page115[0]['blocks'][6]
    target_text = target_block.get('content', '')
    
    logger.info(f"Target text from page 115, block 6:")
    logger.info(f"{target_text[:200]}...")
    logger.info(f"\nTotal length: {len(target_text)} chars")
    
    # Load index
    index_dir = Path("data/spec_output/20260119_165832_rochecobasliatfull_v2/index")
    
    logger.info("\nLoading BM25 index to check all indexed texts...")
    bm25_searcher = BM25Searcher.load(index_dir / "bm25")
    
    # Check if target text is in the index
    logger.info(f"\nSearching through {len(bm25_searcher.metadata)} indexed blocks...")
    
    found = False
    for i, meta in enumerate(bm25_searcher.metadata):
        text = meta.get('text', '')
        page = meta.get('page', 'unknown')
        
        # Skip empty texts
        if not text or len(text) < 10:
            continue
        
        # Check for exact match or substring
        if target_text in text or text in target_text:
            logger.info(f"\n✓ FOUND at index position {i}!")
            logger.info(f"  Page: {page}")
            logger.info(f"  Text length: {len(text)} chars")
            logger.info(f"  Text preview: {text[:200]}...")
            found = True
            break
        
        # Check for partial match with message names
        if page == 115 and any(msg in text for msg in ["ACK.R01", "DST.R01", "EOT.R01"]):
            logger.info(f"\n✓ Found page 115 block with messages at index {i}:")
            logger.info(f"  Text: {text[:300]}...")
            found = True
    
    if not found:
        logger.error("\n✗ Target text NOT FOUND in index!")
        logger.info("\nShowing all page 115 blocks in index:")
        for i, meta in enumerate(bm25_searcher.metadata):
            if meta.get('page') == 115:
                text = meta.get('text', '')
                logger.info(f"  Index {i}: {text[:100]}...")


if __name__ == "__main__":
    main()
