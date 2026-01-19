"""
Field definition parser for POCT1-A specifications.

Extracts field definitions from markdown tables in device specifications,
including field names, types, optionality, descriptions, and examples.
"""

from typing import List, Dict, Optional, Tuple, Any
import re
from dataclasses import dataclass
from loguru import logger


@dataclass
class FieldDefinition:
    """Represents a single field definition extracted from spec."""
    
    field_name: str
    field_type: str  # Inferred type: string, datetime, int, float, bool
    optionality: Optional[str]  # R (required), O (optional), N (not used)
    description: str
    example: Optional[str]
    message_id: str  # Parent message (e.g., "HEL.R01")
    page: int
    citation_id: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "field_name": self.field_name,
            "field_type": self.field_type,
            "optionality": self.optionality,
            "description": self.description,
            "example": self.example,
            "message_id": self.message_id,
            "page": self.page,
            "citation_id": self.citation_id
        }


class FieldTableParser:
    """Parses field definition tables from POCT1-A specification markdown."""
    
    # Common POCT1-A field table headers
    FIELD_HEADERS = [
        r"field",
        r"field\s+name",
        r"name",
        r"segment"
    ]
    
    DESCRIPTION_HEADERS = [
        r"description",
        r"meaning",
        r"definition"
    ]
    
    EXAMPLE_HEADERS = [
        r"example",
        r"sample",
        r"value"
    ]
    
    OPTIONALITY_HEADERS = [
        r"r/o/n",
        r"use",
        r"usage",
        r"req"
    ]
    
    def __init__(self):
        """Initialize field table parser."""
        self.message_pattern = re.compile(r'([A-Z]{3,4}\.[A-Z]\d+)')
        
    def parse_page(self, page_data: Dict[str, Any]) -> List[FieldDefinition]:
        """
        Parse field definitions from a single page.
        
        Args:
            page_data: Page bundle dict with markdown, blocks, citations
            
        Returns:
            List of field definitions found on this page
        """
        fields = []
        page_num = page_data.get("page", 0)
        markdown = page_data.get("markdown", "")
        blocks = page_data.get("blocks", [])
        citations = page_data.get("citations", {})
        
        # Find message IDs in markdown
        message_ids = self._extract_message_ids(markdown)
        
        if not message_ids:
            return fields
        
        # Parse tables from blocks
        for block in blocks:
            if block.get("type") != "table":
                continue
                
            markdown_table = block.get("markdown_table", "")
            citation_id = block.get("citation")
            
            # Try to parse as field definition table
            parsed_fields = self._parse_table(
                markdown_table,
                page_num,
                citation_id,
                message_ids
            )
            fields.extend(parsed_fields)
        
        logger.debug(f"Page {page_num}: Extracted {len(fields)} fields")
        return fields
    
    def _extract_message_ids(self, markdown: str) -> List[str]:
        """Extract message IDs from markdown text."""
        matches = self.message_pattern.findall(markdown)
        return list(set(matches))  # Unique message IDs
    
    def _parse_table(
        self,
        markdown_table: str,
        page: int,
        citation_id: Optional[str],
        message_ids: List[str]
    ) -> List[FieldDefinition]:
        """
        Parse a markdown table for field definitions.
        
        Args:
            markdown_table: Markdown table string
            page: Page number
            citation_id: Citation ID for this table
            message_ids: Possible parent message IDs from page
            
        Returns:
            List of parsed field definitions
        """
        fields = []
        
        # Split table into rows
        lines = [l.strip() for l in markdown_table.strip().split('\n') if l.strip()]
        
        if len(lines) < 3:  # Need header, separator, and at least one data row
            return fields
        
        # Parse header row
        header_row = lines[0]
        headers = [h.strip() for h in header_row.split('|') if h.strip()]
        
        # Find column indices
        field_col = self._find_column(headers, self.FIELD_HEADERS)
        desc_col = self._find_column(headers, self.DESCRIPTION_HEADERS)
        example_col = self._find_column(headers, self.EXAMPLE_HEADERS)
        opt_col = self._find_column(headers, self.OPTIONALITY_HEADERS)
        
        if field_col is None:
            return fields  # Not a field table
        
        # Determine parent message (use first message ID found on page)
        parent_message = message_ids[0] if message_ids else "UNKNOWN"
        
        # Parse data rows (skip header and separator)
        for row_line in lines[2:]:
            cells = [c.strip() for c in row_line.split('|') if c.strip()]
            
            # Skip empty rows
            if not cells:
                continue
            
            # Check if we have enough columns
            valid_cols = [c for c in [field_col, desc_col, example_col, opt_col] if c is not None]
            if valid_cols and len(cells) <= max(valid_cols):
                continue
            
            field_name = cells[field_col] if field_col < len(cells) else ""
            description = cells[desc_col] if desc_col is not None and desc_col < len(cells) else ""
            example = cells[example_col] if example_col is not None and example_col < len(cells) else None
            optionality = cells[opt_col] if opt_col is not None and opt_col < len(cells) else None
            
            # Skip empty or invalid rows
            if not field_name or field_name.lower() in ['field', 'name', '']:
                continue
            
            # Infer field type
            field_type = self._infer_type(field_name, description, example)
            
            field_def = FieldDefinition(
                field_name=field_name,
                field_type=field_type,
                optionality=optionality,
                description=description,
                example=example,
                message_id=parent_message,
                page=page,
                citation_id=citation_id
            )
            fields.append(field_def)
        
        return fields
    
    def _find_column(self, headers: List[str], patterns: List[str]) -> Optional[int]:
        """Find column index matching any of the given patterns."""
        for i, header in enumerate(headers):
            header_lower = header.lower()
            for pattern in patterns:
                if re.search(pattern, header_lower):
                    return i
        return None
    
    def _infer_type(
        self,
        field_name: str,
        description: str,
        example: Optional[str]
    ) -> str:
        """
        Infer field type from name, description, and example.
        
        Args:
            field_name: Field name (e.g., "HDR.control_id")
            description: Field description
            example: Example value
            
        Returns:
            Inferred type: string, datetime, int, float, bool
        """
        field_lower = field_name.lower()
        desc_lower = description.lower() if description else ""
        
        # Check for datetime patterns
        if any(x in field_lower for x in ['date', 'time', 'dttm', 'timestamp']):
            return "datetime"
        
        if example:
            # Check example format
            # DateTime: YYYYMMDDHHMMSS or ISO format
            if re.match(r'\d{14}', example.replace('-', '').replace(':', '').replace('T', '')):
                return "datetime"
            
            # ISO datetime
            if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', example):
                return "datetime"
            
            # Integer
            if re.match(r'^-?\d+$', example.strip('"')):
                return "int"
            
            # Float
            if re.match(r'^-?\d+\.\d+$', example.strip('"')):
                return "float"
            
            # Boolean
            if example.strip('"').lower() in ['true', 'false', 'yes', 'no', '0', '1']:
                return "bool"
        
        # Check description for type hints
        if any(x in desc_lower for x in ['number', 'integer', 'count', 'quantity', 'qty']):
            return "int"
        
        if any(x in desc_lower for x in ['float', 'decimal', 'percent']):
            return "float"
        
        if any(x in desc_lower for x in ['flag', 'boolean', 'true/false']):
            return "bool"
        
        # Default to string
        return "string"


def parse_fields_from_document(document: Dict[str, Any]) -> List[FieldDefinition]:
    """
    Parse all field definitions from a complete document.
    
    Args:
        document: Document JSON with pages array
        
    Returns:
        List of all field definitions found
    """
    parser = FieldTableParser()
    all_fields = []
    
    pages = document.get("pages", [])
    for page_data in pages:
        fields = parser.parse_page(page_data)
        all_fields.extend(fields)
    
    logger.info(f"Extracted {len(all_fields)} field definitions from document")
    return all_fields
