#!/usr/bin/env python
"""
Phase 2.5: Entity Extraction

Run structured entity extraction on Phase 2 output.
Extracts messages, fields, configuration, errors, etc. from parsed tables.

Usage:
    python test_phase2_5.py <spec_output_dir>

Example:
    python test_phase2_5.py data/spec_output/20260118_003024_cobaliatsystemhimpoc/
"""

import sys
import json
from pathlib import Path
from loguru import logger

from spec_parser.parsers.table_parser import TableParser
from spec_parser.extractors.message_extractor import MessageExtractor
from spec_parser.utils.logger import setup_logger


def extract_entities(spec_output_dir: Path):
    """
    Extract structured entities from Phase 2 output.
    
    Args:
        spec_output_dir: Directory containing Phase 2 output
                         (json/, markdown/, etc.)
    """
    logger.info(f"Starting entity extraction from: {spec_output_dir}")
    
    # Validate directory structure
    json_dir = spec_output_dir / "json"
    markdown_dir = spec_output_dir / "markdown"
    
    if not json_dir.exists():
        logger.error(f"JSON directory not found: {json_dir}")
        sys.exit(1)
    
    if not markdown_dir.exists():
        logger.error(f"Markdown directory not found: {markdown_dir}")
        sys.exit(1)
    
    # Load JSON sidecar
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        logger.error(f"No JSON files found in {json_dir}")
        sys.exit(1)
    
    json_file = json_files[0]
    logger.info(f"Loading JSON: {json_file.name}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    # Load master markdown
    master_files = list(markdown_dir.glob("*_MASTER.md"))
    if not master_files:
        logger.error(f"No master markdown file found in {markdown_dir}")
        sys.exit(1)
    
    master_file = master_files[0]
    logger.info(f"Loading markdown: {master_file.name}")
    
    with open(master_file, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    # Step 1: Parse all tables
    logger.info("Parsing tables...")
    table_parser = TableParser()
    tables = table_parser.parse_all_tables(json_data)
    
    logger.success(f"✓ Parsed {len(tables)} tables")
    
    # Show table statistics
    if tables:
        total_rows = sum(len(t) for t in tables)
        pages_with_tables = len(set(t.page for t in tables))
        logger.info(f"  Total rows: {total_rows}")
        logger.info(f"  Pages with tables: {pages_with_tables}")
        logger.info(f"  Average rows per table: {total_rows / len(tables):.1f}")
    
    # Step 2: Extract messages
    logger.info("Extracting message definitions...")
    msg_extractor = MessageExtractor()
    messages = msg_extractor.extract(tables, markdown_content, json_data)
    
    logger.success(f"✓ Extracted {len(messages)} message definitions")
    
    # Show message statistics
    if messages:
        standard_msgs = [m for m in messages if not m.get("vendor_specific")]
        vendor_msgs = [m for m in messages if m.get("vendor_specific")]
        
        logger.info(f"  Standard messages: {len(standard_msgs)}")
        logger.info(f"  Vendor-specific messages: {len(vendor_msgs)}")
        
        # Show some examples
        logger.info("\n  Sample messages:")
        for msg in messages[:5]:
            msg_id = msg["message_id"]
            segments = len(msg.get("segments", []))
            method = msg.get("extraction_method", "unknown")
            logger.info(f"    • {msg_id} ({segments} segments, method: {method})")
    
    # Step 3: Save entities
    entities_dir = spec_output_dir / "entities"
    entities_dir.mkdir(exist_ok=True)
    
    logger.info(f"Saving entities to: {entities_dir}")
    
    # Save messages
    messages_file = entities_dir / "messages.json"
    msg_extractor.save(messages_file)
    
    # Save table summary
    table_summary = {
        "total_tables": len(tables),
        "tables_by_page": {},
        "tables": [
            {
                "page": t.page,
                "headers": t.headers,
                "row_count": len(t),
                "citation": t.citation
            }
            for t in tables
        ]
    }
    
    # Group by page
    for table in tables:
        page = table.page
        table_summary["tables_by_page"][page] = \
            table_summary["tables_by_page"].get(page, 0) + 1
    
    tables_file = entities_dir / "tables_summary.json"
    with open(tables_file, 'w', encoding='utf-8') as f:
        json.dump(table_summary, f, indent=2)
    
    logger.success(f"✓ Saved tables summary to {tables_file}")
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.success("✅ Phase 2.5 Complete!")
    logger.info(f"   Output: {entities_dir}")
    logger.info(f"   Tables: {len(tables)}")
    logger.info(f"   Messages: {len(messages)}")
    logger.info(f"   Files:")
    logger.info(f"     • {messages_file.name}")
    logger.info(f"     • {tables_file.name}")
    logger.info("="*80)


def main():
    """Main entry point"""
    setup_logger()
    
    if len(sys.argv) < 2:
        print("Usage: python test_phase2_5.py <spec_output_dir>")
        print("\nExample:")
        print("  python test_phase2_5.py data/spec_output/20260118_003024_cobaliatsystemhimpoc/")
        sys.exit(1)
    
    spec_output_dir = Path(sys.argv[1])
    
    if not spec_output_dir.exists():
        logger.error(f"Directory not found: {spec_output_dir}")
        sys.exit(1)
    
    extract_entities(spec_output_dir)


if __name__ == "__main__":
    main()
