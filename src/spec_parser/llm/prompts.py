"""Prompt templates for POCT1-A specification extraction."""

from typing import Optional


class PromptTemplates:
    """POCT1-A extraction prompts with citation requirements."""

    @staticmethod
    def message_discovery(context_chunks: list[str], device_name: str) -> str:
        """Prompt for discovering all POCT1-A messages in spec.
        
        Args:
            context_chunks: Retrieved text chunks from spec
            device_name: Device identifier
            
        Returns:
            Formatted prompt
        """
        context = "\n\n---\n\n".join(context_chunks)
        
        return f"""You are analyzing a POCT1-A specification for the {device_name} device.

Your task: Extract ALL POCT1-A message types mentioned in this specification.

DISCOVER ALL message types including:
- Standard POCT1-A messages (format: XXX.R01, XXX.R02, etc.) - DO NOT assume which ones exist
- Vendor-specific extensions (format: VENDOR.DEVICE.MESSAGE or Z-prefixed messages)
- Custom messages (any device-specific communication patterns)
- Bidirectional patterns (request/response, query/acknowledgment)

Search the context for:
- Table of contents listing message names
- "Supported messages" or "Implemented messages" sections
- Message structure definitions with names
- Communication flow diagrams showing message exchanges
- Vendor extension or custom message namespaces
- Bidirectional communication patterns (which messages trigger which responses)

Context from specification:
{context}

Return a JSON array with ALL message types found. For each:
- message_type: The message identifier (e.g., "OBS.R01", "ROCHE.LIAT.CFG", "DEVICE_STATUS")
- direction: "device_to_host", "host_to_device", or "bidirectional"
- description: Brief description from spec
- message_category: "standard" (POCT1-A standard), "vendor_extension" (vendor namespace), or "custom"
- namespace: Vendor namespace if applicable (e.g., "ROCHE.LIAT"), null otherwise
- triggers: Array of message names this message can trigger as response (e.g., ["ACK.R01"])
- citations: Array of page numbers where found (e.g., ["p12", "p45"])

Example output:
[
  {{
    "message_type": "OBS.R01",
    "direction": "device_to_host",
    "description": "Patient-related observation result",
    "message_category": "standard",
    "namespace": null,
    "triggers": ["ACK.R01"],
    "citations": ["p20"]
  }},
  {{
    "message_type": "VENDOR.DEVICE.CFG",
    "direction": "host_to_device",
    "description": "Device-specific configuration",
    "message_category": "vendor_extension",
    "namespace": "VENDOR.DEVICE",
    "triggers": [],
    "citations": ["p125"]
  }}
]

IMPORTANT: 
- DO NOT list only common POCT1-A messages - discover what THIS device actually implements
- Include ALL messages: standard, vendor extensions, custom
- Extract from context, do not assume"""

    @staticmethod
    def message_field_extraction(
        message_type: str,
        context_chunks: list[str],
        device_name: str
    ) -> str:
        """Prompt for extracting field definitions for a specific message.
        
        Args:
            message_type: POCT1-A message type (e.g., "OBS.R01")
            context_chunks: Retrieved text chunks relevant to this message
            device_name: Device identifier
            
        Returns:
            Formatted prompt
        """
        context = "\n\n---\n\n".join(context_chunks)
        
        return f"""You are extracting field definitions for the {message_type} message from the {device_name} POCT1-A specification.

Context from specification:
{context}

Extract ALL field definitions for this message. Discover fields from the context - DO NOT assume standard fields exist.

Look for ANY field patterns in this specification:
- Field names with any extensions or formats
- Data element names and identifiers
- Component names in message structures
- Segment field definitions
- Vendor-specific field additions
- Enum values and coded vocabularies
- Field hierarchies and repeating structures

For each field include:
- field_name: Field identifier exactly as specified in document
- field_description: What this field contains
- data_type: Data type (string, number, datetime, boolean, enum, object, array, etc.)
- optionality: "required", "optional", "conditional", or "depends" (with condition)
- cardinality: "1", "0..1", "1..*", "0..*" or specific range
- max_length: Maximum field length (if specified)
- allowed_values: Array of allowed values, codes, or enumerations (if specified)
- default_value: Default value (if specified)
- usage_notes: Any implementation notes, constraints, or vendor-specific details
- citations: Page numbers or sections where field is defined

Return JSON array. Example:
[
  {{
    "field_name": "observation_identifier",
    "field_description": "Unique identifier for this observation type",
    "data_type": "string",
    "optionality": "required",
    "cardinality": "1",
    "max_length": 50,
    "allowed_values": [],
    "default_value": null,
    "usage_notes": "Device assigns based on test type",
    "citations": ["p15"]
  }},
  {{
    "field_name": "result_status",
    "field_description": "Status of result processing",
    "data_type": "enum",
    "optionality": "required",
    "cardinality": "1",
    "max_length": 1,
    "allowed_values": ["F", "C", "P", "X"],
    "default_value": "F",
    "usage_notes": "F=Final, C=Corrected, P=Preliminary, X=Cancelled",
    "citations": ["p23"]
  }},
  {{
    "field_name": "vendor_extension",
    "field_description": "Vendor-specific data block",
    "data_type": "object",
    "optionality": "optional",
    "cardinality": "0..1",
    "max_length": null,
    "allowed_values": [],
    "default_value": null,
    "usage_notes": "Contains device-specific configuration or metadata",
    "citations": ["p125"]
  }}
]

CRITICAL: 
- Extract fields ONLY from the provided context
- Include vendor-specific fields and extensions
- Do not assume standard POCT1-A field names - discover what THIS message uses
- Include ALL citations"""

    @staticmethod
    def sample_message_extraction(
        message_type: str,
        context_chunks: list[str],
        device_name: str
    ) -> str:
        """Prompt for extracting example messages from spec.
        
        Args:
            message_type: POCT1-A message type
            context_chunks: Retrieved text chunks with examples
            device_name: Device identifier
            
        Returns:
            Formatted prompt
        """
        context = "\n\n---\n\n".join(context_chunks)
        
        return f"""Extract example {message_type} messages from the {device_name} specification.

Context:
{context}

Return a JSON object with:
- message_type: "{message_type}"
- examples: Array of example message objects (exactly as shown in spec, typically JSON or XML format for POCT1-A)
- citations: Page numbers where examples were found

Example output:
{{
  "message_type": "OBS",
  "examples": [
    {{
      "analyte_cd": "GLU",
      "result_val": 95.5,
      "result_unit": "mg/dL",
      "collection_dttm": "2021-01-15T10:30:45Z"
    }}
  ],
  "citations": ["p25", "Appendix A"]
}}

CRITICAL: Copy examples EXACTLY as they appear. Do not modify or generate synthetic examples."""

    @staticmethod
    def blueprint_consolidation(
        message_extractions: list[dict],
        device_name: str
    ) -> str:
        """Prompt for consolidating message extractions into final blueprint.
        
        Args:
            message_extractions: List of extracted message definitions
            device_name: Device identifier
            
        Returns:
            Formatted prompt
        """
        import json
        extractions_json = json.dumps(message_extractions, indent=2)
        
        return f"""You are creating a final POCT1-A device blueprint for {device_name}.

Extracted message definitions:
{extractions_json}

Your task: Consolidate these extractions into a complete device blueprint.

Return JSON with this structure:
{{
  "device_name": "{device_name}",
  "spec_version": "POCT1-A" or "POCT1-A2",
  "messages": [
    {{
      "message_type": "...",
      "direction": "...",
      "description": "...",
      "fields": [ /* field definitions */ ],
      "examples": [ /* example messages */ ],
      "citations": [ /* all citations */ ]
    }}
  ],
  "summary": {{
    "total_messages": 0,
    "core_messages": 0,
    "vendor_extensions": 0,
    "field_count": 0
  }}
}}

CRITICAL: Preserve ALL citations and field definitions. Do not drop any data."""

    @staticmethod
    def system_prompt() -> str:
        """System prompt for all POCT1-A extraction tasks.
        
        Returns:
            System prompt text
        """
        return """You are an expert in POCT1-A (Point-of-Care Testing) protocol specifications.

Your expertise includes:
- POCT1-A and POCT1-A2 standard message types (HELLO, OBS, RGT, DST, CONFG)
- Device-to-LIS interface specifications and bidirectional communication
- POCT1-A field patterns (_cd, _dttm, _dt, _tm, _id, _nm, _val, _unit)
- Analyte codes, result values, and quality control data
- Vendor-specific message extensions (Z-messages)

Requirements for ALL responses:
1. Extract information ONLY from provided context - never invent or assume
2. Include citations (page numbers, sections) for ALL extracted data
3. Return valid JSON with proper escaping
4. Preserve exact field names and message identifiers
5. Flag ambiguities or missing information explicitly
6. Use null for unknown values, never guess

Your output will be used to generate production code for medical device integration.
Accuracy and completeness are critical."""
