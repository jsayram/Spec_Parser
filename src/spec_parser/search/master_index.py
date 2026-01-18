"""
Master index manager for cross-PDF search.

Maintains a universal index across all processed PDFs with manifest tracking.
Supports incremental updates, provenance tracking, and multi-document search.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from loguru import logger

from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.exceptions import ValidationError


class IndexManifest:
    """
    Tracks which PDFs are indexed in the master index.
    
    Enables incremental updates and version tracking.
    """
    
    def __init__(self, manifest_path: Path):
        """
        Initialize manifest.
        
        Args:
            manifest_path: Path to manifest JSON file
        """
        self.manifest_path = manifest_path
        self.documents: Dict[str, Dict[str, Any]] = {}
        
        if manifest_path.exists():
            self._load()
    
    def _load(self) -> None:
        """Load manifest from disk"""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.documents = data.get("documents", {})
        
        logger.info(f"Loaded manifest with {len(self.documents)} documents")
    
    def save(self) -> None:
        """Save manifest to disk"""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "total_documents": len(self.documents),
            "documents": self.documents
        }
        
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved manifest: {len(self.documents)} documents")
    
    def add_document(
        self,
        pdf_name: str,
        json_path: Path,
        chunk_count: int
    ) -> None:
        """
        Add or update document in manifest.
        
        Args:
            pdf_name: Name of PDF (e.g., "04_Abbott_InfoHQ")
            json_path: Path to JSON sidecar
            chunk_count: Number of text chunks indexed
        """
        self.documents[pdf_name] = {
            "json_path": str(json_path),
            "chunk_count": chunk_count,
            "indexed_at": datetime.now().isoformat(),
            "status": "indexed"
        }
        
        logger.info(f"Added to manifest: {pdf_name} ({chunk_count} chunks)")
    
    def is_indexed(self, pdf_name: str) -> bool:
        """Check if PDF is already indexed"""
        return pdf_name in self.documents
    
    def get_document_info(self, pdf_name: str) -> Optional[Dict[str, Any]]:
        """Get document info from manifest"""
        return self.documents.get(pdf_name)
    
    def list_documents(self) -> List[str]:
        """List all indexed document names"""
        return list(self.documents.keys())


class MasterIndexManager:
    """
    Manages universal master index across all PDFs.
    
    Features:
    - Incremental updates (add PDFs without rebuilding)
    - Manifest tracking (which PDFs are indexed)
    - Cross-PDF search with provenance
    - Supports both FAISS (semantic) and BM25 (keyword) indices
    """
    
    def __init__(
        self,
        master_index_dir: Path,
        embedding_model: EmbeddingModel
    ):
        """
        Initialize master index manager.
        
        Args:
            master_index_dir: Directory for master index files
            embedding_model: Embedding model for FAISS
        """
        self.master_index_dir = Path(master_index_dir)
        self.master_index_dir.mkdir(parents=True, exist_ok=True)
        
        self.embedding_model = embedding_model
        
        # Paths
        self.faiss_path = self.master_index_dir / "faiss_index"
        self.bm25_path = self.master_index_dir / "bm25_index"
        self.manifest_path = self.master_index_dir / "index_manifest.json"
        
        # Manifest
        self.manifest = IndexManifest(self.manifest_path)
        
        # Indices
        self.faiss_indexer: Optional[FAISSIndexer] = None
        self.bm25_searcher: Optional[BM25Searcher] = None
        
        # Load existing indices if available
        self._load_indices()
        
        logger.info(f"Master index directory: {master_index_dir}")
    
    def _load_indices(self) -> None:
        """Load existing indices if they exist"""
        # Load FAISS
        if self.faiss_path.with_suffix(".faiss").exists():
            self.faiss_indexer = FAISSIndexer.load(
                self.faiss_path,
                self.embedding_model
            )
            logger.info(f"Loaded existing FAISS index: {self.faiss_indexer.size} vectors")
        else:
            self.faiss_indexer = FAISSIndexer(
                self.embedding_model,
                self.faiss_path
            )
            logger.info("Created new FAISS index")
        
        # Load BM25
        if self.bm25_path.with_suffix(".bm25.pkl").exists():
            self.bm25_searcher = BM25Searcher.load(self.bm25_path)
            logger.info(f"Loaded existing BM25 index: {self.bm25_searcher.size} documents")
        else:
            self.bm25_searcher = BM25Searcher(self.bm25_path)
            logger.info("Created new BM25 index")
    
    def add_pdf(
        self,
        pdf_name: str,
        json_sidecar_path: Path,
        force_reindex: bool = False
    ) -> int:
        """
        Add PDF to master index (or skip if already indexed).
        
        Args:
            pdf_name: Name of PDF (e.g., "04_Abbott_InfoHQ")
            json_sidecar_path: Path to JSON sidecar
            force_reindex: Force re-indexing even if already indexed
            
        Returns:
            Number of chunks added
        """
        # Check if already indexed
        if self.manifest.is_indexed(pdf_name) and not force_reindex:
            logger.info(f"PDF already indexed: {pdf_name} (skipping)")
            return 0
        
        # Load JSON sidecar
        if not json_sidecar_path.exists():
            raise ValidationError(f"JSON sidecar not found: {json_sidecar_path}")
        
        with open(json_sidecar_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract text chunks with metadata
        texts = []
        metadatas = []
        
        for page_data in data["pages"]:
            page_num = page_data["page"]
            
            # Add text blocks (check both "content" and "text" fields)
            for block in page_data["blocks"]:
                if block["type"] == "text":
                    # JSON stores as "content", fallback to "text"
                    text = block.get("content") or block.get("text")
                    if text and len(text) > 10:  # Skip tiny fragments
                        texts.append(text)
                        metadatas.append({
                            "pdf_name": pdf_name,
                            "page": page_num,
                            "type": "text",
                            "bbox": block.get("bbox"),
                            "citation": block.get("citation"),
                            "text": text
                        })
            
            # Add OCR results (skip tiny fragments)
            for ocr in page_data.get("ocr", []):
                text = ocr.get("text", "")
                if text and len(text) > 20:  # OCR needs more chars to be useful
                    texts.append(text)
                    metadatas.append({
                        "pdf_name": pdf_name,
                        "page": page_num,
                        "type": "ocr",
                        "bbox": ocr.get("bbox"),
                        "citation": ocr.get("citation"),
                        "confidence": ocr.get("confidence"),
                        "text": text
                    })
            
            # Add page markdown as a chunk (contains structured content)
            page_markdown = page_data.get("markdown", "")
            # Clean markdown: remove citation section (noise for LLM)
            if "## Citations" in page_markdown:
                page_markdown = page_markdown.split("## Citations")[0].strip()
            
            if page_markdown and len(page_markdown) > 50:
                texts.append(page_markdown)
                metadatas.append({
                    "pdf_name": pdf_name,
                    "page": page_num,
                    "type": "markdown",
                    "citation": f"p{page_num}_md",
                    "text": page_markdown
                })
        
        if not texts:
            logger.warning(f"No text found in {pdf_name}")
            return 0
        
        # Add to indices
        logger.info(f"Adding {len(texts)} chunks from {pdf_name} to master index...")
        self.faiss_indexer.add_texts(texts, metadatas)
        self.bm25_searcher.add_texts(texts, metadatas)
        
        # Update manifest
        self.manifest.add_document(pdf_name, json_sidecar_path, len(texts))
        
        logger.success(f"Added {pdf_name}: {len(texts)} chunks")
        
        return len(texts)
    
    def save(self) -> None:
        """Save all indices and manifest"""
        self.faiss_indexer.save()
        self.bm25_searcher.save()
        self.manifest.save()
        
        logger.success(
            f"Saved master index: "
            f"{self.faiss_indexer.size} vectors, "
            f"{len(self.manifest.documents)} PDFs"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get master index statistics"""
        return {
            "total_vectors": self.faiss_indexer.size,
            "total_documents": self.bm25_searcher.size,
            "total_pdfs": len(self.manifest.documents),
            "indexed_pdfs": self.manifest.list_documents(),
            "index_dir": str(self.master_index_dir)
        }
