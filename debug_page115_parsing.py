#!/usr/bin/env python3
"""
Debug script to see what's in page 115 blocks during indexing.
"""

from pathlib import Path
import json
from pydantic import BaseModel, Field, ValidationError
from typing import List, Union, Tuple

# Load the JSON document
doc_path = Path("data/spec_output/20260119_165832_rochecobasliatfull_v2/json/document.json")
with open(doc_path) as f:
    data = json.load(f)

# Find page 115
page115_data = [p for p in data['pages'] if p['page'] == 115][0]

print(f"Page 115 has {len(page115_data['blocks'])} blocks")
print("\nBlock 6 (the TOC block):")
block6 = page115_data['blocks'][6]
print(f"  Type: {block6['type']}")
print(f"  Has 'content' key: {'content' in block6}")
print(f"  Content length: {len(block6.get('content', ''))}")
print(f"  Content preview: {block6.get('content', 'NO CONTENT')[:200]}")

# Try to parse as Pydantic model
print("\n--- Attempting to parse as Pydantic PageBundle ---")

# Define minimal models
class Block(BaseModel):
    type: str
    bbox: Tuple[float, float, float, float]
    citation: str

class TextBlock(Block):
    type: str = Field(default="text")
    content: str
    md_slice: Tuple[int, int]

class TableBlock(Block):
    type: str = Field(default="table")
    table_ref: str
    markdown_table: str | None = None

class GraphicsBlock(Block):
    type: str = Field(default="graphics")
    source: str

class PictureBlock(Block):
    type: str = Field(default="picture")
    image_ref: str
    source: str

# Try parsing blocks
print("\nParsing all blocks...")
for i, block_data in enumerate(page115_data['blocks']):
    block_type = block_data.get('type')
    print(f"\nBlock {i}: type={block_type}")
    
    try:
        if block_type == "text":
            block = TextBlock(**block_data)
            print(f"  ✓ Parsed as TextBlock")
            print(f"  content length: {len(block.content)}")
            print(f"  content preview: {block.content[:100]}")
        elif block_type == "table":
            block = TableBlock(**block_data)
            print(f"  ✓ Parsed as TableBlock")
            if block.markdown_table:
                print(f"  markdown_table length: {len(block.markdown_table)}")
        elif block_type == "graphics":
            block = GraphicsBlock(**block_data)
            print(f"  ✓ Parsed as GraphicsBlock")
        elif block_type == "picture":
            block = PictureBlock(**block_data)
            print(f"  ✓ Parsed as PictureBlock")
    except ValidationError as e:
        print(f"  ✗ Failed to parse: {e}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
