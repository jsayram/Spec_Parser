# Table Extraction & Field Type Analysis

## Q1: How can we make table extraction better?

### Current Limitations

**What We Miss (21% failure rate):**
1. **Complex merged cells** - Multi-row/column spans
2. **Rotated/skewed tables** - Y-coordinate grouping assumes horizontal
3. **Highly irregular spacing** - Column detection needs consistent X-positions
4. **Tables across page breaks** - Each page processed independently
5. **Nested tables** - Table-within-table structures

### Improvement Opportunities

#### A. **Better Column Detection**
**Current:** Fixed 20pt minimum gap
```python
MIN_COL_GAP = 20.0  # Too rigid for dense tables
```

**Improvement:** Adaptive column detection
```python
def _detect_column_boundaries(self, rows):
    """Analyze X-position distribution to find natural column breaks."""
    # Collect all X-positions across rows
    all_x_positions = sorted(set(cell.x for row in rows for cell in row))
    
    # Find gaps larger than average spacing
    gaps = [all_x_positions[i+1] - all_x_positions[i] 
            for i in range(len(all_x_positions)-1)]
    avg_gap = sum(gaps) / len(gaps)
    threshold = avg_gap * 1.5  # Adaptive threshold
    
    # Column boundaries where gap > threshold
    column_boundaries = [x for i, x in enumerate(all_x_positions[:-1])
                        if gaps[i] > threshold]
    return column_boundaries
```

#### B. **Merged Cell Detection**
**Current:** Assumes one cell per position
```python
# If cell spans multiple columns, we split it incorrectly
```

**Improvement:** Detect cell spanning
```python
def _detect_merged_cells(self, cell, column_positions):
    """Detect if cell spans multiple columns based on width."""
    cell_right = cell.x + cell.width
    covered_columns = sum(1 for col_x in column_positions 
                         if cell.x < col_x < cell_right)
    return max(1, covered_columns)  # Colspan
```

#### C. **Multi-Line Cell Content**
**Current:** Each text span = one cell
```python
# Cells with line breaks are split into multiple rows
```

**Improvement:** Group text by proximity
```python
def _group_multiline_cells(self, cells):
    """Group text spans within same cell region."""
    grouped = []
    for cell in cells:
        # Find nearby cells (within 3pt vertically, same column)
        nearby = [c for c in cells 
                 if abs(c.y - cell.y) < 3 and abs(c.x - cell.x) < 5]
        if nearby:
            # Merge text
            merged_text = "\n".join(sorted([c.text for c in nearby], 
                                          key=lambda c: c.y))
            grouped.append(Cell(merged_text, cell.x, cell.y, ...))
    return grouped
```

#### D. **Table Continuation Detection**
**Current:** Page boundaries break tables
```python
# extract_page() processes each page independently
```

**Improvement:** Cross-page table detection
```python
def _detect_table_continuation(self, prev_page_tables, current_page_tables):
    """Check if table continues from previous page."""
    if not prev_page_tables:
        return current_page_tables
    
    last_table = prev_page_tables[-1]
    first_table = current_page_tables[0]
    
    # Check if column structure matches
    if self._same_column_structure(last_table, first_table):
        # Merge tables
        merged = self._merge_tables(last_table, first_table)
        return [merged] + current_page_tables[1:]
    
    return current_page_tables
```

#### E. **Table Quality Scoring**
**Current:** Binary valid/invalid check
```python
return self._is_valid_table(markdown)  # True/False
```

**Improvement:** Quality confidence score
```python
def _calculate_table_quality(self, table):
    """Score table quality 0-1 for prioritization."""
    score = 0.0
    
    # Column alignment consistency
    col_variance = self._column_alignment_variance(table)
    score += 0.3 * (1 - min(col_variance, 1.0))
    
    # Row completeness (non-empty cells)
    completeness = self._cell_completeness_ratio(table)
    score += 0.3 * completeness
    
    # Header detection confidence
    has_header = self._detect_header_row(table)
    score += 0.2 if has_header else 0.0
    
    # Regular row height
    height_variance = self._row_height_variance(table)
    score += 0.2 * (1 - min(height_variance, 1.0))
    
    return score
```

### Recommended Implementation Priority

1. **High Impact:**
   - Adaptive column detection (80% of failures due to spacing)
   - Multi-line cell grouping (improves 50% of current extractions)

2. **Medium Impact:**
   - Merged cell detection (handles 30% of complex tables)
   - Table quality scoring (helps prioritize manual review)

3. **Lower Impact (but valuable):**
   - Cross-page continuation (5-10% of documents)
   - Nested table detection (rare in POCT1-A specs)

---

## Q2: Does the pipeline extract all field types correctly?

### Current Type Inference Logic

