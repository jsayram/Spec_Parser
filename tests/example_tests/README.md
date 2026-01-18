# Example Test Scripts

This directory contains example scripts demonstrating how to use the spec parser pipeline.

## Scripts

### Phase 2: PDF Extraction
- **`test_phase2.py`** - Extract text, tables, and images from PDFs with OCR
  ```bash
  python tests/example_tests/test_phase2.py <pdf_path> [--pages N]
  ```

### Phase 3: Search Indexing
- **`test_phase3.py`** - Build FAISS + BM25 search indices and run queries
  ```bash
  python tests/example_tests/test_phase3.py <spec_output_dir> [query]
  ```

### Phase 2.5: Entity Extraction
- **`test_phase2_5.py`** - Extract structured entities (messages, tables) from parsed specs
  ```bash
  python tests/example_tests/test_phase2_5.py <spec_output_dir>
  ```

- **`test_phase2_5_comprehensive.py`** - Comprehensive test suite for Phase 2.5
  ```bash
  python tests/example_tests/test_phase2_5_comprehensive.py <spec_output_dir>
  ```

### Debug Utilities
- **`debug_tables.py`** - Find and analyze segment tables in JSON sidecar
  ```bash
  python tests/example_tests/debug_tables.py <spec_output_dir>
  ```

- **`debug_uml_tables.py`** - Analyze UML-style class diagram tables
  ```bash
  python tests/example_tests/debug_uml_tables.py <spec_output_dir>
  ```

## Usage Pattern

```bash
# 1. Extract PDF (Phase 2)
python tests/example_tests/test_phase2.py data/specs/my_spec.pdf --pages 0

# 2. Build search indices (Phase 3)
python tests/example_tests/test_phase3.py data/spec_output/20260118_*/

# 3. Extract entities (Phase 2.5)
python tests/example_tests/test_phase2_5.py data/spec_output/20260118_*/

# 4. Run comprehensive validation
python tests/example_tests/test_phase2_5_comprehensive.py data/spec_output/20260118_*/
```

## Notes

- All scripts accept spec output directory as argument (no hardcoded paths)
- Scripts automatically find JSON/markdown files in subdirectories
- Use `--pages 0` to process all pages (default is 3 for testing)
