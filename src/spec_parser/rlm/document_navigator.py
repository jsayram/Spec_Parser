"""
RLM-style document navigator for surgical extraction.

Provides tools for:
- search(query) → returns page spans
- get_span(page, start, end)
- get_table(page, table_id)
- neighbors(page, k) (grab surrounding context)
- list_headings() / toc_map()

This is the "forensic accountant with a flashlight" approach to handling
large vendor specs without context-rot.
"""

import re
from typing import List, Optional, Dict, Tuple
from loguru import logger

from spec_parser.models.page_bundle import PageBundle
from spec_parser.models.rlm_models import (
    DocumentSpan,
    TableReference,
    HeadingNode,
    TOCEntry,
    ContextWindow,
    SearchResult,
)
from spec_parser.exceptions import RLMError
from spec_parser.config import settings


class DocumentNavigator:
    """
    RLM-style navigator for surgical document extraction.
    
    Instead of reading hundreds of pages linearly, this lets you:
    1. Search for specific content
    2. Extract precise spans
    3. Navigate by structure (headings, tables)
    4. Get surrounding context
    
    Perfect for fighting context-rot in large vendor specs.
    """
    
    def __init__(self, page_bundles: List[PageBundle]):
        """
        Initialize navigator with parsed document.
        
        Args:
            page_bundles: List of PageBundle objects from PDF extraction
        """
        self.page_bundles = {bundle.page: bundle for bundle in page_bundles}
        self.pages = sorted(self.page_bundles.keys())
        
        # Build indices for fast lookup
        self._table_index: Dict[str, TableReference] = {}
        self._heading_index: List[HeadingNode] = []
        self._toc: List[TOCEntry] = []
        
        self._build_indices()
        
        logger.info(f"DocumentNavigator initialized with {len(self.pages)} pages")
    
    def search(self, query: str, method: str = "regex", top_k: int = None) -> SearchResult:
        """
        Search document for query string.
        
        Args:
            query: Search query (regex pattern or plain text)
            method: Search method ('regex' or 'keyword')
            top_k: Number of results to return (None for all)
            
        Returns:
            SearchResult with matching spans
        """
        top_k = top_k or settings.search_top_k
        spans: List[DocumentSpan] = []
        
        if method == "regex":
            pattern = re.compile(query, re.IGNORECASE)
        else:  # keyword
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        
        for page_num in self.pages:
            bundle = self.page_bundles[page_num]
            
            # Search in markdown
            for match in pattern.finditer(bundle.markdown):
                span = DocumentSpan(
                    page=page_num,
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    score=1.0  # Perfect match for regex/keyword
                )
                spans.append(span)
        
        logger.info(f"Search '{query}' found {len(spans)} matches")
        
        return SearchResult(
            query=query,
            spans=spans[:top_k],
            method=method,
            total_results=len(spans)
        )
    
    def get_span(self, page: int, start: int, end: int) -> DocumentSpan:
        """
        Extract exact span from page.
        
        Args:
            page: Page number (1-indexed)
            start: Start position in page markdown
            end: End position in page markdown
            
        Returns:
            DocumentSpan with extracted text
        """
        if page not in self.page_bundles:
            raise RLMError(f"Page {page} not found")
        
        bundle = self.page_bundles[page]
        
        if end > len(bundle.markdown):
            raise RLMError(f"Span end ({end}) exceeds page length ({len(bundle.markdown)})")
        
        text = bundle.markdown[start:end]
        
        # Try to find associated citation
        citation_id = None
        for block in bundle.blocks:
            if hasattr(block, 'md_slice'):
                slice_start, slice_end = block.md_slice
                if slice_start <= start < slice_end:
                    citation_id = block.citation
                    break
        
        return DocumentSpan(
            page=page,
            start=start,
            end=end,
            text=text,
            citation=citation_id
        )
    
    def get_table(self, page: int, table_id: str) -> Optional[TableReference]:
        """
        Get table by ID.
        
        Args:
            page: Page number
            table_id: Table identifier
            
        Returns:
            TableReference or None
        """
        key = f"p{page}_{table_id}"
        return self._table_index.get(key)
    
    def neighbors(self, page: int, position: int, k: int = None) -> ContextWindow:
        """
        Get surrounding context for a position.
        
        Args:
            page: Page number
            position: Character position in page
            k: Number of neighbor spans (default from settings)
            
        Returns:
            ContextWindow with before/after spans
        """
        k = k or settings.rlm_neighbors_count
        window_size = settings.rlm_context_window
        
        if page not in self.page_bundles:
            raise RLMError(f"Page {page} not found")
        
        bundle = self.page_bundles[page]
        
        # Calculate window boundaries
        start_before = max(0, position - window_size)
        end_after = min(len(bundle.markdown), position + window_size)
        
        # Extract before span
        before_text = bundle.markdown[start_before:position]
        before_span = DocumentSpan(
            page=page,
            start=start_before,
            end=position,
            text=before_text
        )
        
        # Extract after span
        after_text = bundle.markdown[position:end_after]
        after_span = DocumentSpan(
            page=page,
            start=position,
            end=end_after,
            text=after_text
        )
        
        return ContextWindow(
            target_page=page,
            target_position=position,
            before=[before_span],
            after=[after_span]
        )
    
    def list_headings(self, page: Optional[int] = None) -> List[HeadingNode]:
        """
        List all headings in document or specific page.
        
        Args:
            page: Page number to filter (None for all pages)
            
        Returns:
            List of HeadingNode objects
        """
        if page is not None:
            return [h for h in self._heading_index if h.page == page]
        return self._heading_index
    
    def toc_map(self) -> List[TOCEntry]:
        """
        Get flat table of contents.
        
        Returns:
            List of TOCEntry objects
        """
        return self._toc
    
    def find_section(self, query: str) -> List[HeadingNode]:
        """
        Find sections matching query.
        
        Args:
            query: Search term for section headings
            
        Returns:
            List of matching HeadingNode objects
        """
        matches = []
        for heading in self._heading_index:
            if query.lower() in heading.text.lower():
                matches.append(heading)
        
        logger.debug(f"Found {len(matches)} sections matching '{query}'")
        return matches
    
    def get_page_bundle(self, page: int) -> Optional[PageBundle]:
        """
        Get raw PageBundle for a specific page.
        
        Args:
            page: Page number
            
        Returns:
            PageBundle or None
        """
        return self.page_bundles.get(page)
    
    def _build_indices(self):
        """Build internal indices for fast lookup"""
        # Build table index
        for page_num, bundle in self.page_bundles.items():
            for block in bundle.get_blocks_by_type("table"):
                if hasattr(block, 'table_ref'):
                    key = f"p{page_num}_{block.table_ref}"
                    
                    table_ref = TableReference(
                        page=page_num,
                        table_id=block.table_ref,
                        bbox=block.bbox,
                        markdown=getattr(block, 'markdown_table', None),
                        citation=block.citation
                    )
                    self._table_index[key] = table_ref
        
        # Build heading index
        self._heading_index = self._extract_headings()
        
        # Build TOC
        self._toc = self._build_toc()
        
        logger.debug(f"Built indices: {len(self._table_index)} tables, {len(self._heading_index)} headings")
    
    def _extract_headings(self) -> List[HeadingNode]:
        """Extract headings from markdown"""
        headings = []
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        for page_num in self.pages:
            bundle = self.page_bundles[page_num]
            
            for match in heading_pattern.finditer(bundle.markdown):
                level = len(match.group(1))
                text = match.group(2).strip()
                position = match.start()
                
                heading = HeadingNode(
                    level=level,
                    text=text,
                    page=page_num,
                    position=position
                )
                headings.append(heading)
        
        return headings
    
    def _build_toc(self) -> List[TOCEntry]:
        """Build flat table of contents"""
        toc = []
        
        for heading in self._heading_index:
            entry = TOCEntry(
                heading=heading.text,
                level=heading.level,
                page=heading.page,
                position=heading.position
            )
            toc.append(entry)
        
        return toc
