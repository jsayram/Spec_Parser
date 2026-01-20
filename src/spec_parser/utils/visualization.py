"""
Visualization debug utility for annotated PDF pages.

Overlays colored bounding boxes on PDF pages to visualize extraction results.
Based on LandingAI agentic-doc viz_parsed_document pattern.
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pymupdf
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle


# Default color scheme for different block types (RGB values 0-1)
DEFAULT_COLORS = {
    "text": (0.2, 0.6, 0.2),      # Green
    "picture": (0.8, 0.4, 0.0),   # Orange
    "table": (0.2, 0.4, 0.8),     # Blue
    "graphics": (0.6, 0.2, 0.6),  # Purple
    "ocr": (0.8, 0.2, 0.2),       # Red (for OCR regions)
}


class VisualizationRenderer:
    """Render annotated PDF pages with extraction overlays."""
    
    def __init__(
        self,
        output_dir: Path,
        colors: Optional[Dict[str, Tuple[float, float, float]]] = None,
        line_width: float = 2.0,
        show_labels: bool = True,
        label_font_size: float = 8.0,
        dpi: int = 150,
        opacity: float = 0.3,
    ):
        """Initialize visualization renderer.
        
        Args:
            output_dir: Directory for rendered visualizations
            colors: Dict mapping block types to RGB tuples (0-1 range)
            line_width: Width of bounding box lines
            show_labels: Whether to show block type labels
            label_font_size: Font size for labels
            dpi: Output image resolution
            opacity: Fill opacity for bounding boxes (0-1)
        """
        self.output_dir = Path(output_dir)
        self.colors = colors or DEFAULT_COLORS
        self.line_width = line_width
        self.show_labels = show_labels
        self.label_font_size = label_font_size
        self.dpi = dpi
        self.opacity = opacity
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def render_page(
        self,
        doc: pymupdf.Document,
        bundle: PageBundle,
        page_num: int,
    ) -> Optional[Path]:
        """Render a single page with block overlays.
        
        Args:
            doc: PyMuPDF document
            bundle: PageBundle with extracted blocks
            page_num: Page number (1-indexed)
            
        Returns:
            Path to rendered image, or None if failed
        """
        try:
            page = doc[page_num - 1]
            
            # Create a shape object for drawing
            shape = page.new_shape()
            
            # Draw text blocks
            for block in bundle.get_blocks_by_type("text"):
                self._draw_bbox(
                    shape, block.bbox, "text",
                    label=f"text:{block.citation[:20]}" if self.show_labels else None
                )
            
            # Draw picture blocks
            for block in bundle.get_blocks_by_type("picture"):
                source_label = "ocr" if block.source == "ocr" else "picture"
                self._draw_bbox(
                    shape, block.bbox, source_label,
                    label=f"img:{block.citation[:20]}" if self.show_labels else None
                )
            
            # Draw table blocks
            for block in bundle.get_blocks_by_type("table"):
                self._draw_bbox(
                    shape, block.bbox, "table",
                    label=f"tbl:{block.citation[:20]}" if self.show_labels else None
                )
            
            # Draw graphics blocks
            for block in bundle.get_blocks_by_type("graphics"):
                self._draw_bbox(
                    shape, block.bbox, "graphics",
                    label=f"gfx:{block.citation[:20]}" if self.show_labels else None
                )
            
            # Commit all drawings
            shape.commit()
            
            # Render to pixmap
            zoom = self.dpi / 72
            matrix = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            
            # Save output
            output_path = self.output_dir / f"page_{page_num:04d}_annotated.png"
            pix.save(str(output_path))
            
            # Count blocks for logging
            block_counts = {
                "text": len(bundle.get_blocks_by_type("text")),
                "picture": len(bundle.get_blocks_by_type("picture")),
                "table": len(bundle.get_blocks_by_type("table")),
                "graphics": len(bundle.get_blocks_by_type("graphics")),
            }
            total_blocks = sum(block_counts.values())
            
            logger.debug(
                f"Rendered page {page_num} with {total_blocks} blocks: "
                f"{block_counts}"
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to render page {page_num}: {e}")
            return None
    
    def _draw_bbox(
        self,
        shape,
        bbox: Tuple[float, float, float, float],
        block_type: str,
        label: Optional[str] = None,
    ):
        """Draw a single bounding box with optional label.
        
        Args:
            shape: PyMuPDF Shape object
            bbox: Bounding box (x0, y0, x1, y1)
            block_type: Type of block for color selection
            label: Optional label text
        """
        color = self.colors.get(block_type, (0.5, 0.5, 0.5))
        rect = pymupdf.Rect(bbox)
        
        # Draw rectangle outline
        shape.draw_rect(rect)
        shape.finish(
            color=color,
            fill=color,
            fill_opacity=self.opacity,
            width=self.line_width,
        )
        
        # Draw label if enabled
        if label and self.show_labels:
            # Position label at top-left of bbox
            label_point = pymupdf.Point(bbox[0] + 2, bbox[1] + self.label_font_size + 2)
            
            # Create text with contrasting background
            shape.insert_text(
                label_point,
                label,
                fontsize=self.label_font_size,
                color=color,
            )
    
    def render_all_pages(
        self,
        pdf_path: Path,
        bundles: List[PageBundle],
    ) -> List[Path]:
        """Render all pages with block overlays.
        
        Args:
            pdf_path: Path to source PDF
            bundles: List of PageBundle objects
            
        Returns:
            List of paths to rendered images
        """
        rendered = []
        
        with pymupdf.open(pdf_path) as doc:
            for bundle in bundles:
                output_path = self.render_page(doc, bundle, bundle.page)
                if output_path:
                    rendered.append(output_path)
        
        logger.info(f"Rendered {len(rendered)}/{len(bundles)} pages to {self.output_dir}")
        
        return rendered
    
    def create_summary_image(
        self,
        pdf_path: Path,
        bundles: List[PageBundle],
        max_pages: int = 10,
    ) -> Optional[Path]:
        """Create a summary grid image of first N pages.
        
        Args:
            pdf_path: Path to source PDF
            bundles: List of PageBundle objects
            max_pages: Maximum pages to include in summary
            
        Returns:
            Path to summary image, or None if failed
        """
        # This would require PIL/Pillow for grid composition
        # For now, just render individual pages
        logger.info(f"Summary image creation: rendering first {max_pages} pages")
        
        bundles_subset = bundles[:max_pages]
        return self.render_all_pages(pdf_path, bundles_subset)


def visualize_extraction(
    pdf_path: Path,
    bundles: List[PageBundle],
    output_dir: Path,
    dpi: int = 150,
    show_labels: bool = True,
) -> List[Path]:
    """Convenience function to visualize all extraction results.
    
    Args:
        pdf_path: Path to source PDF
        bundles: List of extracted PageBundle objects
        output_dir: Directory for visualization output
        dpi: Image resolution (default 150)
        show_labels: Whether to show block type labels
        
    Returns:
        List of paths to rendered images
    """
    renderer = VisualizationRenderer(
        output_dir=output_dir,
        dpi=dpi,
        show_labels=show_labels,
    )
    
    return renderer.render_all_pages(pdf_path, bundles)


def create_comparison_view(
    pdf_path: Path,
    bundles_before: List[PageBundle],
    bundles_after: List[PageBundle],
    output_dir: Path,
    page_num: int,
) -> Tuple[Optional[Path], Optional[Path]]:
    """Create before/after comparison for a specific page.
    
    Useful for debugging extraction improvements.
    
    Args:
        pdf_path: Path to source PDF
        bundles_before: PageBundles before change
        bundles_after: PageBundles after change
        output_dir: Directory for output
        page_num: Page to compare
        
    Returns:
        Tuple of (before_path, after_path)
    """
    renderer = VisualizationRenderer(output_dir=output_dir)
    
    # Find bundles for the specified page
    bundle_before = next((b for b in bundles_before if b.page == page_num), None)
    bundle_after = next((b for b in bundles_after if b.page == page_num), None)
    
    before_path = None
    after_path = None
    
    with pymupdf.open(pdf_path) as doc:
        if bundle_before:
            renderer.output_dir = output_dir / "before"
            renderer.output_dir.mkdir(parents=True, exist_ok=True)
            before_path = renderer.render_page(doc, bundle_before, page_num)
        
        if bundle_after:
            renderer.output_dir = output_dir / "after"
            renderer.output_dir.mkdir(parents=True, exist_ok=True)
            after_path = renderer.render_page(doc, bundle_after, page_num)
    
    return before_path, after_path
