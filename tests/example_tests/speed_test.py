#!/usr/bin/env python
"""Test search speed without LLM."""

import time
from spec_parser.embeddings.embedding_model import EmbeddingModel
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.search.hybrid_search import HybridSearcher
from spec_parser.config import settings

# Load once (startup cost)
print('Loading index...')
t0 = time.time()
embedding_model = EmbeddingModel(cache_dir=settings.models_dir)
faiss_indexer = FAISSIndexer.load(
    settings.spec_output_dir / '_master_index/faiss_index', 
    embedding_model
)
bm25_searcher = BM25Searcher.load(
    settings.spec_output_dir / '_master_index/bm25_index'
)
hybrid = HybridSearcher(faiss_indexer, bm25_searcher)
print(f'Loaded in {time.time()-t0:.2f}s (one-time startup)\n')

# Test query speed
queries = [
    'POCT1 host interface', 
    'device calibration', 
    'Roche diagnostics', 
    'software version'
]

print(f'--- Query Speed Test ({len(queries)} queries) ---')
for query in queries:
    t0 = time.time()
    results = hybrid.search(query, k=5, mode='hybrid')
    elapsed_ms = (time.time() - t0) * 1000
    print(f'  "{query}": {elapsed_ms:.1f}ms -> {len(results)} results')

print('\n--- This is WITHOUT LLM - just retrieval! ---')
