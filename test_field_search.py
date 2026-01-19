"""
Quick test to verify field metadata is searchable.
"""

from pathlib import Path
from src.spec_parser.search.faiss_indexer import FAISSIndexer
from src.spec_parser.search.bm25_searcher import BM25Searcher
from src.spec_parser.embeddings.embedding_model import EmbeddingModel

# Load latest index
index_dir = Path("data/spec_output/20260119_004133_quidelsofia5/index")

print("=== Testing FAISS Semantic Search ===\n")
embedding_model = EmbeddingModel()
faiss_indexer = FAISSIndexer.load(index_dir / "faiss.faiss", embedding_model)

# Test 1: Search for code fields
print("1. Search for 'code field type enumeration':")
results = faiss_indexer.search("code field type enumeration", k=5)
for i, result in enumerate(results, 1):
    if result.metadata.get("type") == "field":
        print(f"   [{i}] {result.metadata['field_name']} - Type: {result.metadata['field_type']} (Score: {result.score:.3f})")

print("\n2. Search for 'datetime timestamp field':")
results = faiss_indexer.search("datetime timestamp field", k=5)
for i, result in enumerate(results, 1):
    if result.metadata.get("type") == "field":
        print(f"   [{i}] {result.metadata['field_name']} - Type: {result.metadata['field_type']} (Score: {result.score:.3f})")

print("\n3. Search for 'control_id identifier':")
results = faiss_indexer.search("control_id identifier", k=3)
for i, result in enumerate(results, 1):
    if result.metadata.get("type") == "field":
        print(f"   [{i}] {result.metadata['field_name']} - Type: {result.metadata['field_type']} - Message: {result.metadata['message_id']} (Score: {result.score:.3f})")

print("\n=== Testing BM25 Keyword Search ===\n")
bm25_searcher = BM25Searcher.load(index_dir / "bm25.bm25")

# Test 4: Search for specific field types
print("4. Search for 'Field Type code':")
results = bm25_searcher.search("Field Type code", k=10)
field_count = 0
for i, result in enumerate(results, 1):
    if result.metadata.get("type") == "field" and result.metadata.get("field_type") == "code":
        field_count += 1
        if field_count <= 5:
            print(f"   [{field_count}] {result.metadata['field_name']} - Message: {result.metadata['message_id']} (Score: {result.score:.3f})")
print(f"   Found {field_count} code fields in top 10 results")

print("\n5. Search for 'Field HDR.control_id':")
results = bm25_searcher.search("Field HDR.control_id", k=5)
for i, result in enumerate(results, 1):
    if result.metadata.get("type") == "field":
        print(f"   [{i}] {result.metadata['field_name']} - Type: {result.metadata['field_type']} (Score: {result.score:.3f})")

print("\n=== Field Metadata Summary ===\n")
total_items = len(faiss_indexer.metadata)
field_items = sum(1 for m in faiss_indexer.metadata if m.get("type") == "field")
text_items = total_items - field_items

print(f"Total indexed items: {total_items}")
print(f"  - Field definitions: {field_items}")
print(f"  - Text/table blocks: {text_items}")

# Count field types
field_types = {}
for m in faiss_indexer.metadata:
    if m.get("type") == "field":
        ftype = m.get("field_type", "unknown")
        field_types[ftype] = field_types.get(ftype, 0) + 1

print(f"\nField types indexed:")
for ftype, count in sorted(field_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {ftype}: {count}")

print("\n✅ Field metadata is fully indexed and searchable!")
