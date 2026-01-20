#!/usr/bin/env python3
"""
Debug script to search FAISS/BM25 index and show results.
"""

from pathlib import Path
import sys
from loguru import logger

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from spec_parser.search import HybridSearcher, FAISSIndexer, BM25Searcher
from spec_parser.embeddings.embedding_model import EmbeddingModel


def main():
    # Index directory
    index_dir = Path("data/spec_output/20260119_165832_rochecobasliatfull_v2/index")
    
    if not index_dir.exists():
        logger.error(f"Index directory not found: {index_dir}")
        sys.exit(1)
    
    logger.info(f"Loading indices from {index_dir}")
    
    # Create embedding model
    logger.info("Loading embedding model...")
    embedding_model = EmbeddingModel(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        cache_dir="models"
    )
    
    # Load FAISS and BM25 indices
    faiss_indexer = FAISSIndexer.load(index_dir / "faiss", embedding_model)
    bm25_searcher = BM25Searcher.load(index_dir / "bm25")
    
    # Create hybrid searcher
    searcher = HybridSearcher(faiss_indexer, bm25_searcher)
    
    # Search query
    query = "table of contents ACK DST EOT EVS ESC HEL KPA OBS OPL REQ END"
    
    logger.info(f"\n{'='*80}")
    logger.info(f"QUERY: {query}")
    logger.info(f"{'='*80}\n")
    
    # Search all modes
    for mode in ["hybrid", "semantic", "keyword"]:
        logger.info(f"\n{'='*80}")
        logger.info(f"MODE: {mode.upper()}")
        logger.info(f"{'='*80}\n")
        
        results = searcher.search(query, k=10, mode=mode)
        
        for i, result in enumerate(results, 1):
            logger.info(f"\n--- Result #{i} ---")
            logger.info(f"Score: {result['score']:.4f}")
            logger.info(f"Source: {result.get('source', 'N/A')}")
            
            # Extract metadata
            metadata = result.get("metadata", {})
            page = metadata.get("page", "unknown")
            bbox = metadata.get("bbox", "unknown")
            source_type = metadata.get("source", "unknown")
            
            logger.info(f"Page: {page}")
            logger.info(f"Source Type: {source_type}")
            logger.info(f"Bbox: {bbox}")
            
            # Show text content (truncated if too long)
            text = result.get("text", "")
            if len(text) > 500:
                logger.info(f"Text (first 500 chars):\n{text[:500]}...")
            else:
                logger.info(f"Text:\n{text}")
            
            # Check if contains the key messages
            key_messages = ["ACK.R01", "DST.R01", "EOT.R01", "EVS.R01", "ESC.R01", 
                           "HEL.R01", "KPA.R01", "OBS.R01", "OPL.R01", "REQ.R01", "END.R01"]
            found_messages = [msg for msg in key_messages if msg in text]
            if found_messages:
                logger.info(f"✓ Contains messages: {', '.join(found_messages)}")
            else:
                logger.info("✗ No key messages found")
            
            # Check if looks like TOC
            toc_indicators = ["table of contents", "contents", "message type", "page number"]
            if any(indicator.lower() in text.lower() for indicator in toc_indicators):
                logger.info("✓ Contains TOC indicators")
            
            logger.info("-" * 80)
    
    logger.info(f"\n{'='*80}")
    logger.info("DEBUG COMPLETE")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()
