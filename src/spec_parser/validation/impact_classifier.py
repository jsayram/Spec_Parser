"""
Impact classification for spec version changes.

Classifies changes between spec versions as HIGH, MEDIUM, or LOW impact
to determine rebuild requirements and approval workflows.
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
import re


class ImpactLevel(Enum):
    """Impact level for spec changes - determines rebuild requirements."""
    HIGH = "HIGH"      # Breaking changes requiring full rebuild + approval
    MEDIUM = "MEDIUM"  # Functional changes requiring rebuild + approval
    LOW = "LOW"        # Documentation-only, no rebuild needed


class ChangeType(Enum):
    """Types of changes detected between spec versions."""
    # HIGH impact changes
    MESSAGE_ADDED = "MESSAGE_ADDED"
    MESSAGE_REMOVED = "MESSAGE_REMOVED"
    FIELD_RENAMED = "FIELD_RENAMED"
    FIELD_TYPE_CHANGED = "FIELD_TYPE_CHANGED"
    CARDINALITY_CHANGED = "CARDINALITY_CHANGED"  # R↔O changes
    OPTIONALITY_CHANGED = "OPTIONALITY_CHANGED"  # Required ↔ Optional
    
    # MEDIUM impact changes
    FIELD_ADDED = "FIELD_ADDED"  # New optional field
    DEFAULT_VALUE_CHANGED = "DEFAULT_VALUE_CHANGED"
    VENDOR_EXTENSION_MODIFIED = "VENDOR_EXTENSION_MODIFIED"
    TABLE_STRUCTURE_CHANGED = "TABLE_STRUCTURE_CHANGED"
    
    # LOW impact changes
    DOCUMENTATION_UPDATED = "DOCUMENTATION_UPDATED"
    WHITESPACE_CHANGED = "WHITESPACE_CHANGED"
    FORMATTING_CHANGED = "FORMATTING_CHANGED"
    TYPO_FIXED = "TYPO_FIXED"
    EXAMPLE_UPDATED = "EXAMPLE_UPDATED"
    DIAGRAM_CHANGED = "DIAGRAM_CHANGED"
    
    # Content changes (need further analysis)
    CONTENT_MODIFIED = "CONTENT_MODIFIED"
    BLOCK_ADDED = "BLOCK_ADDED"
    BLOCK_REMOVED = "BLOCK_REMOVED"
    
    # TODO HL7 EXTENSION: Add HL7-specific change types
    # SEGMENT_CHANGED = "SEGMENT_CHANGED"
    # COMPONENT_CHANGED = "COMPONENT_CHANGED"
    # SUBCOMPONENT_CHANGED = "SUBCOMPONENT_CHANGED"


@dataclass
class ChangeImpact:
    """Result of change classification."""
    level: ImpactLevel
    change_type: ChangeType
    reasoning: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None


# Message type patterns for POCT1
MESSAGE_TYPE_PATTERN = re.compile(r'\b([A-Z]{3})\.[A-Z]\d{2}\b')  # e.g., OBS.R01
FIELD_PATTERN = re.compile(r'\b([A-Z]{3})-(\d+)\b')  # e.g., MSH-9, OBX-3


def classify_change(
    old_content: Optional[str],
    new_content: Optional[str],
    block_type: str = "text",
    context: Optional[Dict[str, Any]] = None
) -> ChangeImpact:
    """
    Classify change between old and new content.
    
    Args:
        old_content: Previous content (None if added)
        new_content: Current content (None if removed)
        block_type: Type of block ("text", "table", "picture", "graphics")
        context: Additional context (metadata, surrounding blocks, etc.)
    
    Returns:
        ChangeImpact with level, type, and reasoning
    """
    context = context or {}
    
    # Block added
    if old_content is None and new_content is not None:
        return _classify_addition(new_content, block_type, context)
    
    # Block removed
    if old_content is not None and new_content is None:
        return _classify_removal(old_content, block_type, context)
    
    # Block modified
    if old_content != new_content:
        return _classify_modification(old_content, new_content, block_type, context)
    
    # No change (shouldn't happen, but handle gracefully)
    return ChangeImpact(
        level=ImpactLevel.LOW,
        change_type=ChangeType.WHITESPACE_CHANGED,
        reasoning="No meaningful change detected",
        old_value=old_content,
        new_value=new_content
    )


def _classify_addition(content: str, block_type: str, context: Dict[str, Any]) -> ChangeImpact:
    """Classify newly added content."""
    # Check for message type additions
    if _contains_message_type(content):
        return ChangeImpact(
            level=ImpactLevel.HIGH,
            change_type=ChangeType.MESSAGE_ADDED,
            reasoning="New message type added - requires parser updates and full rebuild",
            new_value=_extract_message_types(content)
        )
    
    # Check for field additions in tables
    if block_type == "table" and _contains_field_definition(content):
        # New field in table - check if required or optional
        if _is_required_field(content):
            return ChangeImpact(
                level=ImpactLevel.HIGH,
                change_type=ChangeType.FIELD_ADDED,
                reasoning="Required field added - breaks existing messages without this field",
                new_value=_extract_field_info(content)
            )
        else:
            return ChangeImpact(
                level=ImpactLevel.MEDIUM,
                change_type=ChangeType.FIELD_ADDED,
                reasoning="Optional field added - may require parser updates",
                new_value=_extract_field_info(content)
            )
    
    # Vendor extension additions
    if _contains_vendor_extension(content):
        return ChangeImpact(
            level=ImpactLevel.MEDIUM,
            change_type=ChangeType.VENDOR_EXTENSION_MODIFIED,
            reasoning="Vendor-specific extension added - device-specific logic may need updates",
            new_value=content[:100]
        )
    
    # New documentation or examples
    return ChangeImpact(
        level=ImpactLevel.LOW,
        change_type=ChangeType.BLOCK_ADDED,
        reasoning="New content added - documentation or examples, no functional impact",
        new_value=content[:100] if len(content) > 100 else content
    )


def _classify_removal(content: str, block_type: str, context: Dict[str, Any]) -> ChangeImpact:
    """Classify removed content."""
    # Check for message type removals
    if _contains_message_type(content):
        return ChangeImpact(
            level=ImpactLevel.HIGH,
            change_type=ChangeType.MESSAGE_REMOVED,
            reasoning="Message type removed - breaks existing parsers expecting this message",
            old_value=_extract_message_types(content)
        )
    
    # Check for field removals in tables
    if block_type == "table" and _contains_field_definition(content):
        return ChangeImpact(
            level=ImpactLevel.HIGH,
            change_type=ChangeType.BLOCK_REMOVED,
            reasoning="Field definition removed - breaks field mapping and validation",
            old_value=_extract_field_info(content)
        )
    
    # Documentation removal
    return ChangeImpact(
        level=ImpactLevel.LOW,
        change_type=ChangeType.BLOCK_REMOVED,
        reasoning="Content removed - likely documentation cleanup, no functional impact",
        old_value=content[:100] if len(content) > 100 else content
    )


def _classify_modification(
    old_content: str,
    new_content: str,
    block_type: str,
    context: Dict[str, Any]
) -> ChangeImpact:
    """Classify modified content."""
    # Check for field renames
    old_fields = _extract_field_names(old_content)
    new_fields = _extract_field_names(new_content)
    if old_fields and new_fields and old_fields != new_fields:
        return ChangeImpact(
            level=ImpactLevel.HIGH,
            change_type=ChangeType.FIELD_RENAMED,
            reasoning=f"Field name changed - breaks field mapping ({old_fields} → {new_fields})",
            old_value=str(old_fields),
            new_value=str(new_fields)
        )
    
    # Check for type changes
    old_type = _extract_data_type(old_content)
    new_type = _extract_data_type(new_content)
    if old_type and new_type and old_type != new_type:
        return ChangeImpact(
            level=ImpactLevel.HIGH,
            change_type=ChangeType.FIELD_TYPE_CHANGED,
            reasoning=f"Field type changed - breaks data validation ({old_type} → {new_type})",
            old_value=old_type,
            new_value=new_type
        )
    
    # Check for cardinality/optionality changes
    old_opt = _extract_optionality(old_content)
    new_opt = _extract_optionality(new_content)
    if old_opt and new_opt and old_opt != new_opt:
        return ChangeImpact(
            level=ImpactLevel.HIGH,
            change_type=ChangeType.CARDINALITY_CHANGED,
            reasoning=f"Field requirement changed - breaks validation logic ({old_opt} → {new_opt})",
            old_value=old_opt,
            new_value=new_opt
        )
    
    # Check for whitespace-only changes
    if old_content.strip() == new_content.strip():
        return ChangeImpact(
            level=ImpactLevel.LOW,
            change_type=ChangeType.WHITESPACE_CHANGED,
            reasoning="Whitespace or formatting change only - no functional impact",
            old_value=None,
            new_value=None
        )
    
    # Check if only capitalization changed (likely typo fix)
    if old_content.lower() == new_content.lower():
        return ChangeImpact(
            level=ImpactLevel.LOW,
            change_type=ChangeType.TYPO_FIXED,
            reasoning="Capitalization change only - likely typo correction",
            old_value=old_content[:50],
            new_value=new_content[:50]
        )
    
    # Table structure changes
    if block_type == "table":
        return ChangeImpact(
            level=ImpactLevel.MEDIUM,
            change_type=ChangeType.TABLE_STRUCTURE_CHANGED,
            reasoning="Table content modified - may affect field extraction or validation",
            old_value=old_content[:100],
            new_value=new_content[:100]
        )
    
    # General content modification
    return ChangeImpact(
        level=ImpactLevel.LOW,
        change_type=ChangeType.DOCUMENTATION_UPDATED,
        reasoning="Content updated - likely documentation improvement, no structural changes detected",
        old_value=old_content[:100],
        new_value=new_content[:100]
    )


# Helper functions for pattern detection

def _contains_message_type(content: str) -> bool:
    """Check if content contains POCT1 message type definitions."""
    return bool(MESSAGE_TYPE_PATTERN.search(content))


def _extract_message_types(content: str) -> str:
    """Extract message types from content."""
    matches = MESSAGE_TYPE_PATTERN.findall(content)
    return ", ".join(matches) if matches else content[:50]


def _contains_field_definition(content: str) -> bool:
    """Check if content contains field definitions (e.g., MSH-9, OBX-3)."""
    return bool(FIELD_PATTERN.search(content))


def _extract_field_info(content: str) -> str:
    """Extract field identifiers from content."""
    matches = FIELD_PATTERN.findall(content)
    if matches:
        return ", ".join([f"{seg}-{num}" for seg, num in matches])
    return content[:50]


def _extract_field_names(content: str) -> Optional[str]:
    """Extract field names from content."""
    # Look for common patterns like "Field Name:", "Field:", etc.
    match = re.search(r'(?:Field|Name):\s*([A-Za-z_][A-Za-z0-9_]*)', content, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_data_type(content: str) -> Optional[str]:
    """Extract data type from content (ST, NM, CX, etc.)."""
    # Common POCT1 data types
    match = re.search(r'\b(ST|NM|CX|CE|TS|DTM|ID|IS|TX|FT|DT|TM)\b', content)
    return match.group(1) if match else None


def _extract_optionality(content: str) -> Optional[str]:
    """Extract optionality/cardinality (R, O, C, etc.)."""
    # Look for R (required), O (optional), C (conditional)
    match = re.search(r'\b([ROC])(?:\[\d+\.\.\d+\])?\b', content)
    return match.group(1) if match else None


def _is_required_field(content: str) -> bool:
    """Check if field is marked as required."""
    opt = _extract_optionality(content)
    return opt == "R" if opt else False


def _contains_vendor_extension(content: str) -> bool:
    """Check if content contains vendor-specific extensions (Z** patterns)."""
    return bool(re.search(r'\bZ[A-Z]{2}\b', content))


# TODO HL7 EXTENSION: Add protocol-specific classification logic
# def classify_hl7_change(old_content, new_content, context) -> ChangeImpact:
#     """Classify changes specific to HL7 v2.x messages."""
#     pass
