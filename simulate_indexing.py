#!/usr/bin/env python3
"""
Simulated indexing to see what block types we get.
"""

from pathlib import Path
import json
from pydantic import BaseModel, Field
from typing import List, Union, Tuple, Dict

# Define models (same as in page_bundle.py)
class Block(BaseModel):
    type: str
    bbox: Tuple[float, float, float, float]
    citation: str

class TextBlock(Block):
    type: str = Field(default="text")
    md_slice: Tuple[int, int]
    content: str

class PictureBlock(Block):
    type: str = Field(default="picture")
    image_ref: str
    source: str

class TableBlock(Block):
    type: str = Field(default="table")
    table_ref: str
    markdown_table: str | None = None

class GraphicsBlock(Block):
    type: str = Field(default="graphics")
    source: str

class Citation(BaseModel):
    citation_id: str
    page: int
    bbox: Tuple[float, float, float, float]
    source: str
    content_type: str

class PageBundle(BaseModel):
    page: int
    markdown: str
    blocks: List[Union[TextBlock, PictureBlock, TableBlock, GraphicsBlock]]
    ocr: List = []
    citations: Dict[str, Citation] = {}
    metadata: Dict[str, str] = {}

# Load the JSON document
doc_path = Path("data/spec_output/20260119_165832_rochecobasliatfull_v2/json/document.json")
with open(doc_path) as f:
    data = json.load(f)

# Parse page 115 as PageBundle
page115_data = [p for p in data['pages'] if p['page'] == 115][0]
page115 = PageBundle(**page115_data)

print(f"Page 115 has {len(page115.blocks)} blocks")

# Simulate the indexing loop
texts = []
metadatas = []

for block in page115.blocks:
    print(f"\nBlock type: {block.type}")
    print(f"  Python type: {type(block).__name__}")
    print(f"  Has 'content' attr: {hasattr(block, 'content')}")
    
    # The actual indexing code
    text_content = None
    if block.type == "text" and hasattr(block, 'content') and block.content:
        text_content = block.content
        print(f"  ✓ Would index (length={len(text_content)})")
    elif block.type == "table" and hasattr(block, 'markdown_table') and block.markdown_table:
        text_content = block.markdown_table
        print(f"  ✓ Would index table (length={len(text_content)})")
    else:
        print(f"  ✗ Would NOT index")
    
    if text_content:
        texts.append(text_content)

print(f"\n\nTotal blocks that would be indexed: {len(texts)}")
print(f"Block 6 (TOC) indexed: {any('ACK.R01' in t for t in texts)}")
