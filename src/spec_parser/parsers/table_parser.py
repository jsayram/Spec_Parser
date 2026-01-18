"""
Parse markdown tables from JSON sidecar into structured data.

This is the foundation for all entity extraction - converts raw table
markdown into queryable Python objects.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import re
from loguru import logger


@dataclass
class ParsedTable:
    """Represents a parsed table with structured access"""
    
    headers: List[str]
    rows: List[List[str]]
    page: int
    citation: str
    bbox: Tuple[float, float, float, float]
    
    def to_dict_list(self) -> List[Dict[str, str]]:
        """
        Convert table to list of dicts (one per row).
        
        Returns:
            List of dicts where keys are column headers
        """
        return [
            {header: cell for header, cell in zip(self.headers, row)}
            for row in self.rows
        ]
    
    def has_columns(self, required: List[str], fuzzy: bool = True) -> bool:
        """
        Check if table has specific columns.
        
        Args:
            required: List of column names to check for
            fuzzy: If True, uses case-insensitive substring matching
                   If False, requires exact match
        
        Returns:
            True if all required columns found
        """
        if fuzzy:
            headers_lower = [h.lower() for h in self.headers]
            return all(
                any(req.lower() in h for h in headers_lower)
                for req in required
            )
        else:
            return all(col in self.headers for col in required)
    
    def get_column(self, column_name: str, fuzzy: bool = True) -> List[str]:
        """
        Extract all values from a specific column.
        
        Args:
            column_name: Name of column to extract
            fuzzy: If True, uses case-insensitive substring matching
        
        Returns:
            List of cell values from that column
        """
        # Find matching column index
        col_idx = None
        
        if fuzzy:
            column_name_lower = column_name.lower()
            for idx, header in enumerate(self.headers):
                if column_name_lower in header.lower():
                    col_idx = idx
                    break
        else:
            if column_name in self.headers:
                col_idx = self.headers.index(column_name)
        
        if col_idx is None:
            return []
        
        return [row[col_idx] for row in self.rows if col_idx < len(row)]
    
    def filter_rows(self, column: str, value: str, fuzzy: bool = True) -> List[Dict[str, str]]:
        """
        Filter rows where column matches value.
        
        Args:
            column: Column name to filter on
            value: Value to match (case-insensitive if fuzzy)
            fuzzy: Use substring matching
        
        Returns:
            List of matching rows as dicts
        """
        all_rows = self.to_dict_list()
        
        # Find column key
        col_key = None
        if fuzzy:
            column_lower = column.lower()
            value_lower = value.lower()
            for key in all_rows[0].keys() if all_rows else []:
                if column_lower in key.lower():
                    col_key = key
                    break
        else:
            col_key = column if column in (all_rows[0].keys() if all_rows else []) else None
        
        if not col_key:
            return []
        
        # Filter rows
        if fuzzy:
            return [row for row in all_rows if value_lower in row.get(col_key, "").lower()]
        else:
            return [row for row in all_rows if row.get(col_key) == value]
    
    def __len__(self) -> int:
        """Return number of rows"""
        return len(self.rows)
    
    def __repr__(self) -> str:
        return f"ParsedTable(headers={self.headers}, rows={len(self.rows)}, page={self.page})"


class TableParser:
    """Parse markdown tables from JSON sidecar"""
    
    def __init__(self):
        self.tables: List[ParsedTable] = []
    
    def parse_all_tables(self, json_sidecar: dict) -> List[ParsedTable]:
        """
        Extract and parse all tables from document.
        
        Args:
            json_sidecar: The complete JSON sidecar structure
        
        Returns:
            List of parsed tables with structured access
        """
        tables = []
        
        for page_data in json_sidecar.get("pages", []):
            page_num = page_data.get("page", 0)
            
            for block in page_data.get("blocks", []):
                if block.get("type") == "table":
                    # Table content can be in 'content' or 'markdown_table' key
                    table_content = block.get("markdown_table") or block.get("content", "")
                    
                    table = self._parse_markdown_table(
                        content=table_content,
                        page=page_num,
                        citation=block.get("citation", ""),
                        bbox=tuple(block.get("bbox", [0, 0, 0, 0]))
                    )
                    if table:
                        tables.append(table)
                        logger.debug(f"Parsed table on page {page_num}: {len(table)} rows")
        
        self.tables = tables
        logger.info(f"Parsed {len(tables)} tables from document")
        return tables
    
    def _parse_markdown_table(self, content: str, page: int, 
                              citation: str, bbox: Tuple[float, float, float, float]) -> Optional[ParsedTable]:
        """
        Parse markdown table format into structured data.
        
        Args:
            content: Markdown table string
            page: Page number
            citation: Citation ID
            bbox: Bounding box coordinates
        
        Returns:
            ParsedTable if valid, None otherwise
        """
        if not content or not content.strip():
            return None
        
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if len(lines) < 3:  # Need header + separator + at least 1 row
            return None
        
        # Parse header row
        headers = self._parse_table_row(lines[0])
        if not headers:
            return None
        
        # Skip separator line (|---|---|)
        # Separator is usually line[1], but let's be flexible
        separator_idx = self._find_separator_line(lines)
        if separator_idx == -1:
            logger.warning(f"No separator found in table on page {page}")
            separator_idx = 1  # Assume standard position
        
        # Parse data rows
        rows = []
        for line in lines[separator_idx + 1:]:
            cells = self._parse_table_row(line)
            
            # Handle rows with different column counts
            if len(cells) == len(headers):
                rows.append(cells)
            elif len(cells) < len(headers):
                # Pad with empty strings
                cells.extend([''] * (len(headers) - len(cells)))
                rows.append(cells)
            elif len(cells) > len(headers):
                # Truncate extra cells
                rows.append(cells[:len(headers)])
        
        if not rows:
            logger.debug(f"Table on page {page} has no data rows")
            return None
        
        return ParsedTable(
            headers=headers,
            rows=rows,
            page=page,
            citation=citation,
            bbox=bbox
        )
    
    def _parse_table_row(self, line: str) -> List[str]:
        """
        Parse a single table row into cells.
        
        Args:
            line: Markdown table row (with | separators)
        
        Returns:
            List of cell values
        """
        # Remove leading/trailing pipes
        line = line.strip('|').strip()
        
        # Split on pipes, but handle escaped pipes
        cells = [cell.strip() for cell in line.split('|')]
        
        # Remove empty cells
        cells = [cell for cell in cells if cell]
        
        return cells
    
    def _find_separator_line(self, lines: List[str]) -> int:
        """
        Find the separator line in table (contains |---|---|).
        
        Args:
            lines: All lines from the table
        
        Returns:
            Index of separator line, or -1 if not found
        """
        for idx, line in enumerate(lines):
            # Separator contains only pipes, dashes, colons, and spaces
            if re.match(r'^[\|\-:\s]+$', line):
                return idx
        return -1
    
    def get_tables_by_page(self, page: int) -> List[ParsedTable]:
        """Get all tables from a specific page"""
        return [t for t in self.tables if t.page == page]
    
    def get_tables_with_columns(self, required_columns: List[str]) -> List[ParsedTable]:
        """Get all tables that have specific columns"""
        return [t for t in self.tables if t.has_columns(required_columns)]
    
    def get_table_count(self) -> int:
        """Return total number of tables parsed"""
        return len(self.tables)
