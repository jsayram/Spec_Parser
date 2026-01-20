"""
Layout detection for proper reading order and structure understanding.

Analyzes document layout to identify:
- Multi-column layouts
- Reading order sequence
- Table structures
- Headers, footers, sidebars
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger

from spec_parser.schemas.page_bundle import TextBlock, TableBlock, PictureBlock


@dataclass
class LayoutRegion:
    """Represents a detected layout region."""
    
    region_type: str  # "header", "footer", "sidebar", "column", "table", "figure"
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    reading_order: int  # Sequence in logical reading flow
    confidence: float  # 0.0 - 1.0


@dataclass
class LayoutAnalysis:
    """Complete layout analysis for a page."""
    
    regions: List[LayoutRegion]
    column_count: int
    has_sidebar: bool
    reading_order_map: dict  # block_id -> reading_order


class LayoutDetector:
    """
    Detect document layout structure for proper reading order.
    
    Uses heuristic-based approach (can be enhanced with ML models later):
    - Horizontal position clustering for columns
    - Vertical position for reading flow
    - Size/position patterns for headers/footers
    """
    
    def __init__(
        self,
        column_gap_threshold: float = 30.0,
        header_height_threshold: float = 100.0,
        footer_y_threshold: float = 700.0
    ):
        """
        Initialize layout detector.
        
        Args:
            column_gap_threshold: Minimum horizontal gap to detect columns (points)
            header_height_threshold: Max y-position for header regions (points)
            footer_y_threshold: Min y-position for footer regions (points)
        """
        self.column_gap_threshold = column_gap_threshold
        self.header_height_threshold = header_height_threshold
        self.footer_y_threshold = footer_y_threshold
    
    def analyze_layout(
        self,
        blocks: List[TextBlock | TableBlock | PictureBlock],
        page_width: float,
        page_height: float
    ) -> LayoutAnalysis:
        """
        Analyze page layout structure.
        
        Args:
            blocks: List of extracted blocks
            page_width: Page width in points
            page_height: Page height in points
            
        Returns:
            LayoutAnalysis with detected regions and reading order
        """
        regions = []
        
        # Separate text blocks for analysis
        text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
        
        if not text_blocks:
            return LayoutAnalysis(
                regions=[],
                column_count=1,
                has_sidebar=False,
                reading_order_map={}
            )
        
        # Detect columns by horizontal clustering
        columns = self._detect_columns(text_blocks, page_width)
        
        # Detect special regions (header, footer, sidebar)
        special_regions = self._detect_special_regions(
            text_blocks, page_width, page_height
        )
        
        regions.extend(special_regions)
        
        # Assign reading order
        reading_order_map = self._assign_reading_order(
            blocks, columns, special_regions
        )
        
        has_sidebar = any(r.region_type == "sidebar" for r in special_regions)
        
        logger.info(
            f"Detected layout: {len(columns)} columns, "
            f"sidebar={has_sidebar}, {len(regions)} regions"
        )
        
        return LayoutAnalysis(
            regions=regions,
            column_count=len(columns),
            has_sidebar=has_sidebar,
            reading_order_map=reading_order_map
        )
    
    def _detect_columns(
        self,
        blocks: List[TextBlock],
        page_width: float
    ) -> List[Tuple[float, float]]:
        """
        Detect column boundaries by horizontal clustering.
        
        Args:
            blocks: Text blocks
            page_width: Page width
            
        Returns:
            List of (x_start, x_end) tuples for each column
        """
        if not blocks:
            return [(0, page_width)]
        
        # Get horizontal centers of all blocks
        centers = []
        for block in blocks:
            x0, _, x1, _ = block.bbox
            center_x = (x0 + x1) / 2
            centers.append(center_x)
        
        # Sort centers
        centers = sorted(centers)
        
        # Find gaps larger than threshold
        columns = []
        col_start = 0
        
        for i in range(len(centers) - 1):
            gap = centers[i + 1] - centers[i]
            if gap > self.column_gap_threshold:
                # Found column boundary
                col_end = (centers[i] + centers[i + 1]) / 2
                columns.append((col_start, col_end))
                col_start = col_end
        
        # Add final column
        columns.append((col_start, page_width))
        
        # If only one column detected, just use full width
        if len(columns) == 1:
            return [(0, page_width)]
        
        return columns
    
    def _detect_special_regions(
        self,
        blocks: List[TextBlock],
        page_width: float,
        page_height: float
    ) -> List[LayoutRegion]:
        """
        Detect headers, footers, and sidebars.
        
        Args:
            blocks: Text blocks
            page_width: Page width
            page_height: Page height
            
        Returns:
            List of detected special regions
        """
        regions = []
        
        for i, block in enumerate(blocks):
            x0, y0, x1, y1 = block.bbox
            
            # Header detection (top of page)
            if y0 < self.header_height_threshold:
                regions.append(LayoutRegion(
                    region_type="header",
                    bbox=block.bbox,
                    reading_order=0,  # Headers come first
                    confidence=0.9
                ))
            
            # Footer detection (bottom of page)
            elif y0 > self.footer_y_threshold:
                regions.append(LayoutRegion(
                    region_type="footer",
                    bbox=block.bbox,
                    reading_order=9999,  # Footers come last
                    confidence=0.9
                ))
            
            # Sidebar detection (narrow column on edge)
            elif (x1 - x0) < page_width * 0.2:  # Less than 20% of page width
                if x0 < page_width * 0.1 or x1 > page_width * 0.9:
                    regions.append(LayoutRegion(
                        region_type="sidebar",
                        bbox=block.bbox,
                        reading_order=-1,  # Will be assigned later
                        confidence=0.7
                    ))
        
        return regions
    
    def _assign_reading_order(
        self,
        blocks: List[TextBlock | TableBlock | PictureBlock],
        columns: List[Tuple[float, float]],
        special_regions: List[LayoutRegion]
    ) -> dict:
        """
        Assign reading order to all blocks.
        
        Strategy:
        1. Headers first (order 0-99)
        2. Main content by column, top to bottom (order 100+)
        3. Footers last (order 9000+)
        
        Args:
            blocks: All blocks
            columns: Column boundaries
            special_regions: Headers, footers, sidebars
            
        Returns:
            Dictionary mapping block index to reading order
        """
        reading_order_map = {}
        
        # Create special region lookup
        special_bboxes = {
            r.region_type: [r.bbox for r in special_regions if r.region_type == r.region_type]
            for r in special_regions
        }
        
        order = 100  # Start after headers
        
        # Process each column from left to right
        for col_idx, (col_start, col_end) in enumerate(columns):
            # Get blocks in this column, sort top to bottom
            col_blocks = []
            for i, block in enumerate(blocks):
                x0, y0, x1, y1 = block.bbox
                center_x = (x0 + x1) / 2
                
                # Skip special regions
                if self._is_special_region(block.bbox, special_regions):
                    continue
                
                # Check if block is in this column
                if col_start <= center_x <= col_end:
                    col_blocks.append((i, block, y0))
            
            # Sort by y-position (top to bottom)
            col_blocks.sort(key=lambda x: x[2])
            
            # Assign reading order
            for block_idx, block, _ in col_blocks:
                reading_order_map[block_idx] = order
                order += 1
        
        # Assign special regions
        for i, block in enumerate(blocks):
            if i in reading_order_map:
                continue
            
            # Check if header
            if any(self._bbox_overlap(block.bbox, hbbox) 
                   for hbbox in special_bboxes.get("header", [])):
                reading_order_map[i] = 0
            
            # Check if footer
            elif any(self._bbox_overlap(block.bbox, fbbox) 
                     for fbbox in special_bboxes.get("footer", [])):
                reading_order_map[i] = 9000
            
            else:
                # Default fallback
                reading_order_map[i] = order
                order += 1
        
        return reading_order_map
    
    def _is_special_region(
        self,
        bbox: Tuple[float, float, float, float],
        special_regions: List[LayoutRegion]
    ) -> bool:
        """Check if bbox overlaps with any special region."""
        for region in special_regions:
            if self._bbox_overlap(bbox, region.bbox):
                return True
        return False
    
    def _bbox_overlap(
        self,
        bbox1: Tuple[float, float, float, float],
        bbox2: Tuple[float, float, float, float],
        threshold: float = 0.5
    ) -> bool:
        """Check if two bboxes overlap significantly."""
        x0_1, y0_1, x1_1, y1_1 = bbox1
        x0_2, y0_2, x1_2, y1_2 = bbox2
        
        # Calculate intersection
        x_overlap = max(0, min(x1_1, x1_2) - max(x0_1, x0_2))
        y_overlap = max(0, min(y1_1, y1_2) - max(y0_1, y0_2))
        
        if x_overlap == 0 or y_overlap == 0:
            return False
        
        intersection_area = x_overlap * y_overlap
        bbox1_area = (x1_1 - x0_1) * (y1_1 - y0_1)
        
        if bbox1_area == 0:
            return False
        
        overlap_ratio = intersection_area / bbox1_area
        return overlap_ratio > threshold
    
    def reorder_blocks(
        self,
        blocks: List[TextBlock | TableBlock | PictureBlock],
        layout: LayoutAnalysis
    ) -> List[TextBlock | TableBlock | PictureBlock]:
        """
        Reorder blocks according to detected reading order.
        
        Args:
            blocks: Original blocks
            layout: Layout analysis with reading order
            
        Returns:
            Blocks sorted by reading order
        """
        # Create list of (block, order) tuples
        ordered = []
        for i, block in enumerate(blocks):
            order = layout.reading_order_map.get(i, 9999)
            ordered.append((block, order))
        
        # Sort by reading order
        ordered.sort(key=lambda x: x[1])
        
        # Return just blocks
        return [block for block, _ in ordered]
