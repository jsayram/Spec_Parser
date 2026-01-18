#!/usr/bin/env python
"""
Search master index across all PDFs.

Usage:
    python search_master_index.py <query> [--mode semantic|keyword|hybrid] [--top-k N]
"""

import sys
from pathlib import Path
from loguru import logger

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.search.hybrid_search import HybridSearcher
from spec_parser.config import settings
from spec_parser.utils.logger import setup_logger


def search_master(query: str, mode: str = "hybrid", k: int = 10):
    """
    Search master index.
    
    Args:
        query: Search query
        mode: Search mode (semantic, keyword, hybrid)
        k: Number of results
    """
    # Find master index
    master_index_dir = settings.spec_output_dir / "_master_index"
    
    if not master_index_dir.exists():
        logger.error(f"Master index not found at: {master_index_dir}")
        logger.error("Build master index first with:")
        logger.error("  python test_phase3.py --master data/spec_output/*/")
        sys.exit(1)
    
    faiss_path = master_index_dir / "faiss_index"
    bm25_path = master_index_dir / "bm25_index"
    
    if not faiss_path.with_suffix(".faiss").exists():
        logger.error("Master index incomplete (FAISS missing)")
        sys.exit(1)
    
    # Load embedding model
    logger.info("Loading embedding model...")
    model_cache = settings.models_dir if settings.models_dir else None
    embedding_model = EmbeddingModel(cache_dir=model_cache)
    
    # Load indices
    logger.info("Loading master index...")
    faiss_indexer = FAISSIndexer.load(faiss_path, embedding_model)
    bm25_searcher = BM25Searcher.load(bm25_path)
    
    # Create hybrid searcher
    hybrid = HybridSearcher(faiss_indexer, bm25_searcher)
    
    # Search
    logger.info(f"Searching for: '{query}' (mode={mode}, k={k})")
    
    print("\n" + "="*80)
    print(f"MASTER INDEX SEARCH ({mode.upper()} mode)")
    print(f"Query: {query}")
    print(f"Index: {faiss_indexer.size} vectors across {bm25_searcher.size} documents")
    print("="*80)
    
    results = hybrid.search(query, k, mode=mode)
    
    if not results:
        print("\nNo results found.")
        return
    
    print(hybrid.format_results(results))
    
    # Show provenance breakdown
    pdf_counts = {}
    for result in results:
        # Handle both dict and SearchResult objects
        metadata = result.get("metadata") if isinstance(result, dict) else result.metadata
        pdf_name = metadata.get("pdf_name", "unknown")
        pdf_counts[pdf_name] = pdf_counts.get(pdf_name, 0) + 1
    
    print("\n" + "="*80)
    print("PROVENANCE BREAKDOWN")
    print("="*80)
    for pdf_name, count in sorted(pdf_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {pdf_name}: {count} results")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python search_master_index.py <query> [--mode MODE] [--top-k N]")
        print("\nOptions:")
        print("  --mode    Search mode: semantic, keyword, hybrid (default: hybrid)")
        print("  --top-k   Number of results (default: 10)")
        print("\nExamples:")
        print("  # Hybrid search (semantic + keyword)")
        print("  python search_master_index.py 'POCT1 calibration message'")
        print("\n  # Semantic search only")
        print("  python search_master_index.py 'device calibration' --mode semantic")
        print("\n  # Keyword search with more results")
        print("  python search_master_index.py 'OBX segment' --mode keyword --top-k 20")
        sys.exit(1)
    
    # Parse arguments
    query_parts = []
    mode = "hybrid"
    k = 10
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        if arg == "--mode":
            if i + 1 < len(sys.argv):
                mode = sys.argv[i + 1]
                i += 2
            else:
                logger.error("--mode requires an argument")
                sys.exit(1)
        elif arg == "--top-k":
            if i + 1 < len(sys.argv):
                try:
                    k = int(sys.argv[i + 1])
                    i += 2
                except ValueError:
                    logger.error("--top-k requires an integer")
                    sys.exit(1)
            else:
                logger.error("--top-k requires an argument")
                sys.exit(1)
        else:
            query_parts.append(arg)
            i += 1
    
    if not query_parts:
        logger.error("No query provided")
        sys.exit(1)
    
    query = " ".join(query_parts)
    
    if mode not in ["semantic", "keyword", "hybrid"]:
        logger.error(f"Invalid mode: {mode}. Use semantic, keyword, or hybrid")
        sys.exit(1)
    
    try:
        search_master(query, mode, k)
    except Exception as e:
        logger.exception(f"Search failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_logger()
    main()
