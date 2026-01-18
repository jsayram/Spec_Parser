"""
Message type parser for POCT1 specifications.

Extracts and categorizes message types and field specifications from spec documents
using dual detection: table column matching + POCT1 pattern recognition.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..rlm.document_navigator import DocumentNavigator
from ..parsers.json_sidecar import JSONSidecarWriter
from ..schemas.citation import Citation


# TODO HL7 EXTENSION: Add protocol parameter to __init__
# Load standards dynamically based on protocol type (POCT1, HL7v2, etc.)


@dataclass
class FieldSpec:
    """Field specification extracted from table."""
    field_id: str  # e.g., "MSH-9", "OBX-3"
    name: Optional[str] = None
    data_type: Optional[str] = None
    optionality: Optional[str] = None  # R, O, C
    cardinality: Optional[str] = None  # e.g., [1..1], [0..N]
    length: Optional[str] = None
    description: Optional[str] = None
    citation: Optional[Citation] = None


@dataclass
class MessageType:
    """Message type with directionality and category."""
    message_id: str  # e.g., "OBS.R01"
    direction: str  # "→Host", "←Device", "↔Both"
    category: str  # observation, config, qc, vendor_specific, unrecognized
    citations: List[Citation] = field(default_factory=list)


@dataclass
class MessageInventory:
    """Complete inventory of messages and fields from a spec."""
    recognized_messages: List[MessageType] = field(default_factory=list)
    unrecognized_messages: List[MessageType] = field(default_factory=list)
    field_specs: List[FieldSpec] = field(default_factory=list)
    categories: Dict[str, List[str]] = field(default_factory=dict)


class MessageParser:
    """Parse message types and field specifications from POCT1 specs."""
    
    # POCT1 patterns (ordered from most specific to most general)
    MESSAGE_TYPE_PATTERN = re.compile(r'\b([A-Z]{3})\.[A-Z]\d{2}\b')  # OBS.R01
    MESSAGE_TYPE_ALT = re.compile(r'\b([A-Z]{3})\^([A-Z]{3}_[A-Z]\d{2})\b')  # OBS^OBS_R01
    MESSAGE_TYPE_CATCHALL = re.compile(r'\b([A-Z]{3,})[.^_]([A-Z]+\d+)\b')  # Catch variations
    
    FIELD_PATTERN = re.compile(r'\b([A-Z]{3})-(\d+)\b')  # MSH-9, OBX-3
    FIELD_PATTERN_ALT = re.compile(r'\b([A-Z]{3})\.(\d+)\b')  # MSH.9 (dot separator)
    FIELD_PATTERN_CATCHALL = re.compile(r'\b([A-Z]{2,})[-._](\d+)\b')  # Catch variations
    
    VENDOR_PATTERN = re.compile(r'\bZ[A-Z]{2}')  # Z** vendor extensions
    VENDOR_PATTERN_EXTENDED = re.compile(r'\bZ[A-Z0-9]{2,}')  # Z** with numbers
    VENDOR_MULTI_SEGMENT = re.compile(r'\b[A-Z][a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)+\b')  # Mes.mess2.mes3...
    
    # Table column patterns for field tables
    FIELD_TABLE_COLUMNS = [
        ["field", "seq", "type", "opt", "card"],
        ["field", "name", "type", "optionality"],
        ["segment", "field", "description", "type"],
        ["field id", "field name", "data type"],
    ]
    
    def __init__(self, standards_path: Optional[Path] = None):
        """
        Initialize message parser with POCT1 standards.
        
        Args:
            standards_path: Path to poct1_standards.json (or hl7_standards.json)
        """
        if standards_path is None:
            # Default to POCT1 standards
            standards_path = Path(__file__).parent / "poct1_standards.json"
        
        self.standards = self._load_standards(standards_path)
        self.custom_messages_path = Path("data/custom_messages.json")
        self.custom_messages = self._load_custom_messages()
    
    def _load_standards(self, path: Path) -> Dict:
        """Load message type standards from JSON."""
        if not path.exists():
            raise FileNotFoundError(f"Standards file not found: {path}")
        
        with open(path, 'r') as f:
            return json.load(f)
    
    def _load_custom_messages(self) -> Dict:
        """Load custom/unrecognized messages from previous runs."""
        if not self.custom_messages_path.exists():
            return {}
        
        try:
            with open(self.custom_messages_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def _save_custom_messages(self):
        """Save custom messages to disk."""
        self.custom_messages_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.custom_messages_path, 'w') as f:
            json.dump(self.custom_messages, f, indent=2)
    
    def parse_spec(
        self,
        json_sidecar_path: Path,
        device_type: Optional[str] = None
    ) -> MessageInventory:
        """
        Parse message types and fields from JSON sidecar.
        
        Args:
            json_sidecar_path: Path to JSON sidecar file
            device_type: Device type identifier for custom messages
        
        Returns:
            MessageInventory with recognized/unrecognized messages and fields
        """
        # Load JSON sidecar and convert to PageBundle objects
        page_bundles = JSONSidecarWriter.load_document(json_sidecar_path)
        
        # Create DocumentNavigator for table queries
        navigator = DocumentNavigator(page_bundles)
        
        # Extract message types from content
        messages = self._extract_message_types(navigator)
        
        # Extract field specifications from tables
        fields = self._extract_field_specs(navigator)
        
        # Categorize messages
        recognized, unrecognized = self._categorize_messages(messages)
        
        # Auto-accept unrecognized messages (save to custom_messages.json)
        if device_type and unrecognized:
            self._auto_accept_unrecognized(device_type, unrecognized)
        
        # Build category summary
        categories = self._build_category_summary(recognized, unrecognized)
        
        return MessageInventory(
            recognized_messages=recognized,
            unrecognized_messages=unrecognized,
            field_specs=fields,
            categories=categories
        )
    
    def _extract_message_types(self, navigator: DocumentNavigator) -> List[MessageType]:
        """Extract message types from document content."""
        messages = []
        seen_messages = set()
        
        # Search all blocks for message type patterns
        for page_num in navigator.pages:
            page_bundle = navigator.page_bundles[page_num]
            
            for block in page_bundle.blocks:
                # Get content based on block type
                if hasattr(block, 'content'):
                    content = block.content
                else:
                    content = ""
                bbox = block.bbox
                citation = block.citation
                
                # Find message type patterns (try all pattern variations)
                matches = []
                matches.extend(self.MESSAGE_TYPE_PATTERN.finditer(content))
                matches.extend(self.MESSAGE_TYPE_ALT.finditer(content))
                matches.extend(self.MESSAGE_TYPE_CATCHALL.finditer(content))
                # Check for multi-segment vendor messages (Mes.mess2.mes3...)
                matches.extend(self.VENDOR_MULTI_SEGMENT.finditer(content))
                
                for match in matches:
                    # Extract message ID, normalize format
                    msg_id = None
                    if '^' in match.group(0):
                        # Handle OBS^OBS_R01 -> OBS.R01
                        parts = match.group(0).split('^')
                        if len(parts) == 2:
                            msg_id = parts[0] + '.' + parts[1].split('_')[-1]
                    elif self.VENDOR_MULTI_SEGMENT.match(match.group(0)):
                        msg_id = match.group(0)  # Keep vendor multi-segment as-is (Mes.mess2.mes3)
                    else:
                        msg_id = match.group(0).replace('_', '.').replace('^', '.')  # Normalize separators
                    
                    if msg_id and msg_id not in seen_messages:
                        seen_messages.add(msg_id)
                        
                        # Determine directionality from context
                        direction = self._infer_direction(content, msg_id)
                        
                        # Create citation object
                        cit = Citation(
                            citation_id=citation or f"p{page_num}_b{id(block)}",
                            page=page_num,
                            bbox=bbox,
                            source="text",
                            content_type="text"
                        )
                        
                        messages.append(MessageType(
                            message_id=msg_id,
                            direction=direction,
                            category="",  # Will be set during categorization
                            citations=[cit]
                        ))
        
        return messages
    
    def _extract_field_specs(self, navigator: DocumentNavigator) -> List[FieldSpec]:
        """Extract field specifications from tables."""
        field_specs = []
        seen_fields = set()
        
        # Iterate through all pages and their tables
        for page_num in navigator.pages:
            page_bundle = navigator.page_bundles[page_num]
            
            # Find table blocks
            for block in page_bundle.blocks:
                if hasattr(block, 'markdown_table') and block.markdown_table:
                    # Parse markdown table to extract field specs
                    field_data = self._parse_markdown_table(block.markdown_table, page_num, block.bbox)
                    for field in field_data:
                        if field and field.field_id not in seen_fields:
                            seen_fields.add(field.field_id)
                            field_specs.append(field)
        
        return field_specs
    
    def _parse_markdown_table(self, markdown_table: str, page: int, bbox: Tuple) -> List[FieldSpec]:
        """Parse a markdown table to extract field specifications."""
        field_specs = []
        lines = markdown_table.strip().split('\n')
        
        if len(lines) < 3:  # Need header + separator + at least one row
            return field_specs
        
        # Parse header to understand column structure
        header = [col.strip() for col in lines[0].strip('|').split('|')]
        
        # Skip separator line (lines[1])
        # Process data rows
        for line in lines[2:]:
            if not line.strip():
                continue
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            
            # Try to extract field ID from cells
            field_id = self._extract_field_id_from_cells(cells)
            if field_id:
                field_spec = FieldSpec(
                    field_id=field_id,
                    citation=Citation(
                        citation_id=f"p{page}_table",
                        page=page,
                        bbox=bbox,
                        source="table",
                        content_type="table"
                    )
                )
                # Try to populate other fields from table columns
                for i, col_name in enumerate(header):
                    if i < len(cells):
                        col_lower = col_name.lower()
                        if 'name' in col_lower:
                            field_spec.name = cells[i]
                        elif 'type' in col_lower:
                            field_spec.data_type = cells[i]
                        elif 'opt' in col_lower:
                            field_spec.optionality = cells[i]
                        elif 'card' in col_lower:
                            field_spec.cardinality = cells[i]
                        elif 'desc' in col_lower:
                            field_spec.description = cells[i]
                
                field_specs.append(field_spec)
        
        return field_specs
    
    def _extract_field_id_from_cells(self, cells: List[str]) -> Optional[str]:
        """Extract field ID (e.g., MSH-9) from table cells using all patterns."""
        for cell_value in cells:
            if isinstance(cell_value, str):
                # Try standard pattern first
                match = self.FIELD_PATTERN.search(cell_value)
                if match:
                    return match.group(0)
                
                # Try alternative pattern (dot separator)
                match = self.FIELD_PATTERN_ALT.search(cell_value)
                if match:
                    return f"{match.group(1)}-{match.group(2)}"  # Normalize to dash
                
                # Try catch-all pattern
                match = self.FIELD_PATTERN_CATCHALL.search(cell_value)
                if match:
                    return f"{match.group(1)}-{match.group(2)}"  # Normalize to dash
        return None
    
    def _parse_field_row(self, row: Dict, table, field_id: str) -> FieldSpec:
        """Parse field specification from table row."""
        # Try to extract common field attributes
        name = self._get_cell_value(row, ["name", "field name", "field"])
        data_type = self._get_cell_value(row, ["type", "data type", "dt"])
        optionality = self._get_cell_value(row, ["opt", "optionality", "usage"])
        cardinality = self._get_cell_value(row, ["card", "cardinality", "rpt"])
        length = self._get_cell_value(row, ["length", "len", "max length"])
        description = self._get_cell_value(row, ["description", "desc", "comment"])
        
        # Create citation from table
        citation = Citation(
            page=table.page,
            bbox=table.bbox,
            block_id=str(table.block_id),
            source="text",
            citation_id=f"p{table.page}_b{table.block_id}"
        )
        
        return FieldSpec(
            field_id=field_id,
            name=name,
            data_type=data_type,
            optionality=optionality,
            cardinality=cardinality,
            length=length,
            description=description,
            citation=citation
        )
    
    def _get_cell_value(self, row: Dict, possible_keys: List[str]) -> Optional[str]:
        """Get cell value trying multiple possible column names."""
        for key in possible_keys:
            for row_key, value in row.items():
                if key.lower() in row_key.lower() and value:
                    return str(value).strip()
        return None
    
    def _infer_direction(self, content: str, message_id: str) -> str:
        """Infer message directionality from context."""
        content_lower = content.lower()
        
        # Look for directional keywords
        if any(word in content_lower for word in ["device to", "analyzer to", "send to", "transmit to"]):
            return "→Host"
        elif any(word in content_lower for word in ["to device", "to analyzer", "query", "request"]):
            return "←Device"
        elif "bidirectional" in content_lower or "both directions" in content_lower:
            return "↔Both"
        
        # Default based on common POCT1 patterns
        msg_prefix = message_id.split('.')[0]
        if msg_prefix in ["OBS", "ORU"]:
            return "→Host"  # Results typically go to host
        elif msg_prefix in ["QCN", "QRY"]:
            return "←Device"  # Queries typically from host
        
        return "→Host"  # Default assumption
    
    def _categorize_messages(
        self,
        messages: List[MessageType]
    ) -> tuple[List[MessageType], List[MessageType]]:
        """Categorize messages as recognized vs unrecognized."""
        recognized = []
        unrecognized = []
        
        # Build set of all standard message prefixes
        standard_prefixes = set()
        for category_messages in self.standards.values():
            if isinstance(category_messages, list):
                standard_prefixes.update(category_messages)
        
        for msg in messages:
            # Extract prefix, handle various separators
            msg_prefix = msg.message_id.split('.')[0].split('^')[0].split('_')[0]
            
            # Check if vendor extension (Z** patterns)
            if self.VENDOR_PATTERN.match(msg_prefix) or self.VENDOR_PATTERN_EXTENDED.match(msg_prefix):
                msg.category = "vendor_specific"
                recognized.append(msg)
                continue
            
            # Check if multi-segment vendor message (e.g., Mes.mess2.mes3.mes4)
            if self.VENDOR_MULTI_SEGMENT.match(msg.message_id):
                msg.category = "vendor_specific"
                recognized.append(msg)
                continue
            
            # Check against standards (exact match)
            found = False
            for category, prefixes in self.standards.items():
                if category in ["metadata", "patterns"]:
                    continue
                if isinstance(prefixes, list) and msg_prefix in prefixes:
                    msg.category = category
                    recognized.append(msg)
                    found = True
                    break
            
            # If not found, check if it looks like a valid message type (3-letter uppercase)
            if not found:
                if len(msg_prefix) == 3 and msg_prefix.isupper() and msg_prefix.isalpha():
                    # Likely a valid POCT1 message type not in our standards list
                    msg.category = "unrecognized"
                    unrecognized.append(msg)
                else:
                    # Invalid format, still flag as unrecognized but with note
                    msg.category = "unrecognized"
                    unrecognized.append(msg)
        
        return recognized, unrecognized
    
    def _auto_accept_unrecognized(
        self,
        device_type: str,
        unrecognized: List[MessageType]
    ):
        """Auto-accept unrecognized messages and save to custom_messages.json."""
        if device_type not in self.custom_messages:
            self.custom_messages[device_type] = {}
        
        for msg in unrecognized:
            if msg.message_id not in self.custom_messages[device_type]:
                # Convert citations to serializable format
                citations_data = [
                    {
                        "page": c.page,
                        "bbox": c.bbox,
                        "block_id": c.block_id,
                        "source": c.source,
                        "citation_id": c.citation_id
                    }
                    for c in msg.citations
                ]
                
                self.custom_messages[device_type][msg.message_id] = {
                    "category": "vendor_specific",
                    "citations": citations_data,
                    "auto_accepted": True,
                    "timestamp": datetime.now().isoformat(),
                    "review_status": "pending",
                    "notes": f"Auto-accepted during spec parsing - Direction: {msg.direction}"
                }
        
        # Save to disk
        self._save_custom_messages()
    
    def _build_category_summary(
        self,
        recognized: List[MessageType],
        unrecognized: List[MessageType]
    ) -> Dict[str, List[str]]:
        """Build summary of messages by category."""
        summary = {}
        
        for msg in recognized + unrecognized:
            if msg.category not in summary:
                summary[msg.category] = []
            summary[msg.category].append(f"{msg.message_id}{msg.direction}")
        
        return summary