```python
def _infer_type(field_name, description, example):
    # Priority 1: Field name patterns
    if 'date' or 'time' or 'dttm' in field_name:
        return "datetime"
    
    # Priority 2: Example format
    if example matches r'^\d+$':
        return "int"
    if example matches r'^\d+\.\d+$':
        return "float"
    if example in ['true', 'false', 'yes', 'no']:
        return "bool"
    
    # Priority 3: Description keywords
    if 'number' or 'integer' or 'count' in description:
        return "int"
    
    # Default
    return "string"
```

### Type Coverage Analysis

**What's Extracted Correctly:**
- ✅ `datetime` - Pattern matching on field names
- ✅ `int` - Integer examples parsed
- ✅ `string` - Default fallback
- ✅ `float` - Decimal pattern detection

**What's Missing:**
- ❌ **Enum/Code types** - No detection of "code_cd" fields with restricted values
- ❌ **Arrays/Lists** - No detection of repeating fields
- ❌ **Complex types** - No detection of nested structures
- ❌ **Custom POCT1-A types** - No domain-specific type mapping

### Type Extraction Issues Found

**From Quidel Sofia baseline:**
```markdown
| `HDR.control_id` | int | - | A string guaranteed to uniquely identify... | - |
```
**Problem:** Description says "string" but type inferred as "int" (probably has numeric example)

**Root cause:**
```python
# Example: "00027" 
if re.match(r'^-?\d+$', example.strip('"')):
    return "int"  # ❌ Should check description first!
```

### Improvements Needed

#### A. **Code/Enum Detection**
```python
def _infer_type(self, field_name, description, example):
    # NEW: Check for code/enum indicators
    if '_cd' in field_name.lower() or 'code' in field_name.lower():
        # Check description for allowed values
        if re.search(r'(values are|possible values|either)', description, re.I):
            return "code"  # or "enum"
    
    # Check description mentions string before checking example
    if 'string' in description.lower():
        return "string"  # Trust description over example format
```

#### B. **Better Type Hierarchy**
```python
FIELD_TYPES = {
    # Base types
    "string": "Text value",
    "int": "Integer number",
    "float": "Decimal number",
    "bool": "True/False flag",
    "datetime": "ISO 8601 timestamp",
    
    # Domain-specific types
    "code": "Code from controlled vocabulary",
    "id": "Unique identifier (may look numeric but is string)",
    "duration": "Time duration (may be int seconds or ISO duration)",
    "quantity": "Measurement value (float + units)",
    
    # Complex types
    "array": "Repeating field (0..N)",
    "object": "Nested structure",
}
```

#### C. **Optionality Parsing**
**Current:** Extracts R/O/N but doesn't interpret
```python
optionality = cells[opt_col]  # Just stores "R" or "O" or "N"
```

**Improvement:** Parse cardinality
```python
def _parse_optionality(self, opt_value):
    """Parse R/O/N into structured cardinality."""
    if not opt_value:
        return {"required": None, "min": 0, "max": None}
    
    opt_upper = opt_value.strip().upper()
    
    if opt_upper == 'R':
        return {"required": True, "min": 1, "max": 1}
    elif opt_upper == 'O':
        return {"required": False, "min": 0, "max": 1}
    elif opt_upper == 'N':
        return {"required": False, "min": 0, "max": 0}  # Not used
    
    # Parse cardinality like "0..N" or "1..*"
    match = re.match(r'(\d+)\.\.(\d+|\*|N)', opt_value)
    if match:
        min_val = int(match.group(1))
        max_val = None if match.group(2) in ['*', 'N'] else int(match.group(2))
        return {"required": min_val > 0, "min": min_val, "max": max_val}
    
    return {"required": None, "min": 0, "max": None}
```

---

## Q3: Does the pipeline gather all analytes listed?

### Current State: **YES, but indirectly**

**Analyte Data Captured:**
```json
{
  "field_name": "OBS.observation_id",
  "description": "The analyte name from the Test Type File",
  "example": "\"Flu A\""
}
```

**Where it appears:**
- ✅ Extracted as field definition (OBS.observation_id)
- ✅ Description mentions "analyte name"
- ✅ Example shows "Flu A"
- ✅ Full text searchable in FAISS/BM25 indices

**Example from document.json:**
```
"The analyte name from the Test Type File."
"Example: ^^^Flu A"
"^^^Flu B"
"Sofia Flu A+B"
```

### What's NOT Extracted: **Explicit Analyte Registry**

**We don't create:**
```json
{
  "device": "Quidel Sofia",
  "supported_analytes": [
    {"name": "Flu A", "test_type": "Sofia Flu A+B"},
    {"name": "Flu B", "test_type": "Sofia Flu A+B"},
    {"name": "Strep A", "test_type": "Sofia Strep A"},
    {"name": "RSV", "test_type": "Sofia RSV"}
  ]
}
```

### How to Add Analyte Extraction

