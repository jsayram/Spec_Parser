"""
Message schema builder for POCT1-A specifications.

Links extracted fields to their parent messages and builds complete
message schemas with field specifications.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
from loguru import logger

from spec_parser.extractors.field_parser import FieldDefinition
from spec_parser.schemas.poct1_entities import MessageDefinition, FieldSpec
from spec_parser.schemas.citation import Citation


class MessageSchemaBuilder:
    """Builds complete message schemas from extracted field definitions."""
    
    def __init__(self):
        """Initialize schema builder."""
        pass
    
    def build_schemas(
        self,
        fields: List[FieldDefinition],
        citations: Dict[str, Dict[str, Any]]
    ) -> Dict[str, MessageDefinition]:
        """
        Build message schemas from field definitions.
        
        Args:
            fields: List of field definitions extracted from spec
            citations: Citation metadata indexed by citation_id
            
        Returns:
            Dictionary mapping message_id to MessageDefinition
        """
        # Group fields by message
        message_fields = defaultdict(list)
        for field in fields:
            message_fields[field.message_id].append(field)
        
        # Build schemas
        schemas = {}
        for message_id, field_list in message_fields.items():
            schema = self._build_message_schema(
                message_id,
                field_list,
                citations
            )
            schemas[message_id] = schema
        
        logger.info(f"Built {len(schemas)} message schemas")
        return schemas
    
    def _build_message_schema(
        self,
        message_id: str,
        fields: List[FieldDefinition],
        citations: Dict[str, Dict[str, Any]]
    ) -> MessageDefinition:
        """
        Build a single message schema.
        
        Args:
            message_id: Message identifier (e.g., "HEL.R01")
            fields: List of fields for this message
            citations: Citation metadata
            
        Returns:
            Complete message definition
        """
        # Convert fields to FieldSpec objects
        field_specs = []
        for field in fields:
            field_spec = self._convert_field_to_spec(field, citations)
            if field_spec:
                field_specs.append(field_spec)
        
        # Use first field's citation for message citation
        # (fields are from same table/section)
        first_citation_id = fields[0].citation_id if fields else None
        citation_data = citations.get(first_citation_id, {}) if first_citation_id else {}
        
        # Build Citation object
        source_citation = Citation(
            citation_id=first_citation_id or f"{message_id}_unknown",
            page=fields[0].page if fields else 0,
            bbox=citation_data.get("bbox", [0.0, 0.0, 0.0, 0.0]),
            source=citation_data.get("source", "text"),
            content_type=citation_data.get("content_type", "text")
        )
        
        # Extract message type and trigger
        parts = message_id.split('.')
        message_type = message_id
        trigger_event = parts[1] if len(parts) > 1 else None
        
        # Build description from message type
        description = self._generate_message_description(message_id)
        
        message_def = MessageDefinition(
            message_type=message_type,
            trigger_event=trigger_event,
            description=description,
            structure=None,  # TODO: Extract from spec if available
            fields=field_specs,
            citation=first_citation_id or f"{message_id}_unknown",
            source_citation=source_citation
        )
        
        return message_def
    
    def _convert_field_to_spec(
        self,
        field: FieldDefinition,
        citations: Dict[str, Dict[str, Any]]
    ) -> Optional[FieldSpec]:
        """
        Convert FieldDefinition to FieldSpec.
        
        Args:
            field: Field definition from parser
            citations: Citation metadata
            
        Returns:
            FieldSpec object or None if conversion fails
        """
        if not field.field_name:
            return None
        
        citation_data = citations.get(field.citation_id, {}) if field.citation_id else {}
        
        # Build Citation object
        source_citation = Citation(
            citation_id=field.citation_id or f"{field.field_name}_unknown",
            page=field.page,
            bbox=citation_data.get("bbox", [0.0, 0.0, 0.0, 0.0]),
            source=citation_data.get("source", "text"),
            content_type=citation_data.get("content_type", "text")
        )
        
        field_spec = FieldSpec(
            name=field.field_name,
            seq=None,  # Extract from field name if present (e.g., "H-1")
            data_type=field.field_type,
            optionality=field.optionality,
            cardinality=None,  # Extract from description if present
            length=None,  # Extract from description if present
            description=field.description,
            citation=field.citation_id or f"{field.field_name}_unknown",
            source_citation=source_citation
        )
        
        return field_spec
    
    def _generate_message_description(self, message_id: str) -> str:
        """
        Generate human-readable description for message.
        
        Args:
            message_id: Message identifier (e.g., "HEL.R01", "VENDOR.DEVICE.MSG")
            
        Returns:
            Message description
        """
        # Common POCT1-A message descriptions (fallback only, not authoritative)
        # These are generic examples - actual descriptions should come from spec
        common_descriptions = {
            "HEL.R01": "Hello Message - Device introduction",
            "ACK.R01": "Acknowledgement Message",
            "DST.R01": "Device Status Message",
            "DTV.R01": "Basic Directive Message",
            "DTV.R02": "Complex Directive Message",
            "OBS.R01": "Observation Message - Patient Results",
            "OBS.R02": "Observation Message - Non-Patient Results",
            "OPL.R01": "Operator List Message",
            "EOT.R01": "End Of Topic Message",
            "END.R01": "End Conversation Message",
            "QCN.R01": "Quality Control Message"
        }
        
        # Use common description if available, otherwise generate generic
        return common_descriptions.get(message_id, f"{message_id} Message")


def build_message_schemas_from_document(
    document: Dict[str, Any]
) -> Dict[str, MessageDefinition]:
    """
    Build complete message schemas from document.
    
    Args:
        document: Document JSON with pages array
        
    Returns:
        Dictionary mapping message_id to MessageDefinition
    """
    from spec_parser.extractors.field_parser import parse_fields_from_document
    
    # Extract fields
    fields = parse_fields_from_document(document)
    
    # Collect all citations from document
    citations = {}
    for page in document.get("pages", []):
        page_citations = page.get("citations", {})
        citations.update(page_citations)
    
    # Build schemas
    builder = MessageSchemaBuilder()
    schemas = builder.build_schemas(fields, citations)
    
    return schemas
