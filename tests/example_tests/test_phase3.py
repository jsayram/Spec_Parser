#!/usr/bin/env python
"""
Simple CLI to test Phase 3 search pipeline.

Usage:
    # Build local (per-PDF) index
    python test_phase3.py --local <spec_output_dir> [query]
    
    # Build/update master index (across all PDFs)
    python test_phase3.py --master <spec_output_dir> [query]
"""

import sys
from pathlib import Path
import json
from typing import List
from loguru import logger

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.search.hybrid_search import HybridSearcher
from spec_parser.search.master_index import MasterIndexManager
from spec_parser.config import settings
from spec_parser.utils.logger import setup_logger


def build_indices(spec_output_dir: Path):
    """
    Build search indices from Phase 2 output.
    
    Args:
        spec_output_dir: Directory containing Phase 2 output
                         (markdown/, json/, etc.)
    """
    logger.info(f"Building search indices from: {spec_output_dir}")
    
    # Find JSON sidecar
    json_dir = spec_output_dir / "json"
    json_files = list(json_dir.glob("*.json"))
    
    if not json_files:
        logger.error(f"No JSON files found in {json_dir}")
        sys.exit(1)
    
    json_file = json_files[0]
    logger.info(f"Loading JSON: {json_file.name}")
    
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract texts and metadata from JSON
    texts = []
    metadatas = []
    
    for page_data in data["pages"]:
        page_num = page_data["page"]
        
        # Add markdown content
        if page_data.get("markdown"):
            texts.append(page_data["markdown"])
            metadatas.append({
                "page": page_num,
                "type": "markdown",
                "citation": f"p{page_num}_md",
                "text": page_data["markdown"]
            })
        
        # Add text blocks
        for block in page_data.get("blocks", []):
            if block.get("type") == "text" and block.get("content"):
                texts.append(block["content"])
                metadatas.append({
                    "page": page_num,
                    "type": "text_block",
                    "citation": block.get("citation", f"p{page_num}_txt"),
                    "bbox": block.get("bbox"),
                    "text": block["content"]
                })
        
        # Add OCR results
        for ocr in page_data.get("ocr", []):
            if ocr.get("text"):
                texts.append(ocr["text"])
                metadatas.append({
                    "page": page_num,
                    "type": "ocr",
                    "citation": ocr.get("citation", f"p{page_num}_ocr"),
                    "bbox": ocr.get("bbox"),
                    "confidence": ocr.get("confidence"),
                    "text": ocr["text"]
                })
    
    logger.info(f"Extracted {len(texts)} text chunks from {data['total_pages']} pages")
    
    # Initialize embedding model
    logger.info("Loading embedding model...")
    model_cache = settings.models_dir if settings.models_dir else None
    embedding_model = EmbeddingModel(cache_dir=model_cache)
    
    # Build FAISS index
    logger.info("Building FAISS index...")
    index_dir = spec_output_dir / "index"
    index_dir.mkdir(exist_ok=True)
    
    faiss_index_path = index_dir / "faiss_index"
    faiss_indexer = FAISSIndexer(embedding_model, faiss_index_path)
    faiss_indexer.add_texts(texts, metadatas)
    faiss_indexer.save()
    
    # Build BM25 index
    logger.info("Building BM25 index...")
    bm25_index_path = index_dir / "bm25_index"
    bm25_searcher = BM25Searcher(bm25_index_path)
    bm25_searcher.add_texts(texts, metadatas)
    bm25_searcher.save()
    
    logger.success(f"✅ Indices built successfully!")
    logger.success(f"   FAISS: {faiss_indexer.size} vectors")
    logger.success(f"   BM25: {bm25_searcher.size} documents")
    logger.success(f"   Location: {index_dir}")
    
    return index_dir


def search_indices(index_dir: Path, query: str, k: int = 5):
    """
    Search built indices.
    
    Args:
        index_dir: Directory containing indices
        query: Search query
        k: Number of results
    """
    logger.info(f"Searching for: '{query}'")
    
    # Load embedding model
    model_cache = settings.models_dir if settings.models_dir else None
    embedding_model = EmbeddingModel(cache_dir=model_cache)
    
    # Load indices
    faiss_index_path = index_dir / "faiss_index"
    bm25_index_path = index_dir / "bm25_index"
    
    faiss_indexer = FAISSIndexer.load(faiss_index_path, embedding_model)
    bm25_searcher = BM25Searcher.load(bm25_index_path)
    
    # Create hybrid searcher
    hybrid = HybridSearcher(faiss_indexer, bm25_searcher)
    
    # Perform searches
    print("\n" + "="*80)
    print("SEMANTIC SEARCH (FAISS)")
    print("="*80)
    semantic_results = hybrid.search(query, k, mode="semantic")
    print(hybrid.format_results(semantic_results))
    
    print("\n" + "="*80)
    print("KEYWORD SEARCH (BM25)")
    print("="*80)
    keyword_results = hybrid.search(query, k, mode="keyword")
    print(hybrid.format_results(keyword_results))
    
    print("\n" + "="*80)
    print("HYBRID SEARCH (FAISS + BM25)")
    print("="*80)
    hybrid_results = hybrid.search(query, k, mode="hybrid")
    print(hybrid.format_results(hybrid_results))


