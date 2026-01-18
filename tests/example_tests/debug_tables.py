"""Debug script to find segment tables in JSON sidecar."""
import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python debug_tables.py <spec_output_directory>")
    print("Example: python debug_tables.py data/spec_output/20260118_003024_cobaliatsystemhimpoc")
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

# Look for tables with segment-related keywords
segment_keywords = ['segment', 'msh', 'pid', 'obr', 'obx', 'message structure', 'field']

print('Looking for segment-related tables...')
print()

found_count = 0
for page in data['pages']:
    for block in page['blocks']:
        if block.get('type') == 'table':
            md_table = block.get('markdown_table', '')
            lower_table = md_table.lower()
            
            # Check if any keywords present
            if any(kw in lower_table for kw in segment_keywords):
                found_count += 1
                print(f'Page {page["page"]}, Citation: {block.get("citation")}')
                print(f'Table content (first 300 chars):')
                print(md_table[:300])
                print()
                print('-' * 80)
                print()
                
                if found_count >= 5:  # Limit to first 5 matches
                    break
    if found_count >= 5:
        break

print(f'\nTotal segment-related tables found: {found_count}')
