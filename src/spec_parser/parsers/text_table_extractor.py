"""
Table extractor that works from raw text blocks.

Fallback extractor for when PyMuPDF table detection fails or returns empty tables.
Analyzes text block alignment and spacing to identify tabular structures.
"""

from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import re
from loguru import logger


@dataclass
class Cell:
    """Represents a single table cell."""
    text: str
    x: float
    y: float
    width: float
    height: float
    

class TextBasedTableExtractor:
    """
    Extract tables from text blocks by analyzing alignment and spacing.
    
    Identifies table structures by:
    1. Finding rows with consistent vertical alignment
    2. Detecting columns based on horizontal spacing patterns
    3. Reconstructing table structure as markdown
    """
    
    # Thresholds for table detection
    MIN_ROWS = 2  # Minimum rows to be considered a table
    MIN_COLS = 2  # Minimum columns to be considered a table
    Y_TOLERANCE = 5.0  # Vertical tolerance for row alignment (points)
    MIN_COL_GAP = 20.0  # Minimum horizontal gap between columns (points)
    MAX_CELL_HEIGHT = 100.0  # Maximum cell height (points)
    
    def __init__(self):
        """Initialize table extractor."""
        pass
    
    def extract_tables_from_text_dict(
        self,
        text_dict: Dict,
        page_bbox: Tuple[float, float, float, float]
    ) -> List[Tuple[Tuple[float, float, float, float], str]]:
        """
        Extract tables from PyMuPDF text dictionary.
        
        Args:
            text_dict: PyMuPDF text dictionary from page.get_text("dict")
            page_bbox: Page bounding box
            
        Returns:
            List of (bbox, markdown_table) tuples
        """
        tables = []
        
        # Extract all text spans with positions
        cells = self._extract_cells(text_dict)
        
        if len(cells) < self.MIN_ROWS * self.MIN_COLS:
            return tables
        
        # Group cells into rows
        rows = self._group_into_rows(cells)
        
        # Find table regions
        table_regions = self._find_table_regions(rows)
        
        # Convert regions to markdown tables
        for region_rows in table_regions:
            if len(region_rows) >= self.MIN_ROWS:
                bbox, markdown = self._rows_to_markdown_table(region_rows)
                if markdown and self._is_valid_table(markdown):
                    tables.append((bbox, markdown))
                    logger.debug(f"Extracted text-based table with {len(region_rows)} rows")
        
        return tables
    
    def _extract_cells(self, text_dict: Dict) -> List[Cell]:
        """Extract all text spans as potential cells."""
        cells = []
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Only text blocks
                continue
            
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    
                    bbox = span.get("bbox", (0, 0, 0, 0))
                    cell = Cell(
                        text=text,
                        x=bbox[0],
                        y=bbox[1],
                        width=bbox[2] - bbox[0],
                        height=bbox[3] - bbox[1]
                    )
                    
                    # Filter out very large cells (likely not table content)
                    if cell.height <= self.MAX_CELL_HEIGHT:
                        cells.append(cell)
        
        return cells
    
    def _group_into_rows(self, cells: List[Cell]) -> List[List[Cell]]:
        """Group cells into rows based on vertical alignment."""
        if not cells:
            return []
        
        # Sort by Y position
        sorted_cells = sorted(cells, key=lambda c: c.y)
        
        rows = []
        current_row = [sorted_cells[0]]
        current_y = sorted_cells[0].y
        
        for cell in sorted_cells[1:]:
            # Check if cell is on same row (within tolerance)
            if abs(cell.y - current_y) <= self.Y_TOLERANCE:
                current_row.append(cell)
            else:
                # Start new row
                if current_row:
                    # Sort row by X position
                    current_row.sort(key=lambda c: c.x)
                    rows.append(current_row)
                current_row = [cell]
                current_y = cell.y
        
        # Add last row
        if current_row:
            current_row.sort(key=lambda c: c.x)
            rows.append(current_row)
        
        return rows
    
    def _find_table_regions(self, rows: List[List[Cell]]) -> List[List[List[Cell]]]:
        """
        Find contiguous table regions.
        
        A table region is a sequence of rows with:
        - Similar number of cells
        - Consistent column positions
        """
        if not rows:
            return []
        
        regions = []
        current_region = []
        
        for row in rows:
            if not current_region:
                current_region = [row]
                continue
            
            # Check if row fits with current region
            if self._rows_compatible(current_region[-1], row):
                current_region.append(row)
            else:
                # Save current region if it's a table
                if len(current_region) >= self.MIN_ROWS:
                    regions.append(current_region)
                current_region = [row]
        
        # Add last region
        if len(current_region) >= self.MIN_ROWS:
            regions.append(current_region)
        
        return regions
    
    def _rows_compatible(self, row1: List[Cell], row2: List[Cell]) -> bool:
        """Check if two rows are compatible (part of same table)."""
        # Similar number of cells (within 1)
        if abs(len(row1) - len(row2)) > 1:
            return False
        
        # Check column alignment (X positions should be similar)
        if len(row1) < 2 or len(row2) < 2:
            return True  # Can't determine alignment with too few cells
        
        # Get X positions
        x_positions_1 = [c.x for c in row1]
        x_positions_2 = [c.x for c in row2]
        
        # Check if column positions align
        min_len = min(len(x_positions_1), len(x_positions_2))
        aligned_count = 0
        
        for i in range(min_len):
            if abs(x_positions_1[i] - x_positions_2[i]) <= self.MIN_COL_GAP:
                aligned_count += 1
        
        # At least half of columns should align
        return aligned_count >= min_len / 2
    
    def _rows_to_markdown_table(
        self,
        rows: List[List[Cell]]
    ) -> Tuple[Tuple[float, float, float, float], str]:
        """Convert rows to markdown table with bbox."""
        if not rows:
            return ((0, 0, 0, 0), "")
        
        # Calculate table bbox
        all_cells = [cell for row in rows for cell in row]
        min_x = min(c.x for c in all_cells)
        min_y = min(c.y for c in all_cells)
        max_x = max(c.x + c.width for c in all_cells)
        max_y = max(c.y + c.height for c in all_cells)
        bbox = (min_x, min_y, max_x, max_y)
        
        # Determine number of columns (use max from any row)
        max_cols = max(len(row) for row in rows)
        
        if max_cols < self.MIN_COLS:
            return (bbox, "")
        
        # Build markdown table
        markdown_lines = []
        
        for idx, row in enumerate(rows):
            # Pad row to max_cols
            cells_text = [cell.text for cell in row]
            cells_text.extend([''] * (max_cols - len(cells_text)))
            
            # Create markdown row
            row_text = '|' + '|'.join(cells_text) + '|'
            markdown_lines.append(row_text)
            
            # Add separator after first row (header)
            if idx == 0:
                separator = '|' + '|'.join(['---'] * max_cols) + '|'
                markdown_lines.append(separator)
        
        markdown = '\n'.join(markdown_lines)
        return (bbox, markdown)
    
    def _is_valid_table(self, markdown: str) -> bool:
        """Check if markdown table has actual data (not just empty cells)."""
        lines = [l.strip() for l in markdown.split('\n') if l.strip()]
        
        # Need at least header + separator + 1 data row
        if len(lines) < 3:
            return False
        
        # Check data rows (skip header and separator)
        data_rows = [l for l in lines[2:] if l and not l.startswith('|---')]
        
        if not data_rows:
            return False
        
        # Check if rows have non-empty content
        for row in data_rows:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            if any(cells):  # At least one non-empty cell
                return True
        
        return False
    
    def enhance_empty_table(
        self,
        empty_table_bbox: Tuple[float, float, float, float],
        text_dict: Dict
    ) -> Optional[str]:
        """
        Try to extract table content for an empty table using text analysis.
        
        Args:
            empty_table_bbox: Bounding box of the empty table
            text_dict: PyMuPDF text dictionary
            
        Returns:
            Markdown table string or None if extraction fails
        """
        # Extract cells within or near the table bbox
        cells = self._extract_cells(text_dict)
        
        # Filter cells within expanded bbox (add margin for alignment issues)
        margin = 20.0
        table_cells = [
            c for c in cells
            if (empty_table_bbox[0] - margin <= c.x <= empty_table_bbox[2] + margin and
                empty_table_bbox[1] - margin <= c.y <= empty_table_bbox[3] + margin)
        ]
        
        if not table_cells:
            return None
        
        # Group into rows
        rows = self._group_into_rows(table_cells)
        
        if len(rows) < self.MIN_ROWS:
            return None
        
        # Convert to markdown
        _, markdown = self._rows_to_markdown_table(rows)
        
        if self._is_valid_table(markdown):
            return markdown
        
        return None
