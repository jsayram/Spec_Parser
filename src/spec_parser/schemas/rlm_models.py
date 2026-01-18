"""
RLM-style models for surgical document extraction.

These models support:
- search(query) → page spans
- get_span(page, start, end)
- get_table(page, table_id)
- neighbors(page, k)
- list_headings() / toc_map()
"""

from typing import List, Optional, Dict, Tuple
from pydantic import BaseModel, Field


class DocumentSpan(BaseModel):
    """
    A span of text within a document with precise location.
    
    Used by RLM controller to slice documents surgically instead of
    reading entire pages. Essential for avoiding context-rot.
    """
    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    start: int = Field(..., ge=0, description="Start position in page markdown")
    end: int = Field(..., ge=0, description="End position in page markdown")
    text: str = Field(..., description="Extracted text content")
    bbox: Optional[Tuple[float, float, float, float]] = Field(
        None,
        description="Bounding box if available"
    )
    citation: Optional[str] = Field(None, description="Citation ID for provenance")
    score: Optional[float] = Field(None, description="Relevance score from search")
    
    @property
    def length(self) -> int:
        """Length of span in characters"""
        return self.end - self.start
    
    def overlaps(self, other: "DocumentSpan") -> bool:
        """Check if this span overlaps with another on the same page"""
        if self.page != other.page:
            return False
        return not (self.end <= other.start or other.end <= self.start)


class TableReference(BaseModel):
    """
    Reference to a table within the document.
    
    Enables get_table(page, table_id) for structured data extraction.
    """
    page: int = Field(..., ge=1, description="Page number containing table")
    table_id: str = Field(..., description="Unique table identifier")
    bbox: Tuple[float, float, float, float] = Field(..., description="Table bounding box")
    caption: Optional[str] = Field(None, description="Table caption if found")
    markdown: Optional[str] = Field(None, description="Markdown representation")
    row_count: int = Field(default=0, ge=0, description="Number of rows")
    col_count: int = Field(default=0, ge=0, description="Number of columns")
    citation: str = Field(..., description="Citation for provenance")
    
    def get_cell(self, row: int, col: int) -> Optional[str]:
        """
        Extract specific cell from markdown table.
        
        Args:
            row: Row index (0-indexed)
            col: Column index (0-indexed)
            
        Returns:
            Cell content or None
        """
        if not self.markdown:
            return None
        
        lines = self.markdown.strip().split('\n')
        # Skip header separator line
        data_lines = [line for line in lines if not line.strip().startswith('|--')]
        
        if row >= len(data_lines):
            return None
        
        cells = [cell.strip() for cell in data_lines[row].split('|')]
        cells = [cell for cell in cells if cell]  # Remove empty
        
        if col >= len(cells):
            return None
        
        return cells[col]


class HeadingNode(BaseModel):
    """
    A heading/section in the document structure.
    
    Supports toc_map() for navigating document structure.
    """
    level: int = Field(..., ge=1, le=6, description="Heading level (1-6)")
    text: str = Field(..., description="Heading text")
    page: int = Field(..., ge=1, description="Page number")
    position: int = Field(..., ge=0, description="Character position in page markdown")
    bbox: Optional[Tuple[float, float, float, float]] = Field(None, description="Heading bounding box")
    citation: Optional[str] = Field(None, description="Citation for provenance")
    children: List["HeadingNode"] = Field(default_factory=list, description="Child headings/sections")
    
    def add_child(self, child: "HeadingNode"):
        """Add child heading node"""
        self.children.append(child)
    
    def find_sections(self, query: str) -> List["HeadingNode"]:
        """
        Find sections matching query (case-insensitive).
        
        Args:
            query: Search term
            
        Returns:
            List of matching heading nodes
        """
        matches = []
        if query.lower() in self.text.lower():
            matches.append(self)
        
        for child in self.children:
            matches.extend(child.find_sections(query))
        
        return matches


class TOCEntry(BaseModel):
    """
    Table of Contents entry for navigation.
    
    Flat representation for quick lookup.
    """
    heading: str = Field(..., description="Heading text")
    level: int = Field(..., ge=1, le=6, description="Heading level")
    page: int = Field(..., ge=1, description="Page number")
    position: int = Field(..., ge=0, description="Position in page")
    section_number: Optional[str] = Field(None, description="Section number (e.g., '3.2.1')")


class ContextWindow(BaseModel):
    """
    Context window for neighbors(page, k) operation.
    
    Provides surrounding context for a target location.
    """
    target_page: int = Field(..., ge=1, description="Target page")
    target_position: int = Field(..., ge=0, description="Target position in page")
    before: List[DocumentSpan] = Field(default_factory=list, description="Spans before target")
    after: List[DocumentSpan] = Field(default_factory=list, description="Spans after target")
    
    @property
    def all_spans(self) -> List[DocumentSpan]:
        """Get all spans in order"""
        return self.before + self.after
    
    @property
    def total_length(self) -> int:
        """Total characters in context window"""
        return sum(span.length for span in self.all_spans)


class SearchResult(BaseModel):
    """
    Result from search(query) operation.
    
    Returns ranked page spans for surgical extraction.
    """
    query: str = Field(..., description="Original search query")
    spans: List[DocumentSpan] = Field(default_factory=list, description="Matching document spans")
    method: str = Field(..., description="Search method: 'regex', 'keyword', 'semantic', 'hybrid'")
    total_results: int = Field(..., ge=0, description="Total number of results found")
    
    def top_k(self, k: int) -> List[DocumentSpan]:
        """Get top-k results by score"""
        sorted_spans = sorted(self.spans, key=lambda x: x.score or 0, reverse=True)
        return sorted_spans[:k]
    
    def by_page(self) -> Dict[int, List[DocumentSpan]]:
        """Group results by page number"""
        by_page: Dict[int, List[DocumentSpan]] = {}
        for span in self.spans:
            if span.page not in by_page:
                by_page[span.page] = []
            by_page[span.page].append(span)
        return by_page
