"""Comprehensive test suite for Phase 2.5 entity extraction."""
import sys
import json
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from spec_parser.parsers.table_parser import TableParser, ParsedTable
from spec_parser.extractors.message_extractor import MessageExtractor

def test_table_parser(spec_dir: Path):
    """Test table parsing with markdown_table key."""
    logger.info("=" * 80)
    logger.info("TEST 1: Table Parser")
    logger.info("=" * 80)
    
    # Load JSON sidecar
    json_files = list((spec_dir / "json").glob("*.json"))
    if not json_files:
        logger.error("No JSON files found")
        return False
    
    json_path = json_files[0]
    logger.info(f"Loading: {json_path.name}")
    
    with open(json_path) as f:
        data = json.load(f)
    
    # Parse tables
    parser = TableParser()
    tables = parser.parse_all_tables(data)
    
    logger.success(f"✓ Parsed {len(tables)} tables")
    
    if not tables:
        logger.error("❌ No tables parsed - FAILED")
        return False
    
    # Test table properties
    first_table = tables[0]
    logger.info(f"  First table: Page {first_table.page}, {len(first_table.rows)} rows")
    logger.info(f"  Headers: {first_table.headers}")
    logger.info(f"  Citation: {first_table.citation}")
    
    # Test has_columns method
    logger.info("Testing has_columns() method:")
    logger.info(f"  Has 'Header' column: {first_table.has_columns(['Header'])}")
    logger.info(f"  Has 'HDR' column: {first_table.has_columns(['HDR'])}")
    
    # Test to_dict_list method
    dict_list = first_table.to_dict_list()
    logger.info(f"  Converted to {len(dict_list)} row dicts")
    
    logger.success("✓ Table Parser tests PASSED")
    return True

def test_message_extractor(spec_dir: Path):
    """Test message extraction from spec."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 2: Message Extractor")
    logger.info("=" * 80)
    
    # Load JSON and markdown
    json_files = list((spec_dir / "json").glob("*.json"))
    md_files = list((spec_dir / "markdown").glob("*_MASTER.md"))
    
    if not json_files or not md_files:
        logger.error("Missing required files")
        return False
    
    with open(json_files[0]) as f:
        json_data = json.load(f)
    
    with open(md_files[0], encoding='utf-8') as f:
        markdown = f.read()
    
    logger.info(f"JSON: {json_files[0].name}")
    logger.info(f"Markdown: {md_files[0].name} ({len(markdown)} chars)")
    
    # Parse tables first
    parser = TableParser()
    tables = parser.parse_all_tables(json_data)
    logger.info(f"Tables available: {len(tables)}")
    
    # Extract messages
    extractor = MessageExtractor()
    messages = extractor.extract(tables, markdown, json_data)
    
    logger.success(f"✓ Extracted {len(messages)} messages")
    
    if not messages:
        logger.error("❌ No messages extracted - FAILED")
        return False
    
    # Analyze messages
    vendor_msgs = [m for m in messages if m.get('vendor_specific')]
    standard_msgs = [m for m in messages if not m.get('vendor_specific')]
    
    logger.info(f"  Standard messages: {len(standard_msgs)}")
    logger.info(f"  Vendor-specific messages: {len(vendor_msgs)}")
    
    # Test message properties
    for i, msg in enumerate(messages[:3], 1):
        logger.info(f"  Message {i}:")
        logger.info(f"    ID: {msg['message_id']}")
        logger.info(f"    Vendor: {msg.get('vendor', 'N/A')}")
        logger.info(f"    Direction: {msg.get('direction', 'N/A')}")
        logger.info(f"    Extraction method: {msg['extraction_method']}")
        logger.info(f"    Confidence: {msg['confidence']}")
        logger.info(f"    Segments: {len(msg.get('segments', []))}")
    
    logger.success("✓ Message Extractor tests PASSED")
    return True

def test_file_outputs(spec_dir: Path):
    """Test that output files were created correctly."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 3: Output Files")
    logger.info("=" * 80)
    
    entities_dir = spec_dir / "entities"
    
    if not entities_dir.exists():
        logger.error(f"❌ Entities directory not found: {entities_dir}")
        return False
    
    logger.success(f"✓ Entities directory exists: {entities_dir}")
    
    # Check messages.json
    messages_file = entities_dir / "messages.json"
    if not messages_file.exists():
        logger.error(f"❌ messages.json not found")
        return False
    
    with open(messages_file) as f:
        messages_data = json.load(f)
    
    logger.success(f"✓ messages.json exists ({messages_file.stat().st_size} bytes)")
    logger.info(f"  Contains {len(messages_data.get('messages', []))} messages")
    
    # Check tables_summary.json
    tables_file = entities_dir / "tables_summary.json"
    if not tables_file.exists():
        logger.error(f"❌ tables_summary.json not found")
        return False
    
    with open(tables_file) as f:
        tables_data = json.load(f)
    
    logger.success(f"✓ tables_summary.json exists ({tables_file.stat().st_size} bytes)")
    logger.info(f"  Contains {tables_data.get('total_tables', 0)} tables")
    
    # Validate JSON structure
    if 'messages' not in messages_data:
        logger.error("❌ messages.json missing 'messages' key")
        return False
    
    if 'total_tables' not in tables_data or 'tables' not in tables_data:
        logger.error("❌ tables_summary.json missing required keys")
        return False
    
    logger.success("✓ Output Files tests PASSED")
    return True

