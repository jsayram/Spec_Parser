"""Debug script to analyze UML-style tables."""
import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python debug_uml_tables.py <spec_output_directory>")
    print("Example: python debug_uml_tables.py data/spec_output/20260118_003024_cobaliatsystemhimpoc")
    sys.exit(1)

spec_dir = Path(sys.argv[1])
if not spec_dir.exists():
    print(f"Error: Directory not found: {spec_dir}")
    sys.exit(1)

# Find JSON sidecar
json_files = list((spec_dir / "json").glob("*.json"))
if not json_files:
    print(f"Error: No JSON files found in {spec_dir / 'json'}")
    sys.exit(1)

json_path = json_files[0]
print(f"Loading: {json_path.name}")
print()

with open(json_path) as f:
    data = json.load(f)

# Look at page 116 tables (where we know message structures are)
for page in data['pages']:
    if page['page'] == 116:
        print(f'Page {page["page"]} - Total blocks: {len(page["blocks"])}')
        print()
        
        table_count = 0
        for block in page['blocks']:
            if block.get('type') == 'table':
                table_count += 1
                print(f'Table {table_count}:')
                print(f'  Citation: {block.get("citation")}')
                md_table = block.get('markdown_table', '')
                print(f'  Content:')
                print(md_table)
                print()
                print('-' * 80)
                print()
        
        print(f'Total tables on page: {table_count}')
        break
