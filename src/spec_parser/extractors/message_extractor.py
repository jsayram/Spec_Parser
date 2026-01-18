"""
Extract POCT1-A message definitions from specifications.

DEPRECATED: This module is superseded by message_parser.py which provides
more complete extraction using DocumentNavigator patterns.

This module is kept for backward compatibility with existing tests.
For new code, use MessageParser from message_parser.py instead.
"""

from typing import List, Dict, Optional, Any
import re
from loguru import logger

from .base_extractor import BaseExtractor
from ..parsers.table_parser import ParsedTable


class MessageExtractor(BaseExtractor):
    """Extract message definitions from POCT1-A specifications"""
    
    # Pattern for standard POCT1-A messages (e.g., OBS^R01, QRY^Q01)
    STANDARD_MESSAGE_PATTERN = r'\b([A-Z]{3,})\^([A-Z]\d{2})\b'
    
    # Pattern for vendor-specific messages (e.g., ROCHE.LIAT.PVI.R01)
    VENDOR_MESSAGE_PATTERN = r'\b([A-Z][A-Za-z]+)\.([A-Z][A-Za-z]+)\.([A-Z]{2,})\.R\d{2}\b'
    
    # Pattern for message references in text
    MESSAGE_REF_PATTERN = r'\b(?:message|Message)\s+(?:type|structure|format)?\s*[:.]?\s*([A-Z]{3,}(?:\^[A-Z]\d{2}|\.[\w.]+))\b'
    
    def __init__(self):
        super().__init__()
        self.message_index: Dict[str, Dict] = {}  # For deduplication
    
    def entity_type(self) -> str:
        return "messages"
    
    def extract(self, tables: List[ParsedTable], 
                markdown_content: str, 
                json_data: dict) -> List[Dict[str, Any]]:
        """
        Extract message definitions from document.
        
        Strategy:
        1. Find segment tables (most reliable)
        2. Pattern match in markdown for message IDs
        3. Cross-reference and merge duplicates
        
        Args:
            tables: Parsed tables from document
            markdown_content: Full markdown text
            json_data: JSON sidecar data
        
        Returns:
            List of message definitions with segments
        """
        logger.info("Starting message extraction...")
        
        # Extract from segment tables (high confidence)
        self._extract_from_segment_tables(tables, json_data)
        
        # Extract from text patterns (medium confidence)
        self._extract_from_text_patterns(markdown_content, json_data)
        
        # Extract vendor-specific messages
        self._extract_vendor_messages(markdown_content, json_data)
        
        # Finalize
        self.extracted_entities = list(self.message_index.values())
        
        logger.success(f"Extracted {len(self.extracted_entities)} message definitions")
        return self.extracted_entities
    
    def _extract_from_segment_tables(self, tables: List[ParsedTable], json_data: dict):
        """Extract messages from tables that describe segments"""
        
        for table in tables:
            # Detect segment tables by column names
            if self._is_segment_table(table):
                message_def = self._parse_segment_table(table, json_data)
                
                if message_def:
                    msg_id = message_def["message_id"]
                    
                    if msg_id in self.message_index:
                        # Merge with existing definition
                        self._merge_message_definitions(self.message_index[msg_id], message_def)
                    else:
                        self.message_index[msg_id] = message_def
                    
                    logger.debug(f"Found message {msg_id} from segment table (page {table.page})")
    
    def _is_segment_table(self, table: ParsedTable) -> bool:
        """
        Detect if table describes message segments.
        
        Segment tables typically have columns like:
        - Segment | Description | Required | Repeating
        - Segment | Usage | Cardinality
        """
        # Check for "Segment" column (required)
        if not table.has_columns(["Segment"]):
            return False
        
        # Check for other typical columns
        has_description = table.has_columns(["Description", "Name", "Usage"])
        has_metadata = table.has_columns(["Required", "Repeating", "Cardinality", "Optional"])
        
        # Need at least one metadata column
        return has_description or has_metadata
    
    def _parse_segment_table(self, table: ParsedTable, json_data: dict) -> Optional[Dict]:
        """Parse segment table into message definition"""
        
        # Find message name in nearby text
        message_id = self._find_message_name_near_table(table, json_data)
        
        if not message_id:
            logger.debug(f"Could not find message name for table on page {table.page}")
            return None
        
        # Parse segments from table rows
        segments = []
        for row_dict in table.to_dict_list():
            segment_code = row_dict.get("Segment", "").strip()
            
            if not segment_code or len(segment_code) > 10:  # Basic validation
                continue
            
            segment = {
                "code": segment_code,
                "description": self._get_cell_value(row_dict, ["Description", "Name", "Usage"]),
                "required": self._parse_required(
                    self._get_cell_value(row_dict, ["Required", "Usage", "Cardinality"])
                ),
                "repeating": self._parse_repeating(
                    self._get_cell_value(row_dict, ["Repeating", "Cardinality"])
                )
            }
            
            segments.append(segment)
        
        if not segments:
            return None
        
        return {
            "message_id": message_id,
            "segments": segments,
            "direction": self._infer_direction(message_id),
            "vendor_specific": self._is_vendor_specific(message_id),
            "pages": [table.page],
            "citations": [table.citation],
            "extraction_method": "segment_table",
            "confidence": "high"
        }
    
    def _find_message_name_near_table(self, table: ParsedTable, json_data: dict) -> Optional[str]:
        """
        Find message name in text near the table.
        
        Strategy:
        1. Look in same page's text blocks before the table
        2. Check page title/headers
        3. Pattern match for message formats
        """
        page_data = self._get_page_data(json_data, table.page)
        if not page_data:
            return None
        
        # Get text blocks before this table
        text_before = []
        for block in page_data.get("blocks", []):
            if block.get("citation") == table.citation:
                break
            if block.get("type") == "text":
                text_before.append(block.get("content", ""))
        
        # Combine recent text (last 3 blocks)
        context = " ".join(text_before[-3:])
        
        # Try to find message patterns
        # Standard messages
        match = re.search(self.STANDARD_MESSAGE_PATTERN, context)
        if match:
            return match.group(0)
        
        # Vendor messages
        match = re.search(self.VENDOR_MESSAGE_PATTERN, context)
        if match:
            return match.group(0)
        
        # Message references
        match = re.search(self.MESSAGE_REF_PATTERN, context)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_from_text_patterns(self, markdown_content: str, json_data: dict):
        """Extract message IDs from text patterns"""
        
        # Find standard messages
        for match in re.finditer(self.STANDARD_MESSAGE_PATTERN, markdown_content):
            msg_id = match.group(0)
            
            if msg_id not in self.message_index:
                # Try to find which page it's on
                page = self._find_page_for_text(match.start(), json_data)
                
                self.message_index[msg_id] = {
                    "message_id": msg_id,
                    "direction": self._infer_direction(msg_id),
                    "vendor_specific": False,
                    "pages": [page] if page else [],
                    "extraction_method": "pattern_match",
                    "confidence": "medium"
                }
                
                logger.debug(f"Found message {msg_id} from text pattern")
    
    def _extract_vendor_messages(self, markdown_content: str, json_data: dict):
        """Extract vendor-specific message definitions"""
        
        for match in re.finditer(self.VENDOR_MESSAGE_PATTERN, markdown_content):
            msg_id = match.group(0)
            vendor = match.group(1)
            
            if msg_id not in self.message_index:
                page = self._find_page_for_text(match.start(), json_data)
                
                self.message_index[msg_id] = {
                    "message_id": msg_id,
                    "vendor": vendor,
                    "direction": self._infer_direction(msg_id),
                    "vendor_specific": True,
                    "pages": [page] if page else [],
                    "extraction_method": "pattern_match",
                    "confidence": "medium"
                }
                
                logger.debug(f"Found vendor message {msg_id}")
    
    def _merge_message_definitions(self, existing: Dict, new: Dict):
        """Merge two message definitions (prefer higher confidence)"""
        
        # Prefer segment_table over pattern_match
        if new.get("extraction_method") == "segment_table" and \
           existing.get("extraction_method") != "segment_table":
            # Replace with new (better quality)
            for key, value in new.items():
                existing[key] = value
        else:
            # Merge pages and citations
            if "pages" in new:
                existing.setdefault("pages", [])
                existing["pages"].extend(new["pages"])
                existing["pages"] = list(set(existing["pages"]))  # Deduplicate
            
            if "citations" in new:
                existing.setdefault("citations", [])
                existing["citations"].extend(new["citations"])
    
    def _get_cell_value(self, row_dict: Dict[str, str], possible_keys: List[str]) -> str:
        """Get value from row dict trying multiple possible column names"""
        for key in possible_keys:
            for actual_key in row_dict.keys():
                if key.lower() in actual_key.lower():
                    return row_dict[actual_key].strip()
        return ""
    
    def _parse_required(self, value: str) -> bool:
        """
        Parse Required/Usage field.
        
        Values: R (required), O (optional), C (conditional)
        """
        value_upper = value.upper().strip()
        return value_upper in ['R', 'REQUIRED', 'YES', 'MANDATORY']
    
    def _parse_repeating(self, value: str) -> bool:
        """
        Parse Repeating/Cardinality field.
        
        Values: Y/N, [1..1], [0..*], etc.
        """
        value_upper = value.upper().strip()
        
        # Direct yes/no
        if value_upper in ['Y', 'YES', 'REPEATING', 'MULTIPLE']:
            return True
        if value_upper in ['N', 'NO', 'SINGLE']:
            return False
        
        # Cardinality notation [min..max]
        if '..*' in value or '[1..*]' in value or '[0..*]' in value:
            return True
        
        return False
    
    def _infer_direction(self, message_id: str) -> str:
        """
        Infer message direction from ID.
        
        R## = device to host (results, reports)
        Q## = host to device (queries)
        """
        if '^R' in message_id or '.R' in message_id:
            return "device_to_host"
        elif '^Q' in message_id or '.Q' in message_id:
            return "host_to_device"
        else:
            return "bidirectional"
    
    def _is_vendor_specific(self, message_id: str) -> bool:
        """Check if message is vendor-specific"""
        return '.' in message_id and not message_id.startswith('.')
    
    def _get_page_data(self, json_data: dict, page_num: int) -> Optional[Dict]:
        """Get page data from JSON sidecar"""
        for page in json_data.get("pages", []):
            if page.get("page") == page_num:
                return page
        return None
    
    def _find_page_for_text(self, char_position: int, json_data: dict) -> Optional[int]:
        """
        Find which page contains text at given character position.
        
        This is approximate - markdown is concatenated, so we estimate.
        """
        # This is a simplified version - in reality, would need to track
        # character positions per page during markdown generation
        # For now, return None (page will be empty)
        return None
