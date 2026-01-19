"""
Enum value extractor for code/enumeration fields.

Extracts valid values for code fields from field descriptions and examples.
"""

from typing import List, Dict, Optional, Set
import re
from dataclasses import dataclass
from loguru import logger


@dataclass(frozen=True)
class EnumValue:
    """Represents a single enumeration value."""
    
    value: str
    description: Optional[str] = None
    is_default: bool = False  # If description says "Always:"


@dataclass
class EnumDefinition:
    """Represents an enumeration field with all possible values."""
    
    field_name: str
    field_type: str  # Should be "code"
    values: List[EnumValue]
    message_id: str
    page: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "field_name": self.field_name,
            "field_type": self.field_type,
            "values": [
                {
                    "value": v.value,
                    "description": v.description,
                    "is_default": v.is_default
                }
                for v in self.values
            ],
            "message_id": self.message_id,
            "page": self.page
        }


class EnumExtractor:
    """Extracts enumeration values from field descriptions."""
    
    # Patterns that indicate enumeration values
    ENUM_PATTERNS = [
        # "Always: value" or "Always: 'value'" or 'Always: "value"'
        r'[Aa]lways:\s*["\']?([A-Z_][A-Z0-9_]*)["\']?',
        
        # "values are X, Y, Z" or "Possible values are X, Y, Z"
        r'(?:possible\s+)?values?\s+(?:are|include):\s*([^.]+)',
        
        # "either X or Y" or "either 'X' or 'Y'"
        r'[Ee]ither\s+["\']?([A-Z_][A-Z0-9_]*)["\']?\s+or\s+["\']?([A-Z_][A-Z0-9_]*)["\']?',
        
        # "one of: X, Y, Z" or "one of X, Y, or Z"
        r'[Oo]ne\s+of[:\s]+([^.]+)',
        
        # "must be X, Y, or Z"
        r'must\s+be\s+([^.]+)',
        
        # V="VALUE" in XML examples
        r'V=["\']([^"\']+)["\']',
        
        # <field>VALUE</field> in XML examples
        r'<[^>]+>([A-Z_][A-Z0-9_]*)</[^>]+>',
        
        # Quoted single value: "VALUE" or 'VALUE'
        r'["\']([A-Z_][A-Z0-9_]+)["\']',
    ]
    
    # Common non-enum values to filter out
    FILTER_WORDS = {
        'empty', 'example', 'value', 'values', 'field', 'code',
        'string', 'number', 'integer', 'text', 'data', 'or', 'and',
        'the', 'a', 'an', 'is', 'are', 'be', 'in', 'for', 'to'
    }
    
    def extract_enum_values(
        self,
        field_name: str,
        field_type: str,
        description: str,
        example: Optional[str],
        message_id: str,
        page: int
    ) -> Optional[EnumDefinition]:
        """
        Extract enumeration values from field description and example.
        
        Args:
            field_name: Field name (e.g., "DTV.command_cd")
            field_type: Field type (should be "code")
            description: Field description text
            example: Example value (may contain more enum values)
            message_id: Parent message ID
            page: Page number
            
        Returns:
            EnumDefinition if values found, None otherwise
        """
        if field_type != "code":
            return None
        
        values: Set[EnumValue] = set()
        
        # Extract from description
        desc_values = self._extract_from_description(description)
        values.update(desc_values)
        
        # Extract from example
        if example:
            example_values = self._extract_from_example(example)
            values.update(example_values)
        
        if not values:
            return None
        
        # Convert set to list and sort
        sorted_values = sorted(values, key=lambda v: (not v.is_default, v.value))
        
        logger.debug(
            f"Extracted {len(sorted_values)} enum values for {field_name}: "
            f"{[v.value for v in sorted_values]}"
        )
        
        return EnumDefinition(
            field_name=field_name,
            field_type=field_type,
            values=sorted_values,
            message_id=message_id,
            page=page
        )
    
    def _extract_from_description(self, description: str) -> Set[EnumValue]:
        """Extract enum values from description text."""
        values: Set[EnumValue] = set()
        
        if not description:
            return values
        
        # Clean HTML tags
        description = re.sub(r'<br\s*/?>', ' ', description)
        description = re.sub(r'<[^>]+>', '', description)
        
        # Check for "Always: VALUE" pattern (default value) - handle quotes
        always_match = re.search(
            r'[Aa]lways:\s*["\']?([A-Z_][A-Z0-9_]*)["\']?',
            description
        )
        if always_match:
            value = always_match.group(1).strip()
            if self._is_valid_enum_value(value):
                values.add(EnumValue(value=value, is_default=True))
        
        # Check for "values are X, Y, Z" or "possible values are"
        values_match = re.search(
            r'(?:[Pp]ossible\s+)?values?\s+(?:are|include)[:\s]+([^.]+)',
            description
        )
        if values_match:
            value_list = values_match.group(1)
            extracted = self._parse_value_list(value_list)
            values.update(extracted)
        
        # Check for "either X or Y"
        either_match = re.search(
            r'[Ee]ither\s+["\']?([A-Z_][A-Z0-9_]*)["\']?\s+or\s+["\']?([A-Z_][A-Z0-9_]*)["\']?',
            description
        )
        if either_match:
            val1 = either_match.group(1).strip()
            val2 = either_match.group(2).strip()
            if self._is_valid_enum_value(val1):
                values.add(EnumValue(value=val1))
            if self._is_valid_enum_value(val2):
                values.add(EnumValue(value=val2))
        
        # Check for "one of: X, Y, Z"
        oneof_match = re.search(r'[Oo]ne\s+of[:\s]+([^.]+)', description)
        if oneof_match:
            value_list = oneof_match.group(1)
            extracted = self._parse_value_list(value_list)
            values.update(extracted)
        
        # Check for V="VALUE" in XML examples within description
        xml_values = re.findall(r'V=["\']([^"\']+)["\']', description)
        for value in xml_values:
            if self._is_valid_enum_value(value):
                values.add(EnumValue(value=value))
        
        return values
    
    def _extract_from_example(self, example: str) -> Set[EnumValue]:
        """Extract enum values from example field."""
        values: Set[EnumValue] = set()
        
        if not example:
            return values
        
        # Clean HTML tags
        example = re.sub(r'<br\s*/?>', ' ', example)
        example = re.sub(r'<[^>]+>', '', example)
        
        # Check for "Always: VALUE" pattern first
        always_match = re.search(r'[Aa]lways:\s*["\']?([A-Z_][A-Z0-9_]*)["\']?', example)
        if always_match:
            value = always_match.group(1).strip()
            if self._is_valid_enum_value(value):
                values.add(EnumValue(value=value, is_default=True))
                return values  # If "Always:" found, use that and return
        
        # Strip quotes
        example_clean = example.strip().strip('"').strip("'")
        
        # Check if it's a single uppercase value
        if self._is_valid_enum_value(example_clean):
            values.add(EnumValue(value=example_clean))
        
        # Check for comma-separated list
        if ',' in example_clean:
            extracted = self._parse_value_list(example_clean)
            values.update(extracted)
        
        # Check for V="VALUE" pattern
        xml_values = re.findall(r'V=["\']([^"\']+)["\']', example)
        for value in xml_values:
            if self._is_valid_enum_value(value):
                values.add(EnumValue(value=value))
        
        return values
    
    def _parse_value_list(self, value_list: str) -> Set[EnumValue]:
        """Parse a comma/or-separated list of values."""
        values: Set[EnumValue] = set()
        
        # Split by comma, 'or', 'and'
        parts = re.split(r'[,]|\s+or\s+|\s+and\s+', value_list)
        
        for part in parts:
            # Clean up
            part = part.strip().strip('"').strip("'").strip()
            
            # Extract uppercase identifiers
            matches = re.findall(r'[A-Z_][A-Z0-9_]*', part)
            for match in matches:
                if self._is_valid_enum_value(match):
                    values.add(EnumValue(value=match))
        
        return values
    
    def _is_valid_enum_value(self, value: str) -> bool:
        """Check if a value looks like a valid enum value."""
        if not value:
            return False
        
        # Must be at least 1 character (allow single chars/digits for codes)
        if len(value) < 1:
            return False
        
        # Allow single uppercase letters or digits (common for codes: "R", "M", "1")
        if len(value) == 1 and (value.isupper() or value.isdigit()):
            return True
        
        # For longer values:
        # Must start with letter or digit
        if not (value[0].isalpha() or value[0].isdigit()):
            return False
        
        # Must be mostly uppercase or mixed with underscores or all digits
        if not (value.isupper() or '_' in value or value.isdigit()):
            return False
        
        # Filter out common words (but allow short codes)
        if len(value) > 2 and value.lower() in self.FILTER_WORDS:
            return False
        
        # Must contain only alphanumeric and underscore
        if not re.match(r'^[A-Z0-9][A-Z0-9_]*$', value, re.IGNORECASE):
            return False
        
        return True


def extract_enums_from_fields(
    fields: List[Dict]
) -> List[EnumDefinition]:
    """
    Extract enum definitions from a list of field definitions.
    
    Args:
        fields: List of field definition dicts
        
    Returns:
        List of EnumDefinition objects
    """
    extractor = EnumExtractor()
    enums = []
    
    for field in fields:
        if field.get("field_type") != "code":
            continue
        
        enum_def = extractor.extract_enum_values(
            field_name=field["field_name"],
            field_type=field["field_type"],
            description=field.get("description", ""),
            example=field.get("example"),
            message_id=field.get("message_id", "unknown"),
            page=field.get("page", 0)
        )
        
        if enum_def:
            enums.append(enum_def)
    
    logger.info(f"Extracted enum definitions for {len(enums)} code fields")
    return enums
