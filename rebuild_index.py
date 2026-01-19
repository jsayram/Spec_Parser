#!/usr/bin/env python3
"""Rebuild FAISS and BM25 indexes with text in metadata."""
from pathlib import Path
import json
from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from loguru import logger

# Paths
index_dir = Path("data/spec_output/20260119_010845_rochecobasliat/index")
doc_path = Path("data/spec_output/20260119_010845_rochecobasliat/json/document.json")

logger.info("Loading document...")
with open(doc_path) as f:
    doc_data = json.load(f)

# Build texts and metadatas
texts = []
metadatas = []
for page_data in doc_data["pages"]:
    page_num = page_data["page"]
    for block in page_data.get("blocks", []):
        text_content = block.get("content") or block.get("markdown_table")
        if text_content:
            texts.append(text_content)
            metadatas.append({
                "page": page_num,
                "bbox": block.get("bbox", []),
                "type": block.get("type", "unknown")
            })

logger.info(f"Found {len(texts)} text blocks")

# Rebuild FAISS index
logger.info("Rebuilding FAISS index...")
embedding_model = EmbeddingModel()
faiss_indexer = FAISSIndexer(embedding_model, index_dir / "faiss")
faiss_indexer.add_texts(texts, metadatas)
faiss_indexer.save()
logger.info("FAISS index rebuilt!")

# Rebuild BM25 index
logger.info("Rebuilding BM25 index...")
bm25_searcher = BM25Searcher(index_path=index_dir / "bm25")
bm25_searcher.add_texts(texts, metadatas)
bm25_searcher.save()
logger.info("BM25 index rebuilt!")

print("\n✅ Indexes rebuilt successfully!")
