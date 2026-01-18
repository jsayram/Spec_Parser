"""
Hybrid search combining semantic (FAISS) and keyword (BM25) search.

Provides best of both worlds: semantic understanding + exact keyword matching.
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from spec_parser.search.faiss_indexer import FAISSIndexer, SearchResult
from spec_parser.search.bm25_searcher import BM25Searcher


class HybridSearcher:
    """
    Hybrid search combining FAISS (semantic) and BM25 (keyword) search.
    
    Features:
    - Parallel search in both indices
    - Score normalization and fusion
    - Reciprocal Rank Fusion (RRF) for combining results
    - Full provenance preservation
    """
    
    def __init__(
        self,
        faiss_indexer: FAISSIndexer,
        bm25_searcher: BM25Searcher,
        faiss_weight: float = 0.6,
        bm25_weight: float = 0.4
    ):
        """
        Initialize hybrid searcher.
        
        Args:
            faiss_indexer: FAISS semantic search index
            bm25_searcher: BM25 keyword search index
            faiss_weight: Weight for semantic search (0-1)
            bm25_weight: Weight for keyword search (0-1)
        """
        self.faiss = faiss_indexer
        self.bm25 = bm25_searcher
        self.faiss_weight = faiss_weight
        self.bm25_weight = bm25_weight
        
        logger.info(
            f"Created hybrid searcher "
            f"(FAISS: {faiss_weight}, BM25: {bm25_weight})"
        )
    
    def search(
        self,
        query: str,
        k: int = 10,
        mode: str = "hybrid",
        filter_fn: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using hybrid approach.
        
        Args:
            query: Query text
            k: Number of results to return
            mode: Search mode ('hybrid', 'semantic', 'keyword')
            filter_fn: Optional filter function(metadata) -> bool
            
        Returns:
            List of results with scores and metadata
        """
        if mode == "semantic":
            return self._search_semantic(query, k, filter_fn)
        elif mode == "keyword":
            return self._search_keyword(query, k, filter_fn)
        elif mode == "hybrid":
            return self._search_hybrid(query, k, filter_fn)
        else:
            raise ValueError(
                f"Invalid mode: {mode}. Use 'hybrid', 'semantic', or 'keyword'"
            )
    
    def _search_semantic(
        self,
        query: str,
        k: int,
        filter_fn: Optional[callable]
    ) -> List[Dict[str, Any]]:
        """Semantic-only search"""
        results = self.faiss.search(query, k, filter_fn)
        
        return [
            {
                "text": r.text,
                "score": r.score,
                "metadata": r.metadata,
                "rank": r.rank,
                "source": "semantic"
            }
            for r in results
        ]
    
    def _search_keyword(
        self,
        query: str,
        k: int,
        filter_fn: Optional[callable]
    ) -> List[Dict[str, Any]]:
        """Keyword-only search"""
        results = self.bm25.search(query, k, filter_fn)
        
        for r in results:
            r["source"] = "keyword"
        
        return results
    
    def _search_hybrid(
        self,
        query: str,
        k: int,
        filter_fn: Optional[callable]
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search using Reciprocal Rank Fusion (RRF).
        
        RRF formula: score = sum(1 / (rank + k)) for each source
        where k=60 is a constant
        """
        # Get results from both indices (request more for fusion)
        search_k = k * 3
        
        faiss_results = self.faiss.search(query, search_k, filter_fn)
        bm25_results = self.bm25.search(query, search_k, filter_fn)
        
        # Build citation -> result mapping
        # Use citation as unique identifier (or text if no citation)
        result_map: Dict[str, Dict[str, Any]] = {}
        
        # RRF constant
        rrf_k = 60
        
        # Add FAISS results with RRF scores
        for result in faiss_results:
            citation = result.metadata.get("citation", result.text[:50])
            
            rrf_score = self.faiss_weight / (result.rank + rrf_k)
            
            result_map[citation] = {
                "text": result.text,
                "metadata": result.metadata,
                "scores": {
                    "semantic": result.score,
                    "keyword": 0.0,
                    "rrf": rrf_score
                },
                "ranks": {
                    "semantic": result.rank,
                    "keyword": None
                },
                "source": ["semantic"]
            }
        
        # Add BM25 results with RRF scores
        for result in bm25_results:
            citation = result["metadata"].get("citation", result["text"][:50])
            
            rrf_score = self.bm25_weight / (result["rank"] + rrf_k)
            
            if citation in result_map:
                # Already have FAISS result, add BM25 score
                result_map[citation]["scores"]["keyword"] = result["score"]
                result_map[citation]["scores"]["rrf"] += rrf_score
                result_map[citation]["ranks"]["keyword"] = result["rank"]
                result_map[citation]["source"].append("keyword")
            else:
                # New result from BM25 only
                result_map[citation] = {
                    "text": result["text"],
                    "metadata": result["metadata"],
                    "scores": {
                        "semantic": 0.0,
                        "keyword": result["score"],
                        "rrf": rrf_score
                    },
                    "ranks": {
                        "semantic": None,
                        "keyword": result["rank"]
                    },
                    "source": ["keyword"]
                }
        
        # Sort by RRF score
        sorted_results = sorted(
            result_map.values(),
            key=lambda x: x["scores"]["rrf"],
            reverse=True
        )
        
        # Take top k and add final rank
        final_results = []
        for rank, result in enumerate(sorted_results[:k], 1):
            result["rank"] = rank
            result["score"] = result["scores"]["rrf"]
            result["source"] = "+".join(result["source"])
            final_results.append(result)
        
        logger.info(
            f"Hybrid search: {len(final_results)} results "
            f"(FAISS: {len(faiss_results)}, BM25: {len(bm25_results)})"
        )
        
        return final_results
    
    def format_results(
        self,
        results: List[Dict[str, Any]],
        show_scores: bool = True
    ) -> str:
        """
        Format search results as human-readable text.
        
        Args:
            results: Search results
            show_scores: Include scores in output
            
        Returns:
            Formatted results string
        """
        if not results:
            return "No results found."
        
        lines = [f"Found {len(results)} results:\n"]
        
        for result in results:
            metadata = result["metadata"]
            text = result["text"]
            
            # Format result header
            header = f"[{result['rank']}] "
            
            if "citation" in metadata:
                header += f"{metadata['citation']} "
            
            if "page" in metadata:
                header += f"(Page {metadata['page']}) "
            
            if show_scores:
                header += f"[score: {result['score']:.4f}, source: {result['source']}]"
            
            lines.append(header)
            
            # Format text preview
            text_preview = text[:200] + "..." if len(text) > 200 else text
            lines.append(f"  {text_preview}\n")
        
        return "\n".join(lines)
