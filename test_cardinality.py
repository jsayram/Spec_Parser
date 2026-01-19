#!/usr/bin/env python3
"""Test if cardinality is being extracted from field tables."""

import json
from pathlib import Path

json_path = Path('data/spec_output/20260119_005704_quidelsofia10/json/document.json')
doc = json.loads(json_path.read_text())

# Check first few pages for tables with cardinality headers
print("=== Looking for tables with cardinality columns ===")
for page in doc['pages'][:10]:
    for block in page.get('blocks', []):
        if block.get('type') == 'table':
            md = block.get('markdown', '')
            if any(word in md.lower() for word in ['rep', 'cardinality', 'occurs']):
                print(f"\nPage {page['page']}: Found table with cardinality column")
                lines = md.split('\n')
                if len(lines) > 0:
                    print(f"Header: {lines[0]}")
                break

# Check extracted fields for cardinality values
print("\n=== Checking extracted field definitions for cardinality ===")
fields_with_card = 0
fields_without_card = 0

for page in doc['pages']:
    for block in page.get('blocks', []):
        if block.get('type') == 'field_definition':
            cardinality = block.get('cardinality')
            if cardinality:
                fields_with_card += 1
                if fields_with_card <= 5:  # Show first 5 examples
                    print(f"Field: {block.get('field_name')} - Cardinality: {cardinality}")
            else:
                fields_without_card += 1

print(f"\nTotal fields WITH cardinality: {fields_with_card}")
print(f"Total fields WITHOUT cardinality: {fields_without_card}")

# Check a few actual field defs to see what data they have
print("\n=== Sample field definitions ===")
sample_count = 0
for page in doc['pages']:
    for block in page.get('blocks', []):
        if block.get('type') == 'field_definition' and sample_count < 3:
            print(f"\nField: {block.get('field_name')}")
            print(f"  Type: {block.get('field_type')}")
            print(f"  Optionality: {block.get('optionality')}")
            print(f"  Cardinality: {block.get('cardinality')}")
            print(f"  Message: {block.get('message_id')}")
            sample_count += 1