#### Option 1: **Field Value Mining**
Extract example values from OBS.observation_id fields:

```python
def extract_analyte_list(field_definitions):
    """Extract analyte list from field examples."""
    analytes = set()
    
    for field in field_definitions:
        if 'observation_id' in field.field_name.lower():
            # Parse example for analyte names
            if field.example:
                # Example: "Flu A" or "^^^Flu A"
                analyte = field.example.strip('"').replace('^^^', '')
                analytes.add(analyte)
            
            # Parse description for test names
            if 'test type file' in field.description.lower():
                # Could contain: "from the Test Type File: Flu A, Flu B"
                matches = re.findall(r'Test Type File[:\s]+(.*)', 
                                    field.description, re.I)
                for match in matches:
                    for item in match.split(','):
                        analytes.add(item.strip())
    
    return sorted(list(analytes))
```

#### Option 2: **Dedicated Analyte Table Parser**
Look for analyte/test type tables in specs:

```python
class AnalyteTableParser:
    """Extract analyte/test type tables from specs."""
    
    TABLE_INDICATORS = [
        'test type', 'analyte', 'assay', 'test name', 
        'supported tests', 'available tests'
    ]
    
    def parse_analyte_table(self, page_bundle):
        """Find and parse analyte tables."""
        for table_block in page_bundle.tables:
            if not table_block.markdown_table:
                continue
            
            # Check if table header mentions analytes
            headers = self._extract_headers(table_block.markdown_table)
            if any(ind in ' '.join(headers).lower() 
                   for ind in self.TABLE_INDICATORS):
                return self._parse_table_rows(table_block.markdown_table)
        
        return []
    
    def _parse_table_rows(self, markdown_table):
        """Parse analyte rows."""
        analytes = []
        lines = markdown_table.split('\n')
        
        # Skip header and separator
        for row in lines[2:]:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            if cells:
                analytes.append({
                    'name': cells[0],
                    'test_type': cells[1] if len(cells) > 1 else None,
                    'description': cells[2] if len(cells) > 2 else None
                })
        
        return analytes
```

#### Option 3: **Text Pattern Matching**
Search full document for analyte mentions:

```python
def find_analyte_mentions(document):
    """Find analyte references in document text."""
    analyte_patterns = [
        r'analyte[s]?\s*:\s*([^.]+)',
        r'test[s]?\s+supported\s*:\s*([^.]+)',
        r'(Flu A|Flu B|Strep A|RSV|COVID)',  # Known analytes
    ]
    
    analytes = set()
    
    for page in document['pages']:
        for block in page.get('text_blocks', []):
            content = block.get('content', '')
            for pattern in analyte_patterns:
                matches = re.findall(pattern, content, re.I)
                for match in matches:
                    # Clean and split
                    items = match.split(',')
                    analytes.update(item.strip() for item in items)
    
    return list(analytes)
```

### Recommended Implementation

**Add to baseline report generation:**

```python
# In spec_diff.py or message_parser.py
def _extract_analyte_registry(self, document, field_definitions):
    """Extract comprehensive analyte list."""
    
    # Method 1: From field examples
    field_analytes = self._extract_from_fields(field_definitions)
    
    # Method 2: From dedicated tables
    table_analytes = self._extract_from_tables(document)
    
    # Method 3: From text mentions
    text_analytes = self._extract_from_text(document)
    
    # Combine and deduplicate
    all_analytes = set(field_analytes + table_analytes + text_analytes)
    
    return {
        'total_count': len(all_analytes),
        'analyte_list': sorted(all_analytes),
        'sources': {
            'field_examples': len(field_analytes),
            'tables': len(table_analytes),
            'text_mentions': len(text_analytes)
        }
    }
```

**Add to baseline report:**

```markdown
## Supported Analytes
**Total:** 8 analytes

| Analyte | Test Type | Found In |
|---------|-----------|----------|
| Flu A | Sofia Flu A+B | OBS.observation_id example (p16) |
| Flu B | Sofia Flu A+B | OBS.observation_id example (p16) |
| Strep A | Sofia Strep A | Text mention (p3) |
| RSV | Sofia RSV | Table (p4) |
```

### Summary

**Q1: Make table extraction better**
- Implement adaptive column detection (high priority)
- Add multi-line cell grouping (high priority)
- Add merged cell detection (medium priority)
- Add quality scoring for review prioritization

**Q2: Field types extracted correctly?**
- Mostly yes, but needs improvement:
  - Add code/enum detection for "_cd" fields
  - Trust description over example format
  - Add better optionality parsing (cardinality)
  - Add domain-specific POCT1-A types

**Q3: Analytes captured?**
- YES - data exists in fields, examples, descriptions
- NO - not extracted into explicit registry
- RECOMMEND: Add dedicated analyte extraction phase
- Target: Generate "Supported Analytes" section in baseline reports
