#!/usr/bin/env python
"""Medical compliance check for current extraction."""

import json
from pathlib import Path

# Load current extraction
json_path = Path('data/spec_output/20260118_013647_cobaliatsystemhimpoc/json/coba-liat-system-him-poct1-a_sw-ver.-3.3.1_ver.-6.0.json')
with open(json_path) as f:
    data = json.load(f)

print('=== CURRENT MEDICAL COMPLIANCE CHECK ===\n')

# Check 1: Source PDF hash?
print('1. Source PDF Verification:')
print(f'   Has PDF hash/checksum: {"pdf_hash" in data}')
print(f'   Has PDF path: {"source_path" in data}')
print('   Can verify unchanged: NO ❌')

# Check 2: Extraction validation
print('\n2. Extraction Validation:')
print('   Confidence scores stored: Partial (OCR only)')
print('   Text verification: NO ❌')
print('   Character-level accuracy: NOT MEASURED ❌')

# Check 3: OCR confidence
print('\n3. OCR Confidence Filtering:')
ocr_count = sum(len(p.get('ocr', [])) for p in data['pages'])
print(f'   OCR results: {ocr_count}')

# Check 4: Error handling
print('\n4. Error Handling:')
print('   Extraction errors logged: BASIC')
print('   Failed pages tracked: NO ❌')
print('   Retry mechanism: NO ❌')

# Check 5: Audit trail
print('\n5. Audit Trail:')
print(f'   Extraction timestamp: {"extracted_at" in data}')
print('   User/system info: NO ❌')
print('   Processing version: NO ❌')

# Check 6: Data integrity
print('\n6. Data Integrity:')
print(f'   JSON schema validation: NO ❌')
print(f'   Required fields enforced: PARTIAL (Pydantic)')

print('\n' + '='*50)
print('OVERALL: NOT READY FOR MEDICAL USE')
print('='*50)
