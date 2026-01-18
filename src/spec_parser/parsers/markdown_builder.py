"""Markdown builder for converting extracted pages to markdown."""

from typing import List
from ..schemas.page_bundle import PageBundle


def build_markdown(pages: List[PageBundle]) -> str:
    """
    Build markdown document from extracted pages.
    
    Args:
        pages: List of PageBundle objects with blocks
    
    Returns:
        Complete markdown document
    """
    markdown_lines = []
    
    for page_bundle in pages:
        markdown_lines.append(f"\n# Page {page_bundle.page}\n")
        
        for block in page_bundle.blocks:
            if hasattr(block, 'markdown') and block.markdown:
                markdown_lines.append(block.markdown)
                markdown_lines.append("\n")
    
    return "\n".join(markdown_lines)
