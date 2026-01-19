"""
Analyte extractor for POCT1-A specifications.

Extracts supported analytes/test types from device specifications.
"""

from typing import List, Dict, Set, Any, Optional
import re
from loguru import logger
from dataclasses import dataclass


@dataclass
class AnalyteInfo:
    """Information about a supported analyte."""
    name: str
    test_type: Optional[str] = None
    page: Optional[int] = None
    source: str = "unknown"  # field_example, table, text_mention
    
    def __hash__(self):
        """Hash by name for deduplication."""
        return hash(self.name.lower())
    
    def __eq__(self, other):
        """Equal if same name (case-insensitive)."""
        if not isinstance(other, AnalyteInfo):
            return False
        return self.name.lower() == other.name.lower()


class AnalyteExtractor:
    """Extract analyte/test type information from device specifications."""
    
    # Known analyte patterns (case-insensitive)
    KNOWN_ANALYTES = [
        'Flu A', 'Flu B', 'Influenza A', 'Influenza B',
        'Strep A', 'Streptococcus A', 'Group A Strep',
        'RSV', 'Respiratory Syncytial Virus',
        'COVID', 'COVID-19', 'SARS-CoV-2', 'Coronavirus',
        'hCG', 'Troponin', 'D-Dimer', 'CRP', 'Procalcitonin',
        'Malaria', 'Dengue', 'HIV', 'HBsAg', 'HCV',
    ]
    
    # Table header patterns indicating analyte tables
    ANALYTE_TABLE_HEADERS = [
        'test type', 'analyte', 'assay', 'test name',
        'supported test', 'available test', 'result',
        'observation', 'measurement'
    ]
    
    def extract_from_document(self, document: Dict[str, Any]) -> List[AnalyteInfo]:
        """
        Extract all analytes from document using multiple methods.
        
        Args:
            document: Document JSON with pages array
            
        Returns:
            Deduplicated list of analyte information
        """
        analytes_set: Set[AnalyteInfo] = set()
        
        # Method 1: Extract from text mentions
        text_analytes = self._extract_from_text(document)
        analytes_set.update(text_analytes)
        logger.debug(f"Found {len(text_analytes)} analytes from text mentions")
        
        # Method 2: Extract from tables
        table_analytes = self._extract_from_tables(document)
        analytes_set.update(table_analytes)
        logger.debug(f"Found {len(table_analytes)} analytes from tables")
        
        # Convert to list and sort
        analytes_list = sorted(list(analytes_set), key=lambda a: a.name.lower())
        
        logger.info(f"Extracted {len(analytes_list)} unique analytes from document")
        return analytes_list
    
    def extract_from_fields(self, field_definitions: List) -> List[AnalyteInfo]:
        """
        Extract analytes from field definitions (examples).
        
        Args:
            field_definitions: List of FieldDefinition objects
            
        Returns:
            List of analytes found in field examples
        """
        analytes = []
        
        for field in field_definitions:
            field_name_lower = field.field_name.lower()
            
            # Look for observation_id or analyte fields
            if 'observation_id' in field_name_lower or 'analyte' in field_name_lower:
                # Extract from example
                if field.example:
                    analyte_name = self._clean_analyte_name(field.example)
                    if analyte_name:
                        analytes.append(AnalyteInfo(
                            name=analyte_name,
                            page=field.page,
                            source='field_example'
                        ))
                
                # Extract from description
                if field.description:
                    desc_analytes = self._extract_analytes_from_text(
                        field.description, 
                        field.page
                    )
                    analytes.extend(desc_analytes)
        
        logger.debug(f"Found {len(analytes)} analytes from field definitions")
        return analytes
    
    def _extract_from_text(self, document: Dict[str, Any]) -> List[AnalyteInfo]:
        """Extract analytes from document text content."""
        analytes = []
        
        pages = document.get("pages", [])
        for page_bundle in pages:
            page_num = page_bundle.get("page", 0)
            
            # Check text blocks
            for block in page_bundle.get("text_blocks", []):
                content = block.get("content", "")
                if content:
                    block_analytes = self._extract_analytes_from_text(content, page_num)
                    analytes.extend(block_analytes)
            
            # Check markdown content
            markdown = page_bundle.get("markdown", "")
            if markdown:
                markdown_analytes = self._extract_analytes_from_text(markdown, page_num)
                analytes.extend(markdown_analytes)
        
        return analytes
    
    def _extract_from_tables(self, document: Dict[str, Any]) -> List[AnalyteInfo]:
        """Extract analytes from table structures."""
        analytes = []
        
        pages = document.get("pages", [])
        for page_bundle in pages:
            page_num = page_bundle.get("page", 0)
            
            for table_block in page_bundle.get("table_blocks", []):
                markdown_table = table_block.get("markdown_table")
                if not markdown_table:
                    continue
                
                # Check if this is an analyte-related table
                if self._is_analyte_table(markdown_table):
                    table_analytes = self._parse_analyte_table(markdown_table, page_num)
                    analytes.extend(table_analytes)
        
        return analytes
    
    def _extract_analytes_from_text(self, text: str, page: int) -> List[AnalyteInfo]:
        """Extract analytes from text using patterns."""
        analytes = []
        
        # Pattern 1: "analyte name" or "test type" lists
        patterns = [
            r'analyte[s]?\s*[:\-]\s*([^.\n]+)',
            r'test\s+type[s]?\s*[:\-]\s*([^.\n]+)',
            r'assay[s]?\s*[:\-]\s*([^.\n]+)',
            r'observation[_\s]id[:\-]\s*([^.\n]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(1).strip()
                # Split on commas and extract each
                for item in value.split(','):
                    analyte_name = self._clean_analyte_name(item)
                    if analyte_name:
                        analytes.append(AnalyteInfo(
                            name=analyte_name,
                            page=page,
                            source='text_mention'
                        ))
        
        # Pattern 2: Known analyte names in text
        for known in self.KNOWN_ANALYTES:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(known) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                analytes.append(AnalyteInfo(
                    name=known,
                    page=page,
                    source='text_mention'
                ))
        
        return analytes
    
    def _is_analyte_table(self, markdown_table: str) -> bool:
        """Check if table contains analyte information."""
        # Get headers (first row)
        lines = [l.strip() for l in markdown_table.split('\n') if l.strip()]
        if len(lines) < 2:
            return False
        
        header_row = lines[0].lower()
        
        # Check if any analyte-related headers present
        return any(pattern in header_row for pattern in self.ANALYTE_TABLE_HEADERS)
    
    def _parse_analyte_table(self, markdown_table: str, page: int) -> List[AnalyteInfo]:
        """Parse analyte information from table."""
        analytes = []
        
        lines = [l.strip() for l in markdown_table.split('\n') if l.strip()]
        if len(lines) < 3:  # Need header + separator + at least 1 data row
            return analytes
        
        # Parse header to find relevant columns
        header_cells = [c.strip() for c in lines[0].split('|') if c.strip()]
        
        # Find analyte/test type columns
        analyte_col = None
        test_type_col = None
        
        for i, header in enumerate(header_cells):
            header_lower = header.lower()
            if any(x in header_lower for x in ['analyte', 'observation', 'result', 'test name']):
                analyte_col = i
            elif 'test type' in header_lower or 'assay' in header_lower:
                test_type_col = i
        
        if analyte_col is None:
            return analytes
        
        # Parse data rows (skip header and separator)
        for row_line in lines[2:]:
            cells = [c.strip() for c in row_line.split('|') if c.strip()]
            
            if len(cells) <= analyte_col:
                continue
            
            analyte_name = self._clean_analyte_name(cells[analyte_col])
            if not analyte_name:
                continue
            
            test_type = None
            if test_type_col is not None and len(cells) > test_type_col:
                test_type = cells[test_type_col].strip()
                if not test_type or test_type == '-':
                    test_type = None
            
            analytes.append(AnalyteInfo(
                name=analyte_name,
                test_type=test_type,
                page=page,
                source='table'
            ))
        
        return analytes
    
    def _clean_analyte_name(self, raw_name: str) -> Optional[str]:
        """Clean and validate analyte name."""
        if not raw_name:
            return None
        
        # Remove quotes, carets, and extra whitespace
        cleaned = raw_name.strip('"\'').strip()
        cleaned = cleaned.replace('^^^', '').strip()
        
        # Remove common prefixes/suffixes
        cleaned = re.sub(r'^(test|assay|analyte)[:\s]*', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        
        # Filter out invalid/empty values
        if not cleaned or len(cleaned) < 2:
            return None
        
        # Filter out common non-analyte words
        invalid_words = ['example', 'n/a', 'none', 'empty', '-', 'col', 'field']
        if cleaned.lower() in invalid_words:
            return None
        
        return cleaned