def build_master_index(spec_output_dirs: List[Path], force_reindex: bool = False):
    """
    Build or update master index across multiple PDFs.
    
    Args:
        spec_output_dirs: List of Phase 2 output directories
        force_reindex: Force re-indexing even if already indexed
    """
    logger.info(f"Building master index from {len(spec_output_dirs)} PDFs...")
    
    # Initialize embedding model
    model_cache = settings.models_dir if settings.models_dir else None
    embedding_model = EmbeddingModel(cache_dir=model_cache)
    
    # Create master index directory
    master_index_dir = settings.spec_output_dir / "_master_index"
    master_index_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize master index manager
    manager = MasterIndexManager(master_index_dir, embedding_model)
    
    # Add each PDF to master index
    total_chunks = 0
    for spec_dir in spec_output_dirs:
        # Find JSON sidecar
        json_dir = spec_dir / "json"
        json_files = list(json_dir.glob("*.json"))
        
        if not json_files:
            logger.warning(f"No JSON found in {spec_dir.name}, skipping")
            continue
        
        json_file = json_files[0]
        pdf_name = json_file.stem  # e.g., "04_Abbott_InfoHQ"
        
        # Add to master index
        chunks_added = manager.add_pdf(pdf_name, json_file, force_reindex)
        total_chunks += chunks_added
    
    # Save master index
    manager.save()
    
    # Print statistics
    stats = manager.get_stats()
    logger.success(f"\n✅ Master Index Built!")
    logger.success(f"   Location: {master_index_dir}")
    logger.success(f"   Total PDFs: {stats['total_pdfs']}")
    logger.success(f"   Total Vectors: {stats['total_vectors']}")
    logger.success(f"   Total Documents: {stats['total_documents']}")
    logger.success(f"   Chunks Added: {total_chunks}")
    
    return master_index_dir


def search_master_index(master_index_dir: Path, query: str, k: int = 10):
    """
    Search master index across all PDFs.
    
    Args:
        master_index_dir: Directory containing master index
        query: Search query
        k: Number of results
    """
    logger.info(f"Searching master index for: '{query}'")
    
    # Load embedding model
    model_cache = settings.models_dir if settings.models_dir else None
    embedding_model = EmbeddingModel(cache_dir=model_cache)
    
    # Load master indices
    faiss_path = master_index_dir / "faiss_index"
    bm25_path = master_index_dir / "bm25_index"
    
    faiss_indexer = FAISSIndexer.load(faiss_path, embedding_model)
    bm25_searcher = BM25Searcher.load(bm25_path)
    
    # Create hybrid searcher
    hybrid = HybridSearcher(faiss_indexer, bm25_searcher)
    
    # Search
    print("\n" + "="*80)
    print("MASTER INDEX SEARCH (All PDFs)")
    print("="*80)
    results = hybrid.search(query, k, mode="hybrid")
    print(hybrid.format_results(results))


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  # Build local index (per-PDF)")
        print("  python test_phase3.py --local <spec_output_dir> [query]")
        print("\n  # Build/update master index (all PDFs)")
        print("  python test_phase3.py --master <spec_output_dir> [query]")
        print("\n  # Build master from multiple PDFs")
        print("  python test_phase3.py --master <dir1> <dir2> <dir3> [query]")
        print("\nExamples:")
        print("  # Build local index")
        print("  python test_phase3.py --local data/spec_output/20260118_013952_04AbbottInfoHQ/")
        print("\n  # Build master index from all processed PDFs")
        print("  python test_phase3.py --master data/spec_output/*/")
        print("\n  # Search master index")
        print("  python test_phase3.py --master data/spec_output/*/ 'POCT1 calibration'")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode not in ["--local", "--master"]:
        logger.error(f"Invalid mode: {mode}. Use --local or --master")
        sys.exit(1)
    
    # Parse directories
    spec_output_dirs = []
    query = None
    
    for arg in sys.argv[2:]:
        path = Path(arg)
        if path.exists() and path.is_dir():
            spec_output_dirs.append(path)
        else:
            # Assume it's part of the query
            if query:
                query += " " + arg
            else:
                query = arg
    
    if not spec_output_dirs:
        logger.error("No valid directories provided")
        sys.exit(1)
    
    if mode == "--local":
        # Local index mode (per-PDF)
        if len(spec_output_dirs) > 1:
            logger.warning("--local mode only processes first directory")
        
        spec_dir = spec_output_dirs[0]
        logger.info(f"Building local index for: {spec_dir.name}")
        
        # Check if indices exist
        index_dir = spec_dir / "index"
        indices_exist = (
            (index_dir / "faiss_index.faiss").exists() and
            (index_dir / "bm25_index.bm25.pkl").exists()
        )
        
        if not indices_exist:
            logger.info("Indices not found, building...")
            index_dir = build_indices(spec_dir)
        else:
            logger.info(f"Using existing indices: {index_dir}")
        
        # Search if query provided
        if query:
            search_indices(index_dir, query)
    
    elif mode == "--master":
        # Master index mode (cross-PDF)
        master_index_dir = settings.spec_output_dir / "_master_index"
        
        # Build/update master index
        if not query:
            # Build mode
            build_master_index(spec_output_dirs)
        else:
            # Check if master index exists
            if not (master_index_dir / "faiss_index.faiss").exists():
                logger.info("Master index not found, building...")
                build_master_index(spec_output_dirs)
            
            # Search master index
            search_master_index(master_index_dir, query)


if __name__ == "__main__":
    setup_logger()
    main()
