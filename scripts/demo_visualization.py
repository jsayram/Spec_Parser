#!/usr/bin/env python3
"""
Demo script to visualize PDF extraction with bounding boxes.
Shows colored overlays for text, tables, images, and graphics blocks.

Usage:
    python scripts/demo_visualization.py <pdf_path> [--pages N] [--output DIR]
    
Examples:
    python scripts/demo_visualization.py data/specs/my_spec.pdf
    python scripts/demo_visualization.py data/specs/my_spec.pdf --pages 10
    python scripts/demo_visualization.py data/specs/my_spec.pdf --output data/debug_output/my_viz
"""

from pathlib import Path
import sys
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor
from spec_parser.utils.visualization import VisualizationRenderer
from spec_parser.utils.grounding_export import GroundingExporter
from loguru import logger


def main():
    parser = argparse.ArgumentParser(
        description="Visualize PDF extraction with colored bounding boxes"
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to PDF file to visualize"
    )
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=30,
        help="Max pages to extract (default: 30, use 0 for all)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output directory (default: data/debug_output/extraction_viz/<pdf_name>)"
    )
    parser.add_argument(
        "--outline",
        action="store_true",
        help="Use outline-only boxes (no fill) for tighter look"
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Hide citation labels for cleaner view"
    )
    
    args = parser.parse_args()
    
    # Validate PDF exists
    pdf_path = args.pdf_path.resolve()
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    # Set output directory
    if args.output:
        output_dir = args.output.resolve()
    else:
        project_root = Path(__file__).parent.parent
        output_dir = project_root / "data" / "debug_output" / "extraction_viz" / pdf_path.stem
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"PDF: {pdf_path.name}")
    logger.info(f"Output: {output_dir}")
    
    # Determine pages to extract
    max_pages = args.pages if args.pages > 0 else None
    
    # Extract pages
    with PyMuPDFExtractor(pdf_path) as extractor:
        # Get total page count
        total_pages = len(extractor.doc)
        pages_to_extract = min(max_pages, total_pages) if max_pages else total_pages
        logger.info(f"Total pages: {total_pages}, extracting: {pages_to_extract}")
        
        # Extract pages in parallel
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
            show_labels=not args.no_labels,
            opacity=0.0 if args.outline else 0.3,  # No fill for outline mode
            line_width=1.0 if args.outline else 2.0,  # Thinner lines for outline
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
