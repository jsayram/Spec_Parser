#!/usr/bin/env python3
"""
Demo script to visualize PDF extraction on first 30 pages.
Shows colored bounding boxes around extracted blocks.
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.utils.visualization import VisualizationRenderer
from spec_parser.utils.grounding_export import GroundingExporter
from loguru import logger


def main():
    # Paths
    pdf_path = Path("/Users/jramirez/Git/Spec_Parser/data/specs/03_Quidel_Sofia_LIS_Specification_POCT1a.pdf")
    output_dir = Path("/Users/jramirez/Git/Spec_Parser/data/output/extraction_debug")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"PDF: {pdf_path.name}")
    logger.info(f"Output: {output_dir}")
    logger.info("Extracting first 30 pages with visualization...")
    
    # Extract pages
    with PyMuPDFExtractor(pdf_path) as extractor:
        # Get total page count
        total_pages = len(extractor.doc)
        pages_to_extract = min(30, total_pages)
        logger.info(f"Total pages: {total_pages}, extracting: {pages_to_extract}")
        
        # Extract first 30 pages in parallel
        bundles = extractor.extract_all_pages(
            max_pages=pages_to_extract,
            max_workers=4,
            parallel=True
        )
        
        logger.info(f"Extracted {len(bundles)} page bundles")
        
        # Show block stats
        total_blocks = sum(len(b.blocks) for b in bundles)
        logger.info(f"Total blocks extracted: {total_blocks}")
        
        # Block type breakdown
        block_types = {}
        for bundle in bundles:
            for block in bundle.blocks:
                block_type = block.type
                block_types[block_type] = block_types.get(block_type, 0) + 1
        
        logger.info("Block types found:")
        for bt, count in sorted(block_types.items(), key=lambda x: -x[1]):
            logger.info(f"  {bt}: {count}")
        
        # Create visualizations
        logger.info("\n--- Creating Visualizations ---")
        
        # 1. Annotated pages with bounding boxes
        viz_dir = output_dir / "annotated_pages"
        viz_dir.mkdir(parents=True, exist_ok=True)
        
        renderer = VisualizationRenderer(
            output_dir=viz_dir,
            dpi=150,
            show_labels=True,
        )
        
        rendered_pages = renderer.render_all_pages(
            pdf_path=pdf_path,
            bundles=bundles,
        )
        logger.info(f"Created {len(rendered_pages)} annotated page images in {viz_dir}")
        
        # 2. Grounding exports (cropped blocks)
        grounding_dir = output_dir / "block_crops"
        grounding_dir.mkdir(parents=True, exist_ok=True)
        
        exporter = GroundingExporter(output_dir=grounding_dir, dpi=200)
        exported = exporter.export_all_pages(
            pdf_path=pdf_path,
            bundles=bundles,
        )
        logger.info(f"Exported {len(exported)} block crops to {grounding_dir}")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("VISUALIZATION DEMO COMPLETE")
        logger.info("=" * 60)
        logger.info(f"\nOutput locations:")
        logger.info(f"  📁 Annotated pages: {viz_dir}")
        logger.info(f"  📁 Block crops:     {grounding_dir}")
        logger.info(f"\nTo view results:")
        logger.info(f"  open {output_dir}")


if __name__ == "__main__":
    main()
