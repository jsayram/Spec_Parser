"""Rebuild FAISS and BM25 indices from JSON sidecar with correct content."""

from pathlib import Path
from loguru import logger

from src.spec_parser.parsers.json_sidecar import JSONSidecarWriter
from src.spec_parser.search.faiss_indexer import FAISSIndexer
from src.spec_parser.search.bm25_searcher import BM25Searcher
from src.spec_parser.embeddings.embedding_model import EmbeddingModel


def rebuild_index(spec_dir: Path):
    """Rebuild search indices from JSON sidecar.
    
    Args:
        spec_dir: Path to spec output directory (e.g., 20260119_165832_rochecobasliatfull_v2)
    """
    json_path = spec_dir / "json" / "document.json"
    index_dir = spec_dir / "index"
    
    logger.info(f"Loading document from {json_path}")
    pages = JSONSidecarWriter.load_document(json_path)
    
    logger.info(f"Loaded {len(pages)} pages")
    
    # Collect all texts and metadata
    texts = []
    metadatas = []
    
    for page_bundle in pages:
        for block in page_bundle.blocks:
            # Extract text from different block types
            text_content = None
            
            if block.type == "text" and hasattr(block, 'content') and block.content:
                text_content = block.content
            elif block.type == "table" and hasattr(block, 'markdown_table') and block.markdown_table:
                text_content = block.markdown_table
            
            if text_content and len(text_content.strip()) > 0:
                texts.append(text_content)
                metadatas.append({
                    "page": page_bundle.page,
                    "bbox": block.bbox,
                    "type": block.type
                })
    
    logger.info(f"Extracted {len(texts)} text blocks")
    
    # Check page 115 specifically
    page_115_texts = [t for t, m in zip(texts, metadatas) if m["page"] == 115]
    logger.info(f"Page 115 has {len(page_115_texts)} indexed blocks")
    if page_115_texts:
        for i, text in enumerate(page_115_texts[:3]):
            logger.info(f"Page 115 block {i+1} preview: {text[:100]}...")
    
    # Rebuild FAISS index
    logger.info("Rebuilding FAISS index...")
    embedding_model = EmbeddingModel()
    faiss_indexer = FAISSIndexer(embedding_model, index_dir / "faiss.faiss")
    faiss_indexer.add_texts(texts, metadatas)
    faiss_indexer.save()
    logger.success(f"Saved FAISS index with {len(texts)} vectors")
    
    # Rebuild BM25 index
    logger.info("Rebuilding BM25 index...")
    bm25_searcher = BM25Searcher()
    bm25_searcher.add_texts(texts, metadatas)
    bm25_searcher.save(index_dir / "bm25.bm25.pkl")
    logger.success(f"Saved BM25 index with {len(texts)} docs")
    
    logger.success(f"Index rebuild complete: {index_dir}")


if __name__ == "__main__":
    spec_dir = Path("data/spec_output/20260119_165832_rochecobasliatfull_v2")
    rebuild_index(spec_dir)
