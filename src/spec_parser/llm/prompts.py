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

POCT1-A core message types to look for:
- HELLO / HELLO.R01: Device discovery and initialization (bidirectional)
- OBS / OBS.R01: Observation results from device to LIS
- RGT / RGT.R01: Reagent information and lot tracking
- DST / DST.R01: Device status and error reporting
- CONFG / CONFG.R01: Configuration and settings
- ACK: Acknowledgment messages
- QCN: Quality control messages
- Vendor extensions: Messages starting with 'Z' (e.g., ZMKY, ZBAN, ZORD)

Common POCT1-A patterns to look for:
- "supported messages", "message type", "message structure"
- Tables listing POCT1-A message names (HELLO, OBS, RGT, DST, CONFG)
- Message flow diagrams showing Device→LIS or LIS→Device
- Protocol handshake descriptions
- Query/Response/Acknowledgment patterns

Context from specification:
{context}

Return a JSON array with ALL message types found. For each:
- message_type: The POCT1-A message identifier (e.g., "HELLO.R01", "OBS", "RGT")
- direction: "device_to_lis", "lis_to_device", or "bidirectional"
- description: Brief description from spec
- citations: Array of page numbers where found (e.g., ["p12", "p45"])

Example output:
[
  {{
    "message_type": "HELLO.R01",
    "direction": "bidirectional",
    "description": "Device discovery and initialization",
    "citations": ["p12", "p45"]
  }},
  {{
    "message_type": "OBS",
    "direction": "device_to_lis",
    "description": "Observation result message",
    "citations": ["p20"]
  }},
  {{
    "message_type": "RGT",
    "direction": "device_to_lis",
    "description": "Reagent lot information",
    "citations": ["p25"]
  }}
]

IMPORTANT: Extract ONLY POCT1-A message types. Do NOT include HL7 segment names (MSH, PID, OBR, OBX)."""

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

Extract ALL field definitions for this message. Look for POCT1-A field patterns:
- Field names with extensions: _cd, _dttm, _dt, _tm, _id, _nm, _val, _unit
- Analyte identifiers and types
- Enum values and allowed codes
- Field segments and hierarchies

For each field include:
- field_name: Field identifier (e.g., "analyte_cd", "result_val", "collection_dttm")
- field_description: What this field contains
- data_type: Data type (e.g., "string", "number", "datetime", "enum")
- optionality: "required", "optional", or "conditional"
- max_length: Maximum field length (if specified)
- allowed_values: Array of allowed values or codes (if enumerated)
- usage_notes: Any implementation notes or constraints
- citations: Page numbers or sections where field is defined

Return JSON array. Example:
[
  {{
    "field_name": "analyte_cd",
    "field_description": "Analyte code identifier",
    "data_type": "string",
    "optionality": "required",
    "max_length": 20,
    "allowed_values": ["GLU", "HbA1c", "CHOL"],
    "usage_notes": "Device-specific analyte codes",
    "citations": ["p15"]
  }},
  {{
    "field_name": "result_val",
    "field_description": "Numeric result value",
    "data_type": "number",
    "optionality": "required",
    "max_length": null,
    "allowed_values": [],
    "usage_notes": "Floating point, precision depends on analyte",
    "citations": ["p23"]
  }},
  {{
    "field_name": "collection_dttm",
    "field_description": "Sample collection date and time",
    "data_type": "datetime",
    "optionality": "optional",
    "max_length": null,
    "allowed_values": [],
    "usage_notes": "ISO 8601 format",
    "citations": ["p30"]
  }}
]

CRITICAL: Extract fields ONLY from the provided context. Include ALL citations."""

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
- HL7 v2.5.1 message structure and segments
- POCT1-A and POCT1-A2 standard message types
- Device interface specifications and LIS integration
- Field data types (ST, NM, CE, TS, HD, etc.)
- Vendor-specific message extensions

Requirements for ALL responses:
1. Extract information ONLY from provided context - never invent or assume
2. Include citations (page numbers, sections) for ALL extracted data
3. Return valid JSON with proper escaping
4. Preserve exact field names and message identifiers
5. Flag ambiguities or missing information explicitly
6. Use null for unknown values, never guess

Your output will be used to generate production code for medical device integration.
Accuracy and completeness are critical."""
