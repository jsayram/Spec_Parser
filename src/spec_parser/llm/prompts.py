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

POCT1-A message types include:
- Core messages: HELLO, DST, OBS, QCN, RGT, EOT, ACK, REQ, CONFG
- HL7-based: OBS.R01, OBS.R03, QCN.J01, OPL.O21, etc.
- Vendor-specific: Messages starting with 'Z' (e.g., ZMKY, ZBAN)

Context from specification:
{context}

Return a JSON array of message types found. For each message include:
- message_type: The message identifier (e.g., "OBS.R01", "HELLO", "ZMKY")
- direction: "device_to_lis", "lis_to_device", or "bidirectional"
- description: Brief description from spec
- citations: Array of page numbers or section references where this message was found

Example output:
[
  {{
    "message_type": "OBS.R01",
    "direction": "device_to_lis",
    "description": "Observation result message for patient tests",
    "citations": ["p12", "p45"]
  }},
  {{
    "message_type": "HELLO",
    "direction": "bidirectional",
    "description": "Device discovery and initialization",
    "citations": ["p8"]
  }}
]

CRITICAL: Only extract messages explicitly mentioned in the specification. Do not invent or assume messages."""

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

Extract ALL field definitions for this message. For each field include:
- field_name: Field identifier (e.g., "MSH-7", "OBX-3", "PID-5")
- field_description: What this field contains
- data_type: Data type (e.g., "ST", "NM", "CE", "TS", "HD")
- optionality: "required", "optional", or "conditional"
- max_length: Maximum field length (if specified)
- allowed_values: Array of allowed values or codes (if enumerated)
- usage_notes: Any implementation notes or constraints
- citations: Page numbers or sections where field is defined

Return JSON array. Example:
[
  {{
    "field_name": "MSH-7",
    "field_description": "Date/Time of Message",
    "data_type": "TS",
    "optionality": "required",
    "max_length": null,
    "allowed_values": [],
    "usage_notes": "Format: YYYYMMDDHHmmss",
    "citations": ["p15"]
  }},
  {{
    "field_name": "OBX-3",
    "field_description": "Observation Identifier",
    "data_type": "CE",
    "optionality": "required",
    "max_length": 250,
    "allowed_values": ["GLU^Glucose", "HbA1c^Hemoglobin A1c"],
    "usage_notes": "LOINC codes preferred",
    "citations": ["p23", "p67"]
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
- examples: Array of example message strings (exactly as shown in spec)
- citations: Page numbers where examples were found

Example output:
{{
  "message_type": "OBS.R01",
  "examples": [
    "MSH|^~\\&|Sofia|Quidel||||20210115103045||OBS^R01|12345|P|2.5.1",
    "PID|||P123456||Doe^John^A||19800101|M"
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
