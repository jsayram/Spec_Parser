"""
POCT1-specific entity data models.

All entities include mandatory provenance (page, bbox, source).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from spec_parser.schemas.citation import Citation


class FieldSpec(BaseModel):
    """
    POCT1 field specification.
    
    Represents a single field in a message definition with type,
    optionality, and cardinality information.
    """
    
    name: str = Field(..., description="Field name (e.g., 'MSH-1 Field Separator')")
    seq: Optional[str] = Field(None, description="Sequence number (e.g., 'MSH-1')")
    data_type: Optional[str] = Field(None, description="POCT1 data type (e.g., 'ST', 'ID', 'TS', 'CE', 'CX')")
    optionality: Optional[str] = Field(None, description="R (Required), O (Optional), C (Conditional)")
    cardinality: Optional[str] = Field(None, description="Repetition (e.g., '[1..1]', '[0..*]')")
    length: Optional[int] = Field(None, description="Maximum field length")
    description: Optional[str] = Field(None, description="Field description/usage")
    
    # Provenance
    citation: str = Field(..., description="Citation ID linking to source location")
    source_citation: Citation = Field(..., description="Complete citation with bbox")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "MSH-1 Field Separator",
                "seq": "MSH-1",
                "data_type": "ST",
                "optionality": "R",
                "cardinality": "[1..1]",
                "length": 1,
                "description": "Field separator character, always |",
                "citation": "p45_tbl3",
                "source_citation": {
                    "page": 45,
                    "bbox": [100.0, 200.0, 500.0, 250.0],
                    "source": "text",
                    "content_type": "table"
                }
            }
        }


class MessageDefinition(BaseModel):
    """
    POCT1 message definition.
    
    Represents a complete message type (e.g., OBS.R01, QCN.R01) with
    structure and field specifications.
    """
    
    message_type: str = Field(..., description="Message type code (e.g., 'OBS.R01')")
    trigger_event: Optional[str] = Field(None, description="POCT1 trigger event (e.g., R01, J01, Q02)")
    description: str = Field(..., description="Message purpose and usage")
    structure: Optional[str] = Field(None, description="Message structure definition")
    fields: List[FieldSpec] = Field(default_factory=list, description="Field specifications")
    
    # Provenance
    citation: str = Field(..., description="Citation ID linking to source location")
    source_citation: Citation = Field(..., description="Complete citation with bbox")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_type": "OBS.R01",
                "trigger_event": "R01",
                "description": "Unsolicited transmission of an observation message",
                "structure": "MSH-[{PID-[{OBR-[{OBX}]}]}]",
                "fields": [],
                "citation": "p23_msg1",
                "source_citation": {
                    "page": 23,
                    "bbox": [50.0, 100.0, 550.0, 400.0],
                    "source": "text",
                    "content_type": "text"
                }
            }
        }


class XMLSchema(BaseModel):
    """
    XML schema or snippet from specification.
    
    Captures XML structure definitions, examples, or namespace declarations.
    """
    
    name: str = Field(..., description="Schema name or identifier")
    content: str = Field(..., description="XML content (schema, snippet, example)")
    schema_type: str = Field(..., description="Type: 'schema', 'example', 'namespace'")
    description: Optional[str] = Field(None, description="Schema purpose/context")
    
    # Provenance
    citation: str = Field(..., description="Citation ID linking to source location")
    source_citation: Citation = Field(..., description="Complete citation with bbox")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "POCT1 Observation Schema",
                "content": "<xs:element name='observation'>...</xs:element>",
                "schema_type": "schema",
                "description": "XML schema for POCT1 observation element",
                "citation": "p67_xml1",
                "source_citation": {
                    "page": 67,
                    "bbox": [100.0, 150.0, 500.0, 600.0],
                    "source": "text",
                    "content_type": "text"
                }
            }
        }


class VendorExtension(BaseModel):
    """
    Vendor-specific extension or namespace.
    
    Captures vendor customizations, proprietary fields, or namespace definitions.
    """
    
    vendor: str = Field(..., description="Vendor name (e.g., 'Roche', 'Abbott')")
    namespace: Optional[str] = Field(None, description="XML namespace or field prefix")
    extension_type: str = Field(..., description="Type: 'field', 'namespace', 'message'")
    description: str = Field(..., description="Extension purpose and usage")
    content: Optional[str] = Field(None, description="Extension content or definition")
    
    # Provenance
    citation: str = Field(..., description="Citation ID linking to source location")
    source_citation: Citation = Field(..., description="Complete citation with bbox")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vendor": "Roche",
                "namespace": "http://www.roche.com/poct1/ext",
                "extension_type": "namespace",
                "description": "Roche proprietary extensions for device control",
                "content": "xmlns:roche='http://www.roche.com/poct1/ext'",
                "citation": "p89_ext1",
                "source_citation": {
                    "page": 89,
                    "bbox": [100.0, 200.0, 500.0, 250.0],
                    "source": "text",
                    "content_type": "text"
                }
            }
        }


class ExtractedEntities(BaseModel):
    """
    Complete collection of extracted entities from a specification document.
    
    Aggregates all POCT1-specific entities with full provenance.
    """
    
    pdf_name: str = Field(..., description="Source PDF filename")
    total_pages: int = Field(..., description="Total pages processed")
    
    messages: List[MessageDefinition] = Field(
        default_factory=list,
        description="Extracted message definitions"
    )
    fields: List[FieldSpec] = Field(
        default_factory=list,
        description="Extracted field specifications"
    )
    xml_schemas: List[XMLSchema] = Field(
        default_factory=list,
        description="Extracted XML schemas and snippets"
    )
    vendor_extensions: List[VendorExtension] = Field(
        default_factory=list,
        description="Extracted vendor extensions"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extraction metadata (timestamp, version, etc.)"
    )
    
    def total_entities(self) -> int:
        """Count total extracted entities"""
        return (
            len(self.messages) +
            len(self.fields) +
            len(self.xml_schemas) +
            len(self.vendor_extensions)
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "pdf_name": "poct1-v6-specification",
                "total_pages": 236,
                "messages": [],
                "fields": [],
                "xml_schemas": [],
                "vendor_extensions": [],
                "metadata": {
                    "extracted_at": "2026-01-18T00:00:00Z",
                    "extractor_version": "1.0.0"
                }
            }
        }
