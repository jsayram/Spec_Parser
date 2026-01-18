"""Markdown builder for converting extracted pages to markdown."""

from typing import List


def build_markdown(pages: List[dict]) -> str:
    """
    Build markdown document from extracted pages.
    
    Args:
        pages: List of page dictionaries with blocks
    
    Returns:
        Complete markdown document
    """
    markdown_lines = []
    
    for page in pages:
        page_num = page.get("page", 0)
        markdown_lines.append(f"\n# Page {page_num}\n")
        
        for block in page.get("blocks", []):
            content = block.get("markdown", "")
            if content:
                markdown_lines.append(content)
                markdown_lines.append("\n")
    
    return "\n".join(markdown_lines)
