#!/usr/bin/env python
"""
Simple CLI to test Phase 3 search pipeline.

Usage:
    python test_phase3.py <spec_output_dir> <query>
"""

import sys
from pathlib import Path
import json
from loguru import logger

from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.search.hybrid_search import HybridSearcher
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


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python test_phase3.py <spec_output_dir> [query]")
        print("\nExamples:")
        print("  # Build indices only")
        print("  python test_phase3.py data/spec_output/20260118_000443_cobaliatsystemhimpoc/")
        print("\n  # Build indices and search")
        print("  python test_phase3.py data/spec_output/20260118_000443_cobaliatsystemhimpoc/ 'POCT1 message'")
        sys.exit(1)
    
    spec_output_dir = Path(sys.argv[1])
    
    if not spec_output_dir.exists():
        logger.error(f"Directory not found: {spec_output_dir}")
        sys.exit(1)
    
    # Check if indices exist
    index_dir = spec_output_dir / "index"
    indices_exist = (
        (index_dir / "faiss_index.faiss").exists() and
        (index_dir / "bm25_index.bm25.pkl").exists()
    )
    
    if not indices_exist:
        logger.info("Indices not found, building...")
        index_dir = build_indices(spec_output_dir)
    else:
        logger.info(f"Using existing indices: {index_dir}")
    
    # Search if query provided
    if len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        search_indices(index_dir, query)
    else:
        logger.info("No query provided. Indices ready for search!")
        print("\nTo search, run:")
        print(f"  python test_phase3.py {spec_output_dir} 'your query here'")


if __name__ == "__main__":
    setup_logger()
    main()
