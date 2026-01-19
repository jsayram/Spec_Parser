# POCT1 Spec Parser - LLM Blueprint Generation

This document explains how the LLM generates Device Configuration Blueprints from corrected specification data. This is **NOT** a chatbot - the LLM produces structured JSON configuration that can be used to communicate with physical POCT devices over TCP.

For information about the correction system that prepares data for the LLM, see [CORRECTION_SYSTEM.md](./CORRECTION_SYSTEM.md).

---

## Table of Contents

1. [Overview](#overview)
2. [What the LLM Produces](#what-the-llm-produces)
3. [LLM Input Structure](#llm-input-structure)
4. [Blueprint Generation Pipeline](#blueprint-generation-pipeline)
5. [Example Blueprint](#example-blueprint)
6. [How the Blueprint Enables TCP Communication](#how-the-blueprint-enables-tcp-communication)
7. [Why Corrections Matter](#why-corrections-matter)
8. [Knowledge Stack](#knowledge-stack)
9. [Summary](#summary)

---

## Overview

The LLM's role in this system is to generate a **Device Configuration Blueprint** - a complete, structured JSON document that contains everything needed to communicate with a POCT device over TCP.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LLM OUTPUT: DEVICE BLUEPRINT                          │
└─────────────────────────────────────────────────────────────────────────┘

FROM: Corrected spec extraction (baseline.md, document.json, indices)

TO:   Complete device configuration including:
      ├─► All message types (HELLO, DST, OBS, ACK, CONFG, RGT, EOT, etc.)
      ├─► All field definitions per message
      ├─► Bidirectionality (Device→LIS and LIS→Device)
      ├─► Device configuration parameters
      └─► TCP communication protocol details

RESULT: Usable instrument configuration for TCP device connection
```

---

## What the LLM Produces

> **Important**: This is NOT a chatbot. The LLM generates a complete **Device Configuration Blueprint** - a structured output that can be used to configure and communicate with the physical device over TCP.

### The Goal: Executable Device Configuration

The blueprint is the final output of the spec parsing pipeline. It contains:

| Output | Description | Used For |
|--------|-------------|----------|
| **Device Metadata** | Vendor, model, protocol version | Device identification |
| **Communication Settings** | TCP port, encoding, timeouts, message framing | Connection establishment |
| **Message Definitions** | All POCT1-A messages, both directions | Message parsing/building |
| **Field Definitions** | Fields per message with types | Data extraction |
| **Field Mappings** | Common data element locations | Integration mapping |
| **Configuration Parameters** | Device settings and constraints | Device configuration |
| **Validation Rules** | Message/field validation | Data quality |

---

## LLM Input Structure

The LLM receives a structured prompt containing all corrected specification data:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LLM INPUT (After All Corrections)                     │
└─────────────────────────────────────────────────────────────────────────┘

The LLM receives a STRUCTURED PROMPT containing:

1. DEVICE METADATA
   ├─► Vendor: Monkey Labs
   ├─► Model: Device900x
   ├─► Protocol: POCT1-A
   └─► Spec Version: 1.0

2. MESSAGE INVENTORY (from message parser + corrections)
   ├─► Observation Messages: OBS, ZMKY
   ├─► QC Messages: QCN, ZBAN
   ├─► System Messages: HELLO, DST, ACK, EOT
   ├─► Configuration Messages: CONFG, RGT
   └─► Direction for each (Device→LIS or LIS→Device or Bidirectional)

3. FIELD SPECIFICATIONS (from table extraction + corrections)
   ├─► HELLO message fields (handshake)
   ├─► DST fields (device status)
   ├─► OBS fields (observation/result values)
   ├─► ACK fields (acknowledgment)
   └─► Vendor-specific message fields (ZMKY, ZBAN)

4. CONFIGURATION PARAMETERS (from spec extraction)
   ├─► Device settings
   ├─► Communication parameters
   ├─► Acknowledgment requirements
   └─► Timeout values

5. SAMPLE MESSAGES (from spec examples)
   ├─► Example OBS message
   ├─► Example HELLO handshake
   └─► ACK response formats
```

---

## Blueprint Generation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BLUEPRINT GENERATION PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────┘

STEP 1: GATHER ALL CORRECTED DATA
═════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  From Search Index (corrected):                                         │
│  ├─► All message definitions                                            │
│  ├─► All field specifications                                           │
│  ├─► Sample message examples                                            │
│  └─► Configuration parameters                                           │
│                                                                         │
│  From Message Parser Output:                                            │
│  ├─► Categorized messages (observation, qc, config, system)             │
│  ├─► Direction mapping (device→LIS, LIS→device)                         │
│  └─► Field optionality (required, optional, conditional)                │
│                                                                         │
│  From Corrections:                                                      │
│  ├─► Fixed categories                                                   │
│  ├─► Fixed field definitions                                            │
│  └─► Added vendor patterns                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
STEP 2: BUILD STRUCTURED PROMPT
═══════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│  PROMPT TO LLM                                                          │
│                                                                         │
│  SYSTEM:                                                                │
│  You are a POCT1-A integration expert. Generate a complete device       │
│  configuration blueprint from the following specification data.         │
│  Output must be valid JSON that can be used to configure a TCP          │
│  connection to communicate with this device.                            │
│                                                                         │
│  SPECIFICATION DATA:                                                    │
│  ─────────────────────────────────────────────────────────              │
│                                                                         │
│  ## Device Information                                                  │
│  Vendor: Monkey Labs                                                    │
│  Model: Device900x                                                      │
│  Protocol: POCT1-A v2.0                                                 │
│                                                                         │
│  ## Messages (Device → LIS)                                             │
│  ### HELLO - Device Identification                                      │
│  Direction: Bidirectional (handshake)                                   │
│  Trigger: Connection established                                        │
│  [Page 12]                                                              │
│                                                                         │
│  ### OBS - Observation Result                                           │
│  Direction: Device to LIS                                               │
│  Trigger: When test result is available                                 │
│  [Page 23]                                                              │
│                                                                         │
│  OBS Fields:                                                            │
│  | Field | Name | Type | Opt | Description |                            │
│  |-------|------|------|-----|-------------|                            │
│  | 1 | Sequence | SI | R | Message sequence number |                    │
│  | 2 | Patient ID | ST | R | Patient identifier |                       │
│  | 3 | Test Code | CE | R | Test/analyte code |                         │
│  | 4 | Result Value | varies | R | Result value |                       │
│  | 5 | Units | CE | O | Result units |                                  │
│  | 6 | Flag | ID | O | Abnormal flag |                                  │
│  [Page 45-52]                                                           │
│                                                                         │
│  ### DST - Device Status                                                │
│  [... similar structure ...]                                            │
│                                                                         │
│  ## Messages (LIS → Device)                                             │
│  ### ACK - Acknowledgment                                               │
│  [... similar structure ...]                                            │
│                                                                         │
│  ## Vendor-Specific Messages                                            │
│  ### ZMKY - Custom Result Format                                        │
│  [... Monkey Labs specific fields ...]                                  │
│                                                                         │
│  ## Device Configuration Parameters                                     │
│  [... settings from spec ...]                                           │
│                                                                         │
│  ## Sample Messages                                                     │
│  [... example message strings ...]                                      │
│                                                                         │
│  ─────────────────────────────────────────────────────────              │
│                                                                         │
│  TASK:                                                                  │
│  Generate a complete device configuration blueprint JSON that includes: │
│  1. All messages with full field definitions                            │
│  2. Bidirectional message mapping                                       │
│  3. Device configuration parameters                                     │
│  4. Field mappings for common data elements                             │
│  5. TCP communication settings                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
STEP 3: LLM GENERATES BLUEPRINT
═══════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  LLM processes the corrected specification data and generates:          │
│                                                                         │
│  device_blueprint.json                                                  │
│  ├─► device metadata                                                    │
│  ├─► communication settings                                             │
│  ├─► all messages (both directions)                                     │
│  ├─► all fields per message                                             │
│  ├─► field types, optionality, cardinality                              │
│  ├─► device configuration parameters                                    │
│  └─► field mappings for integration                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
STEP 4: USE FOR TCP CONNECTION
══════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  The blueprint is used by your integration software to:                 │
│                                                                         │
│  1. CONFIGURE TCP CONNECTION                                            │
│     ├─► Connect to device on specified port                             │
│     ├─► Set encoding, timeouts, retry logic                             │
│     └─► Establish POCT1-A handshake (HELLO exchange)                    │
│                                                                         │
│  2. PARSE INCOMING MESSAGES                                             │
│     ├─► Identify message type (OBS, DST, QCN, etc.)                     │
│     ├─► Parse fields according to blueprint                             │
│     ├─► Extract values by position                                      │
│     └─► Map to internal data structures                                 │
│                                                                         │
│  3. BUILD OUTGOING MESSAGES                                             │
│     ├─► Select message type based on action (ACK, REQ, CONFG)           │
│     ├─► Populate fields according to blueprint                          │
│     ├─► Format as POCT1-A message                                       │
│     └─► Send to device                                                  │
│                                                                         │
│  4. HANDLE DEVICE CONFIGURATION                                         │
│     ├─► Read current settings via CONFG messages                        │
│     ├─► Modify settings via configuration messages                      │
│     └─► Validate against allowed values                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Example Blueprint

This is an example of the JSON blueprint generated by the LLM for a hypothetical MonkeyDevice900x:

```json
{
  "blueprint_version": "1.0",
  "generated_from": "monkey_spec.pdf",
  "generation_timestamp": "2026-01-18T12:00:00Z",
  
  "device": {
    "vendor": "MonkeyLabs",
    "model": "Device900x",
    "protocol": "POCT1-A",
    "spec_version": "1.0",
    "device_class": "analyzer"
  },
  
  "communication": {
    "transport": "TCP",
    "default_port": 5000,
    "encoding": "UTF-8",
    "message_wrapper": {
      "start_block": "\u000b",
      "end_block": "\u001c\r",
      "field_separator": "|"
    },
    "ack_mode": "enhanced",
    "timeout_ms": 30000,
    "retry_count": 3,
    "keep_alive_interval_ms": 60000
  },
  
  "messages": {
    "device_to_lis": [
      {
        "id": "HELLO",
        "name": "Device Identification",
        "category": "system",
        "description": "Handshake message sent on connection",
        "citation": "[Page 12-15]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "HELLO"},
          {"seq": 2, "name": "device_id", "type": "ST", "opt": "R", "len": 20},
          {"seq": 3, "name": "vendor_name", "type": "ST", "opt": "R", "len": 50},
          {"seq": 4, "name": "model", "type": "ST", "opt": "R", "len": 30},
          {"seq": 5, "name": "serial_number", "type": "ST", "opt": "R", "len": 20},
          {"seq": 6, "name": "protocol_version", "type": "ST", "opt": "R", "len": 10}
        ]
      },
      {
        "id": "DST",
        "name": "Device Status",
        "category": "system",
        "description": "Device status notification",
        "citation": "[Page 18-20]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "DST"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "status_code", "type": "ID", "opt": "R", "values": ["READY", "BUSY", "ERROR", "MAINT"]},
          {"seq": 4, "name": "status_text", "type": "ST", "opt": "O", "len": 200},
          {"seq": 5, "name": "timestamp", "type": "TS", "opt": "R"}
        ]
      },
      {
        "id": "OBS",
        "name": "Observation Result",
        "category": "observation",
        "description": "Test result from device",
        "citation": "[Page 23-35]",
        "repeating": true,
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "OBS"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "patient_id", "type": "ST", "opt": "R", "len": 20},
          {"seq": 4, "name": "sample_id", "type": "ST", "opt": "O", "len": 20},
          {"seq": 5, "name": "test_code", "type": "CE", "opt": "R", "len": 50},
          {"seq": 6, "name": "test_name", "type": "ST", "opt": "O", "len": 100},
          {"seq": 7, "name": "result_value", "type": "varies", "opt": "R"},
          {"seq": 8, "name": "units", "type": "CE", "opt": "O", "len": 20},
          {"seq": 9, "name": "reference_range", "type": "ST", "opt": "O", "len": 60},
          {"seq": 10, "name": "abnormal_flag", "type": "ID", "opt": "O", "values": ["N", "L", "H", "LL", "HH"]},
          {"seq": 11, "name": "result_status", "type": "ID", "opt": "R", "values": ["F", "P", "C"]},
          {"seq": 12, "name": "timestamp", "type": "TS", "opt": "R"},
          {"seq": 13, "name": "operator_id", "type": "ST", "opt": "O", "len": 20}
        ]
      },
      {
        "id": "QCN",
        "name": "QC Notification",
        "category": "qc",
        "description": "Quality control test result",
        "citation": "[Page 45-52]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "QCN"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "qc_lot", "type": "ST", "opt": "R"},
          {"seq": 4, "name": "qc_level", "type": "ID", "opt": "R", "values": ["1", "2", "3"]},
          {"seq": 5, "name": "test_code", "type": "CE", "opt": "R"},
          {"seq": 6, "name": "result_value", "type": "NM", "opt": "R"},
          {"seq": 7, "name": "expected_range", "type": "ST", "opt": "R"},
          {"seq": 8, "name": "qc_status", "type": "ID", "opt": "R", "values": ["P", "F"]},
          {"seq": 9, "name": "timestamp", "type": "TS", "opt": "R"}
        ]
      },
      {
        "id": "RGT",
        "name": "Reagent Status",
        "category": "system",
        "description": "Reagent/consumable status",
        "citation": "[Page 60-65]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "RGT"},
          {"seq": 2, "name": "reagent_id", "type": "ST", "opt": "R"},
          {"seq": 3, "name": "reagent_name", "type": "ST", "opt": "O"},
          {"seq": 4, "name": "lot_number", "type": "ST", "opt": "R"},
          {"seq": 5, "name": "expiration_date", "type": "TS", "opt": "R"},
          {"seq": 6, "name": "remaining_tests", "type": "NM", "opt": "O"},
          {"seq": 7, "name": "status", "type": "ID", "opt": "R", "values": ["OK", "LOW", "EXPIRED", "EMPTY"]}
        ]
      },
      {
        "id": "EOT",
        "name": "End of Transaction",
        "category": "system",
        "description": "Marks end of message batch",
        "citation": "[Page 16]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "EOT"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "message_count", "type": "NM", "opt": "O"}
        ]
      },
      {
        "id": "ZMKY",
        "name": "Monkey Labs Custom Result",
        "category": "observation",
        "vendor_specific": true,
        "description": "Proprietary extended result format",
        "citation": "[Page 89-95]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "ZMKY"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "extended_result_type", "type": "ST", "opt": "R"},
          {"seq": 4, "name": "sensor_reading", "type": "NM", "opt": "R"},
          {"seq": 5, "name": "confidence_score", "type": "NM", "opt": "O"}
        ]
      },
      {
        "id": "ZBAN",
        "name": "Banana Sensor Calibration",
        "category": "qc",
        "vendor_specific": true,
        "description": "Sensor calibration data",
        "citation": "[Page 102-108]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "ZBAN"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "sensor_id", "type": "ST", "opt": "R"},
          {"seq": 4, "name": "calibration_value", "type": "NM", "opt": "R"},
          {"seq": 5, "name": "calibration_status", "type": "ID", "opt": "R", "values": ["P", "F"]}
        ]
      }
    ],
    
    "lis_to_device": [
      {
        "id": "HELLO",
        "name": "LIS Identification",
        "category": "system",
        "description": "LIS response to device HELLO",
        "citation": "[Page 12-15]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "HELLO"},
          {"seq": 2, "name": "lis_id", "type": "ST", "opt": "R", "len": 20},
          {"seq": 3, "name": "lis_name", "type": "ST", "opt": "R", "len": 50},
          {"seq": 4, "name": "facility", "type": "ST", "opt": "O", "len": 50},
          {"seq": 5, "name": "protocol_version", "type": "ST", "opt": "R", "len": 10}
        ]
      },
      {
        "id": "ACK",
        "name": "Acknowledgment",
        "category": "system",
        "description": "Message acknowledgment",
        "citation": "[Page 17]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "ACK"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R", "description": "Sequence of message being acknowledged"},
          {"seq": 3, "name": "ack_code", "type": "ID", "opt": "R", "values": ["OK", "ER", "RJ"]},
          {"seq": 4, "name": "error_text", "type": "ST", "opt": "O", "len": 200}
        ]
      },
      {
        "id": "REQ",
        "name": "Request",
        "category": "system",
        "description": "Request for data from device",
        "citation": "[Page 70-72]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "REQ"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "request_type", "type": "ID", "opt": "R", "values": ["STATUS", "CONFIG", "RESULTS", "PENDING"]},
          {"seq": 4, "name": "filter", "type": "ST", "opt": "O"}
        ]
      },
      {
        "id": "CONFG",
        "name": "Configuration Command",
        "category": "config",
        "description": "Device configuration command",
        "citation": "[Page 75-80]",
        "fields": [
          {"seq": 1, "name": "message_type", "type": "ST", "opt": "R", "value": "CONFG"},
          {"seq": 2, "name": "sequence", "type": "SI", "opt": "R"},
          {"seq": 3, "name": "action", "type": "ID", "opt": "R", "values": ["GET", "SET"]},
          {"seq": 4, "name": "parameter_name", "type": "ST", "opt": "R"},
          {"seq": 5, "name": "parameter_value", "type": "varies", "opt": "C", "description": "Required for SET action"}
        ]
      }
    ]
  },
  
  "device_configuration": {
    "readable_via": "CONFG (GET)",
    "writable_via": "CONFG (SET)",
    "parameters": [
      {
        "id": "auto_send_results",
        "name": "Auto-Send Results",
        "type": "boolean",
        "default": true,
        "description": "Automatically transmit results when available"
      },
      {
        "id": "qc_lockout",
        "name": "QC Lockout Enabled",
        "type": "boolean",
        "default": true,
        "description": "Require QC before patient testing"
      },
      {
        "id": "result_format",
        "name": "Result Format",
        "type": "enum",
        "options": ["standard", "extended", "zmky"],
        "default": "standard",
        "description": "Output message format for results"
      },
      {
        "id": "lis_host",
        "name": "LIS Host Address",
        "type": "string",
        "max_length": 64,
        "description": "IP address or hostname of LIS"
      },
      {
        "id": "lis_port",
        "name": "LIS Port",
        "type": "integer",
        "min": 1,
        "max": 65535,
        "default": 5000,
        "description": "TCP port for LIS connection"
      }
    ]
  },
  
  "field_mappings": {
    "description": "Common field locations for integration",
    "mappings": {
      "patient_id": {"message": "OBS", "field": 3},
      "sample_id": {"message": "OBS", "field": 4},
      "test_code": {"message": "OBS", "field": 5},
      "test_name": {"message": "OBS", "field": 6},
      "result_value": {"message": "OBS", "field": 7},
      "result_units": {"message": "OBS", "field": 8},
      "result_status": {"message": "OBS", "field": 11},
      "result_timestamp": {"message": "OBS", "field": 12},
      "device_status": {"message": "DST", "field": 3},
      "qc_status": {"message": "QCN", "field": 8}
    }
  },
  
  "validation_rules": [
    {
      "message": "OBS",
      "rule": "result_status in ['F', 'P', 'C']",
      "description": "Result status must be Final, Preliminary, or Corrected"
    },
    {
      "message": "QCN",
      "rule": "qc_status in ['P', 'F']",
      "description": "QC status must be Pass or Fail"
    },
    {
      "message": "ACK",
      "rule": "ack_code in ['OK', 'ER', 'RJ']",
      "description": "ACK code must be OK, Error, or Reject"
    }
  ]
}
```

---

## How the Blueprint Enables TCP Communication

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    USING THE BLUEPRINT FOR TCP                           │
└─────────────────────────────────────────────────────────────────────────┘

INTEGRATION SOFTWARE USES BLUEPRINT TO:

1. ESTABLISH CONNECTION (POCT1-A Protocol)
   ═════════════════════════════════════════
   
   blueprint.communication:
   ├─► transport: "TCP"
   ├─► port: 5000 (configurable)
   ├─► encoding: "UTF-8"
   └─► timeout_ms: 30000
   
   → Connect to device at configured address:port
   → POCT1-A handshake: Device sends HELLO, LIS responds with HELLO
   
   Example HELLO exchange:
   Device → LIS: HELLO|Device900x|MonkeyLabs|D9X-001234|1.0|...
   LIS → Device: HELLO|LIS_System|Hospital_LIS|MainLab|1.0|...
   

2. RECEIVE & PARSE DEVICE MESSAGES
   ════════════════════════════════
   
   POCT1-A Message Types from Device:
   ├─► HELLO  - Device identification and handshake
   ├─► DST    - Device Status (ready, busy, error)
   ├─► OBS    - Observation/Result data
   ├─► QCN    - Quality Control notification
   ├─► RGT    - Reagent/Consumable status
   ├─► EOT    - End of Transaction
   └─► ZMKY   - Vendor-specific (Monkey Labs)
   
   Device sends: OBS|1|Patient123|Sample456|GLU|Glucose|95|mg/dL|70-100|N|F|20260118120000|OP001
   
   Integration software:
   ├─► Identifies message type (OBS - field 1)
   ├─► Looks up blueprint.messages.device_to_lis["OBS"]
   ├─► Parses fields according to POCT1-A positions
   ├─► Extracts values using field_mappings
   └─► Returns structured data:
   
       {
         "message_type": "OBS",
         "sequence": 1,
         "patient_id": "Patient123",
         "sample_id": "Sample456",
         "test_code": "GLU",
         "test_name": "Glucose",
         "result_value": 95,
         "units": "mg/dL",
         "reference_range": "70-100",
         "abnormal_flag": "N",
         "result_status": "F",
         "timestamp": "20260118120000",
         "operator_id": "OP001"
       }
   

3. BUILD & SEND LIS MESSAGES
   ══════════════════════════
   
   POCT1-A Message Types to Device:
   ├─► HELLO - LIS identification response
   ├─► ACK   - Acknowledgment (accept/reject)
   ├─► REQ   - Request for data
   └─► CONFG - Configuration commands
   
   To send acknowledgment:
   ├─► Look up blueprint.messages.lis_to_device["ACK"]
   ├─► Build ACK message with sequence number
   └─► Send: ACK|1|OK|
   
   To reject a message:
   └─► Send: ACK|1|ER|Invalid patient ID|
   

4. CONFIGURE DEVICE
   ═════════════════
   
   To read device settings:
   ├─► Send: CONFG|1|GET|auto_send_results|
   ├─► Device responds: CONFG|1|GET|auto_send_results|true|
   └─► Parse CONFG fields per blueprint
   
   To modify settings:
   ├─► Build: CONFG|2|SET|result_format|extended|
   ├─► Validate against allowed parameters (blueprint.device_configuration)
   ├─► Send to device
   └─► Wait for ACK
```

---

## Why Corrections Matter

Corrections applied before LLM processing ensure accurate blueprint generation:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CORRECTIONS → ACCURATE BLUEPRINT                      │
└─────────────────────────────────────────────────────────────────────────┘

WITHOUT CORRECTIONS:
════════════════════

Original OCR: "0BS|1|Patient|G1ucose|95|..."
                ↓
Blueprint field: {"id": "0BS", "name": "G1ucose", ...}
                      ↑               ↑
                   Typo!           Typo!
                ↓
TCP Parser: FAILS to find "OBS" message type
            FAILS to match "Glucose" test code


WITH CORRECTIONS APPLIED:
═════════════════════════

OCR Correction: "0BS" → "OBS", "G1ucose" → "Glucose"
                ↓
Blueprint field: {"id": "OBS", "name": "Glucose", ...}
                ↓
TCP Parser: Successfully parses OBS messages ✓
            Successfully matches Glucose test ✓


THE CHAIN:
══════════

  PDF Spec
      │
      ▼
  Raw Extraction (with OCR errors)
      │
      ▼
  +Corrections Applied
      │
      ▼
  Corrected Data → LLM → Accurate Blueprint → Working TCP Integration
```

For details on how corrections work, see [CORRECTION_SYSTEM.md](./CORRECTION_SYSTEM.md).

---

## Knowledge Stack

The knowledge stack shows how data flows from raw extraction through to LLM processing:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE STACK FOR LLM                               │
└─────────────────────────────────────────────────────────────────────────┘

LAYER 4: LLM (Pre-trained, No Additional Training)
═══════════════════════════════════════════════════
┌───────────────────────────────────────────────────────────────────┐
│  GPT-4 / Claude / Llama (any LLM)                                 │
│                                                                   │
│  Pre-trained on general knowledge                                 │
│  + Your CONTEXT from search results                               │
│                                                                   │
│  The LLM itself is NOT trained on your data.                      │
│  It receives corrected context at query time (RAG pattern).       │
└───────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Retrieved chunks (corrected text)
                              │
LAYER 3: Search Index (Rebuilt with Corrections)
═══════════════════════════════════════════════════
┌───────────────────────────────────────────────────────────────────┐
│  FAISS (semantic search) + BM25 (keyword search)                  │
│                                                                   │
│  Contains: ALL text from device spec                              │
│  With: OCR errors FIXED (from global patterns)                    │
│  With: Categories CORRECT (from standards + vendor config)        │
│  With: CITATIONS preserved (page numbers, bboxes)                 │
│                                                                   │
│  Index is rebuilt when corrections are applied.                   │
└───────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Indexed from corrected content
                              │
LAYER 2: Corrected Content (Generated Outputs)
═══════════════════════════════════════════════════
┌───────────────────────────────────────────────────────────────────┐
│  baseline.md / master.md                                          │
│                                                                   │
│  Original text from document.json                                 │
│  + Global OCR corrections applied automatically                   │
│  + Standard category corrections applied automatically            │
│  + Vendor pattern corrections applied automatically               │
│  + Device-specific corrections applied (if any)                   │
│                                                                   │
│  This is what humans review and what gets indexed.                │
└───────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Corrections loaded from
                              │
LAYER 1: Accumulated Knowledge Base (Shared Corrections)
═══════════════════════════════════════════════════════════
┌───────────────────────────────────────────────────────────────────┐
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │ poct1_standards │  │ ocr_corrections │  │ vendor/         │   │
│  │ .json           │  │ .json           │  │ *.json          │   │
│  │                 │  │                 │  │                 │   │
│  │ From ALL prior  │  │ From ALL prior  │  │ Per-vendor      │   │
│  │ devices:        │  │ devices:        │  │ patterns:       │   │
│  │                 │  │                 │  │                 │   │
│  │ - OBS = obs     │  │ - ROl → R01     │  │ - roche.json    │   │
│  │ - QCN = qc      │  │ - 0BS → OBS     │  │ - abbott.json   │   │
│  │ - CONFG = config│  │ - l vs 1 vs I   │  │ - monkeylabs.json│  │
│  │ - DST = system  │  │                 │  │   (NEW!)        │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                   │
│  This knowledge was built up from prior device onboardings.       │
│  New devices benefit from ALL of it automatically.                │
└───────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Preserved unchanged
                              │
LAYER 0: Original Extraction (Immutable Audit Trail)
═══════════════════════════════════════════════════════════
┌───────────────────────────────────────────────────────────────────┐
│  document.json (per device)                                       │
│                                                                   │
│  Raw extraction from PDF - NEVER modified                         │
│  Includes all OCR errors, all raw text                            │
│  Used as source of truth for regeneration                         │
│  Preserved for audit and compliance                               │
└───────────────────────────────────────────────────────────────────┘
```

---

## Summary

### Key Points

1. **LLM generates device blueprints** - not a chatbot, produces structured JSON configuration
2. **Blueprint enables TCP communication** - all POCT1-A messages, fields, and protocol settings
3. **Bidirectional message support** - both Device→LIS and LIS→Device messages defined
4. **Device configuration included** - parameters, constraints, and validation rules
5. **Corrections ensure accuracy** - OCR errors and miscategorizations fixed before blueprint generation
6. **Citations preserved** - blueprint can reference original spec pages for verification

### POCT1-A Messages (Not HL7)

This system uses POCT1-A protocol messages, which are different from HL7:

| Message | Direction | Description |
|---------|-----------|-------------|
| HELLO | Bidirectional | Device/LIS identification handshake |
| DST | Device → LIS | Device status |
| OBS | Device → LIS | Observation/result data |
| QCN | Device → LIS | Quality control notification |
| RGT | Device → LIS | Reagent/consumable status |
| EOT | Device → LIS | End of transaction |
| ACK | LIS → Device | Acknowledgment |
| REQ | LIS → Device | Request for data |
| CONFG | Bidirectional | Configuration get/set |

**The blueprint is the complete specification needed to communicate with the device over TCP, extracted from the PDF and refined through human corrections.**

---

## Related Documentation

- [CORRECTION_SYSTEM.md](./CORRECTION_SYSTEM.md) - How corrections work and improve over time
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) - System architecture
- [PHASE2_DATA_WORKFLOW.md](./PHASE2_DATA_WORKFLOW.md) - Data pipeline details
- [QUICKSTART.md](../QUICKSTART.md) - Getting started guide
