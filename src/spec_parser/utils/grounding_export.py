"""
Grounding export utility for visual block snippets.

Exports cropped images of extracted blocks for human review and debugging.
Based on LandingAI agentic-doc patterns for grounding visualization.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import pymupdf
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle, TextBlock, PictureBlock, TableBlock
from spec_parser.schemas.citation import Citation


class GroundingExporter:
    """Export visual groundings of extracted blocks as images."""
    
    def __init__(
        self,
        output_dir: Path,
        dpi: int = 150,
        padding: int = 10,
        image_format: str = "png",
        include_text: bool = True,
        include_pictures: bool = True,
        include_tables: bool = True,
    ):
        """Initialize grounding exporter.
        
        Args:
            output_dir: Base directory for grounding exports
            dpi: Resolution for rendered images (default 150)
            padding: Pixels of padding around each crop (default 10)
            image_format: Output format - png, jpg (default png)
            include_text: Export text block groundings
            include_pictures: Export picture block groundings
            include_tables: Export table block groundings
        """
        self.output_dir = Path(output_dir)
        self.dpi = dpi
        self.padding = padding
        self.image_format = image_format.lower()
        self.include_text = include_text
        self.include_pictures = include_pictures
        self.include_tables = include_tables
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_page_groundings(
        self,
        doc: pymupdf.Document,
        bundle: PageBundle,
        page_num: int,
    ) -> Dict[str, Path]:
        """Export all block groundings for a single page.
        
        Args:
            doc: PyMuPDF document object
            bundle: PageBundle with extracted blocks
            page_num: Page number (1-indexed)
            
        Returns:
            Dict mapping citation_id to exported file path
        """
        page = doc[page_num - 1]  # 0-indexed
        page_dir = self.output_dir / f"page_{page_num:04d}"
        page_dir.mkdir(exist_ok=True)
        
        exported = {}
        block_counts = {"text": 0, "picture": 0, "table": 0}
        
        # Export text blocks
        if self.include_text:
            for block in bundle.get_blocks_by_type("text"):
                block_counts["text"] += 1
                file_path = self._export_block(
                    page, block.bbox, 
                    f"text_{block_counts['text']:03d}",
                    page_dir, block.citation
                )
                if file_path:
                    exported[block.citation] = file_path
        
        # Export picture blocks
        if self.include_pictures:
            for block in bundle.get_blocks_by_type("picture"):
                block_counts["picture"] += 1
                file_path = self._export_block(
                    page, block.bbox,
                    f"picture_{block_counts['picture']:03d}",
                    page_dir, block.citation
                )
                if file_path:
                    exported[block.citation] = file_path
        
        # Export table blocks
        if self.include_tables:
            for block in bundle.get_blocks_by_type("table"):
                block_counts["table"] += 1
                file_path = self._export_block(
                    page, block.bbox,
                    f"table_{block_counts['table']:03d}",
                    page_dir, block.citation
                )
                if file_path:
                    exported[block.citation] = file_path
        
        logger.debug(
            f"Exported {len(exported)} groundings for page {page_num}: "
            f"{block_counts['text']} text, {block_counts['picture']} pictures, "
            f"{block_counts['table']} tables"
        )
        
        return exported
    
    def _export_block(
        self,
        page: pymupdf.Page,
        bbox: Tuple[float, float, float, float],
        block_name: str,
        output_dir: Path,
        citation_id: str,
    ) -> Optional[Path]:
        """Export a single block as an image.
        
        Args:
            page: PyMuPDF page object
            bbox: Block bounding box (x0, y0, x1, y1)
            block_name: Descriptive name for the block
            output_dir: Directory to save the image
            citation_id: Citation ID for the block
            
        Returns:
            Path to exported image, or None if failed
        """
        try:
            # Add padding to bbox
            x0, y0, x1, y1 = bbox
            padded_rect = pymupdf.Rect(
                max(0, x0 - self.padding),
                max(0, y0 - self.padding),
                min(page.rect.width, x1 + self.padding),
                min(page.rect.height, y1 + self.padding),
            )
            
            # Render the clipped region at specified DPI
            zoom = self.dpi / 72  # 72 is default PDF DPI
            matrix = pymupdf.Matrix(zoom, zoom)
            
            # Create pixmap of the region
            pix = page.get_pixmap(matrix=matrix, clip=padded_rect)
            
            # Save to file
            safe_citation = citation_id.replace("/", "_").replace("\\", "_")
            file_name = f"{block_name}_{safe_citation}.{self.image_format}"
            file_path = output_dir / file_name
            
            pix.save(str(file_path))
            
            return file_path
            
        except Exception as e:
            logger.warning(f"Failed to export grounding for {block_name}: {e}")
            return None
    
    def export_all_pages(
        self,
        pdf_path: Path,
        bundles: List[PageBundle],
    ) -> Dict[str, Path]:
        """Export groundings for all pages.
        
        Args:
            pdf_path: Path to the PDF file
            bundles: List of PageBundle objects
            
        Returns:
            Dict mapping all citation_ids to exported file paths
        """
        all_exported = {}
        
        with pymupdf.open(pdf_path) as doc:
            for bundle in bundles:
                page_exports = self.export_page_groundings(
                    doc, bundle, bundle.page
                )
                all_exported.update(page_exports)
        
        logger.info(
            f"Exported {len(all_exported)} total groundings to {self.output_dir}"
        )
        
        return all_exported
    
    def export_citation(
        self,
        pdf_path: Path,
        citation: Citation,
    ) -> Optional[Path]:
        """Export a single citation as a grounding image.
        
        Args:
            pdf_path: Path to the PDF file
            citation: Citation object with page and bbox
            
        Returns:
            Path to exported image, or None if failed
        """
        try:
            with pymupdf.open(pdf_path) as doc:
                page = doc[citation.page - 1]
                
                # Create output filename from citation
                output_path = self._export_block(
                    page,
                    citation.bbox,
                    f"citation_{citation.source}",
                    self.output_dir,
                    citation.citation_id,
                )
                
                return output_path
                
        except Exception as e:
            logger.error(f"Failed to export citation {citation.citation_id}: {e}")
            return None


def export_groundings(
    pdf_path: Path,
    bundles: List[PageBundle],
    output_dir: Path,
    dpi: int = 150,
    padding: int = 10,
) -> Dict[str, Path]:
    """Convenience function to export all groundings.
    
    Args:
        pdf_path: Path to source PDF
        bundles: List of extracted PageBundle objects
        output_dir: Directory for grounding exports
        dpi: Image resolution (default 150)
        padding: Padding around crops (default 10)
        
    Returns:
        Dict mapping citation_ids to exported file paths
    """
    exporter = GroundingExporter(
        output_dir=output_dir,
        dpi=dpi,
        padding=padding,
    )
    
    return exporter.export_all_pages(pdf_path, bundles)
