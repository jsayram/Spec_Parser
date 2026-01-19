#!/usr/bin/env python3
"""Verify Roche cobas Liat extraction results."""

from src.spec_parser.utils.file_handler import read_json
from src.spec_parser.extractors.field_parser import parse_fields_from_document
from collections import Counter

doc = read_json('data/spec_output/20260119_010845_rochecobasliat/json/document.json')
print(f'Pages: {doc["total_pages"]}')

fields = parse_fields_from_document(doc)
print(f'\n✅ Extracted fields: {len(fields)}')

type_counts = Counter(f.field_type for f in fields)
print(f'\nField types: {dict(type_counts)}')

code_fields = [f for f in fields if f.field_type == 'code']
print(f'\nCode fields: {len(code_fields)}')
if code_fields:
    for f in code_fields:
        print(f'  - {f.field_name}')

print(f'\nSample fields:')
for f in fields:
    print(f'  - {f.field_name} ({f.field_type}) from {f.message_id} - Page {f.page}')

# Check indexing
import json
faiss_meta = json.load(open('data/spec_output/20260119_010845_rochecobasliat/index/faiss.metadata.json'))
print(f'\n✅ FAISS indexed: {len(faiss_meta)} items')

bm25_meta = json.load(open('data/spec_output/20260119_010845_rochecobasliat/index/bm25.bm25_metadata.json'))
print(f'✅ BM25 indexed: {len(bm25_meta)} items')

# Verify structure
print(f'\n=== VERIFICATION ===')
print(f'Expected: 4010 indexed (3996 text + 14 fields)')
print(f'Actual: {len(faiss_meta)} FAISS, {len(bm25_meta)} BM25')

if len(faiss_meta) == 4010 and len(bm25_meta) == 4010:
    print('✅ CORRECT - All files properly generated')
else:
    print('⚠️  MISMATCH - Check field extraction')