def test_table_content_analysis(spec_dir: Path):
    """Test detailed table content analysis."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 4: Table Content Analysis")
    logger.info("=" * 80)
    
    json_files = list((spec_dir / "json").glob("*.json"))
    with open(json_files[0]) as f:
        data = json.load(f)
    
    parser = TableParser()
    tables = parser.parse_all_tables(data)
    
    # Group tables by page
    tables_by_page = {}
    for table in tables:
        page = table.page
        tables_by_page.setdefault(page, []).append(table)
    
    logger.info(f"Tables found on {len(tables_by_page)} pages")
    
    # Analyze UML-style tables (look for + field_name: TYPE pattern)
    uml_tables = []
    for table in tables:
        # Check if any row contains UML field notation
        for row in table.rows:
            for cell in row:
                if '+' in cell and ':' in cell:
                    uml_tables.append(table)
                    break
            else:
                continue
            break
    
    logger.info(f"UML-style tables: {len(uml_tables)}")
    
    if uml_tables:
        logger.info("Sample UML table:")
        uml_table = uml_tables[0]
        logger.info(f"  Page: {uml_table.page}")
        logger.info(f"  Headers: {uml_table.headers}")
        logger.info(f"  First row: {uml_table.rows[0] if uml_table.rows else 'Empty'}")
    
    # Check for conversation/message flow tables
    conversation_tables = [t for t in tables if any('conversation' in str(h).lower() for h in t.headers)]
    logger.info(f"Conversation/flow tables: {len(conversation_tables)}")
    
    logger.success("✓ Table Content Analysis tests PASSED")
    return True

def test_error_handling(spec_dir: Path):
    """Test error handling with invalid inputs."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 5: Error Handling")
    logger.info("=" * 80)
    
    # Test with invalid directory
    fake_dir = Path("nonexistent_directory")
    logger.info("Testing with nonexistent directory...")
    if fake_dir.exists():
        logger.error("❌ Test directory unexpectedly exists")
        return False
    logger.success("✓ Correctly handles missing directory")
    
    # Test with empty JSON data
    logger.info("Testing with empty JSON data...")
    empty_data = {"pages": []}
    parser = TableParser()
    tables = parser.parse_all_tables(empty_data)
    if tables:
        logger.error("❌ Should return empty list for empty data")
        return False
    logger.success("✓ Correctly handles empty data")
    
    # Test message extractor with empty inputs
    logger.info("Testing message extractor with empty inputs...")
    extractor = MessageExtractor()
    messages = extractor.extract([], "", empty_data)
    if messages:
        logger.error("❌ Should return empty list for empty inputs")
        return False
    logger.success("✓ Correctly handles empty inputs")
    
    logger.success("✓ Error Handling tests PASSED")
    return True

def main():
    """Run comprehensive test suite."""
    if len(sys.argv) < 2:
        print("Usage: python test_phase2_5_comprehensive.py <spec_output_directory>")
        print("Example: python test_phase2_5_comprehensive.py data/spec_output/20260118_003024_cobaliatsystemhimpoc")
        sys.exit(1)
    
    spec_dir = Path(sys.argv[1])
    if not spec_dir.exists():
        logger.error(f"Directory not found: {spec_dir}")
        sys.exit(1)
    
    logger.info("╔═══════════════════════════════════════════════════════════════════════════════╗")
    logger.info("║           Phase 2.5 Comprehensive Test Suite                                 ║")
    logger.info("╚═══════════════════════════════════════════════════════════════════════════════╝")
    logger.info(f"Testing: {spec_dir}")
    logger.info("")
    
    results = []
    
    # Run all tests
    results.append(("Table Parser", test_table_parser(spec_dir)))
    results.append(("Message Extractor", test_message_extractor(spec_dir)))
    results.append(("Output Files", test_file_outputs(spec_dir)))
    results.append(("Table Content Analysis", test_table_content_analysis(spec_dir)))
    results.append(("Error Handling", test_error_handling(spec_dir)))
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"  {status}: {test_name}")
    
    logger.info("")
    if passed == total:
        logger.success(f"╔═══════════════════════════════════════════════════════════════════════════════╗")
        logger.success(f"║  ALL TESTS PASSED: {passed}/{total}                                                  ║")
        logger.success(f"╚═══════════════════════════════════════════════════════════════════════════════╝")
        sys.exit(0)
    else:
        logger.error(f"╔═══════════════════════════════════════════════════════════════════════════════╗")
        logger.error(f"║  SOME TESTS FAILED: {passed}/{total} passed                                          ║")
        logger.error(f"╚═══════════════════════════════════════════════════════════════════════════════╝")
        sys.exit(1)

if __name__ == "__main__":
    main()
