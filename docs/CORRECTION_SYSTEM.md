# POCT1 Spec Parser - Correction System Guide

This document explains how the correction system works, how to fix errors in extracted specifications, and how the system improves over time as more devices are onboarded.

For LLM blueprint generation (the step after corrections are applied), see [LLM_BLUEPRINT_GENERATION.md](./LLM_BLUEPRINT_GENERATION.md).

---

## Table of Contents

1. [Overview](#overview)
2. [How Extraction Works](#how-extraction-works)
3. [Types of Errors](#types-of-errors)
4. [Correction Scopes](#correction-scopes)
5. [How to Add Corrections](#how-to-add-corrections)
6. [Regeneration Pipeline](#regeneration-pipeline)
7. [How the System Improves Over Time](#how-the-system-improves-over-time)
8. [What the LLM Produces](#what-the-llm-produces) *(link to separate doc)*
9. [Future Devices](#future-monkey-labs-device-even-easier)
10. [File Structure Reference](#file-structure-reference)
11. [Command Reference](#command-reference)

---

## Overview

When you onboard a new POCT1 device, the system:

1. **Extracts** text, images, and tables from the PDF specification
2. **Parses** POCT1 message types and field definitions
3. **Indexes** content for semantic and keyword search
4. **Generates** human-readable reports for review

Sometimes the extraction has errors (OCR mistakes, parsing issues, miscategorization). The correction system allows humans to fix these errors while:

- **Preserving** the original extraction (audit trail)
- **Sharing** corrections across devices when applicable
- **Reducing** manual effort for future devices

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    THE BIG PICTURE                                       │
└─────────────────────────────────────────────────────────────────────────┘

   PDF Spec ───► Automated ───► Errors? ───► Human ───► Corrected
                 Extraction         │        Review      Output
                                    │                      │
                                    │                      ▼
                                    │               ┌──────────────┐
                                    │               │ Shared       │
                                    └───────────────│ Knowledge    │
                                                    │ Base         │
                                                    └──────────────┘
                                                           │
                                                           ▼
                                                    Future devices
                                                    benefit from
                                                    past corrections
```

---

## How Extraction Works

### Step 1: PDF Extraction
The system uses PyMuPDF to extract:
- **Text blocks** - Selectable text from the PDF
- **Images** - Diagrams, flowcharts, screenshots
- **Tables** - Structured data (field definitions, message formats)

### Step 2: OCR Processing
For images and non-selectable text:
- Tesseract OCR converts images to text
- Confidence scores track reliability
- Low-confidence results flagged for review

### Step 3: Message Parsing
The parser identifies:
- **Message types** (HELLO, DST, OBS, EOT, ACK, CONFG, RGT)
- **Field specifications** (observation codes, result values, device status fields)
- **Vendor extensions** (device-specific configuration messages)

### Step 4: Output Generation
The system creates:
- `document.json` - Machine-readable extraction (READ-ONLY)
- `baseline.md` - Human-readable report
- `master.md` - Full document in markdown
- Search indices (FAISS + BM25)

---

## Types of Errors

### 1. OCR Errors
**What**: Text recognition mistakes from images
**Example**: `"0BS.ROl"` instead of `"OBS.R01"`
**Cause**: Similar-looking characters (0/O, l/1/I)

### 2. Parsing Errors
**What**: Incorrect field extraction from tables
**Example**: Missing data type, wrong optionality
**Cause**: Unusual table formatting in PDF

### 3. Category Errors
**What**: Message assigned to wrong category
**Example**: QCN.R01 marked as "observation" instead of "qc"
**Cause**: Pattern matching limitations

### 4. Missing Content
**What**: Content not extracted at all
**Example**: Message definition skipped entirely
**Cause**: OCR failure, unusual formatting

### 5. Vendor Pattern Errors
**What**: Vendor-specific messages miscategorized
**Example**: ZCFG (Roche config) marked as unknown
**Cause**: Vendor prefix not in known patterns

---

## Correction Scopes

Not all corrections are equal. Some apply to one device, others to all devices.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CORRECTION SCOPE HIERARCHY                            │
└─────────────────────────────────────────────────────────────────────────┘

SCOPE              APPLIES TO                  EXAMPLE
─────              ──────────                  ───────

DEVICE-SPECIFIC    Only this one device        "Page 42 had a typo"
                   (unique to this PDF)

VENDOR-SPECIFIC    All devices from vendor     "Roche uses ZCFG prefix"
                   (Roche, Abbott, Quidel)

POCT1-STANDARD     ALL POCT1 devices           "QCN = Quality Control"
                   (universal truth)

OCR-GLOBAL         All future OCR              "ROl usually means R01"
                   (common OCR mistakes)
```

### When to Use Each Scope

| Correction Type | Scope | Why |
|-----------------|-------|-----|
| Page-specific typo | Device | Only this PDF has the error |
| Table parsing issue | Device | Unique table layout |
| Vendor Z-segment pattern | Vendor | All Roche devices use ZCFG |
| Message category (QCN=qc) | Standard | POCT1 defines this |
| Common OCR mistake (l→1) | Global | Happens in all PDFs |

---

## How to Add Corrections

### Correction Storage Structure

```
data/spec_output/{device}/
├── json/document.json            # Original extraction (NEVER MODIFIED)
├── markdown/master.md            # Generated (REGENERATED)
├── reports/baseline.md           # Generated (REGENERATED)
│
└── feedback/                     # Human corrections (ADDITIVE)
    ├── corrections.json          # Text corrections
    ├── field_overrides.json      # Field spec corrections
    ├── added_messages.json       # Missed messages
    ├── category_overrides.json   # Category corrections
    ├── manual_content.json       # Manually added content
    └── confirmations.json        # Human verified correct
```

### Shared Correction Storage

```
config/
├── poct1_standards.json          # POCT1 message categories (all devices)
├── ocr_corrections.json          # Common OCR error patterns (all devices)
└── vendor/
    ├── roche.json                # Roche-specific patterns
    ├── abbott.json               # Abbott-specific patterns
    └── quidel.json               # Quidel-specific patterns
```

### Example: Correcting an OCR Error

**Problem**: baseline.md shows `"0BS.ROl"` instead of `"OBS.R01"`

**Step 1**: Find the citation in the report
```markdown
OBS.R01 observation result message [^p42_ocr_001]
```

**Step 2**: Add correction
```bash
spec-parser feedback add \
    --device rochecobasliat \
    --type correction \
    --citation p42_ocr_001 \
    --original "0BS.ROl" \
    --corrected "OBS.R01" \
    --reason "OCR misread O as 0, 1 as l"
```

**Step 3**: Regenerate outputs
```bash
spec-parser device regenerate --device rochecobasliat
```

### Example: Correcting a Category Error

**Problem**: QCN.R01 categorized as "observation" instead of "qc"

**Decide scope**: Is QCN always quality control? Yes (POCT1 standard).

```bash
# Add to POCT1 standards (affects ALL devices)
spec-parser feedback add \
    --scope standard \
    --type category \
    --message "QCN" \
    --category "qc" \
    --reason "QCN is Quality Control Notification per POCT1-A spec"
```

### Example: Adding Vendor Pattern

**Problem**: Roche uses ZCFG for configuration, parser doesn't recognize it

```bash
# Add to Roche vendor config (affects all Roche devices)
spec-parser feedback add \
    --scope vendor \
    --vendor roche \
    --type pattern \
    --prefix "ZCFG" \
    --category "config" \
    --reason "Roche-specific configuration segment"
```

---

## Regeneration Pipeline

When you run `spec-parser device regenerate`, the system:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    REGENERATION FLOW                                     │
└─────────────────────────────────────────────────────────────────────────┘

         ┌──────────────────┐
         │  document.json   │ (Original extraction - UNCHANGED)
         └────────┬─────────┘
                  │
                  ▼
  ┌───────────────────────────────────┐
  │  LOAD ALL CORRECTIONS             │
  │                                   │
  │  Priority order:                  │
  │  1. Device feedback/*.json        │
  │  2. Vendor config/vendor/*.json   │
  │  3. Standard poct1_standards.json │
  │  4. Global ocr_corrections.json   │
  └───────────────────────────────────┘
                  │
                  ▼
  ┌───────────────────────────────────┐
  │  APPLY CORRECTIONS                │
  │                                   │
  │  For each block:                  │
  │  ├─► Apply text replacements      │
  │  ├─► Apply field overrides        │
  │  ├─► Inject manual content        │
  │  └─► Apply category overrides     │
  └───────────────────────────────────┘
                  │
                  ▼
  ┌───────────────────────────────────┐
  │  REGENERATE OUTPUTS               │
  │                                   │
  │  ├─► markdown/master.md (updated) │
  │  ├─► reports/baseline.md (fixed)  │
  │  └─► search/indices (rebuilt)     │
  └───────────────────────────────────┘
                  │
                  ▼
         ┌──────────────────┐
         │  CORRECTED       │
         │  baseline.md     │ ← Ready for use
         └──────────────────┘
```

### What Gets Modified

| File/Component | Modified? | How |
|----------------|-----------|-----|
| document.json | ❌ NEVER | Original preserved for audit |
| feedback/*.json | ✅ APPEND | Human corrections added |
| markdown/master.md | ✅ REGENERATED | Built with corrections |
| reports/baseline.md | ✅ REGENERATED | Built with corrections |
| search/faiss_index | ✅ REBUILT | Re-indexed with corrected text |
| search/bm25_index | ✅ REBUILT | Re-indexed with corrected text |

---

## How the System Improves Over Time

This is the key benefit: **each correction makes future devices easier**.

### The Learning Curve

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    HUMAN EFFORT OVER TIME                                │
└─────────────────────────────────────────────────────────────────────────┘

Device #    Corrections Needed    Knowledge Gained
────────    ──────────────────    ─────────────────────────────────────────
   1              50              First device - many unknowns
   2              30              Standard patterns now known
   3              20              Vendor patterns learned
   4              12              Most POCT1 concepts captured
   5               8              Mainly device-specific issues
   ...
  10               3              Only unique PDF problems remain


          Manual Corrections Required
     50  │████
         │████
     40  │████
         │████
     30  │████ ███
         │████ ███
     20  │████ ███ ██
         │████ ███ ██ █
     10  │████ ███ ██ █ █ █
         │████ ███ ██ █ █ █ █ █ █ █
      0  └─────────────────────────────
          1   2   3  4 5 6 7 8 9 10
                   Device #

```

### What Gets Learned

| After Device # | Knowledge Accumulated |
|----------------|----------------------|
| 1 | Basic POCT1 message types (OBS, QCN, OPL) |
| 2 | Common OCR error patterns (0/O, l/1/I) |
| 3 | First vendor patterns (e.g., Roche ZCFG) |
| 5 | Most POCT1 field definitions |
| 10 | Second vendor patterns, edge cases |
| 20+ | System nearly autonomous |

### Example: Correction Propagation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    HOW ONE CORRECTION HELPS ALL DEVICES                  │
└─────────────────────────────────────────────────────────────────────────┘

DAY 1: Onboard Roche Cobas Liat
───────────────────────────────
Parser categorizes QCN.R01 as "vendor_specific" (wrong!)
Human reviews: "No, QCN is quality control per POCT1 standard"
Human adds correction with scope=standard

    $ spec-parser feedback add --scope standard \
        --type category --message QCN --category qc

This updates: config/poct1_standards.json
              {
                "QCN": {
                  "category": "qc",
                  "description": "Quality Control Notification"
                }
              }


DAY 5: Onboard Abbott InfoHQ
────────────────────────────
Parser encounters QCN.R01 in Abbott specification
Checks poct1_standards.json FIRST (before pattern matching)
Finds: QCN = "qc"
Automatically categorizes correctly! ✅

    No human intervention needed.


DAY 10: Onboard Quidel Sofia
────────────────────────────
Parser encounters QCN.R01 in Quidel specification
Already knows QCN = "qc" from standards
Automatically correct! ✅

    No human intervention needed.


RESULT: 1 correction on Day 1 → saved work on Day 5, 10, and forever after
```

---

## File Structure Reference

### Device-Specific Files (per device)

```
data/spec_output/{device}/
│
├── json/
│   └── document.json           # Original extraction (READ-ONLY)
│
├── markdown/
│   └── master.md               # Full document markdown
│
├── reports/
│   └── baseline.md             # Human-readable summary
│
├── index/
│   ├── faiss_index.faiss       # Vector embeddings
│   ├── faiss_index.metadata.json
│   ├── bm25_index.bm25.pkl     # Keyword index
│   └── bm25_index.metadata.json
│
└── feedback/                   # Human corrections
    ├── corrections.json        # OCR/text fixes
    ├── field_overrides.json    # Field definition fixes
    ├── added_messages.json     # Manually added messages
    ├── category_overrides.json # Category reassignments
    ├── manual_content.json     # Manually transcribed content
    └── confirmations.json      # Verified correct items
```

### Shared Configuration Files

```
config/
│
├── poct1_standards.json        # Universal POCT1 definitions
│   {
│     "message_prefixes": {
│       "OBS": {"category": "observation", "description": "..."},
│       "QCN": {"category": "qc", "description": "..."},
│       "OPL": {"category": "config", "description": "..."}
│     }
│   }
│
├── ocr_corrections.json        # Global OCR error patterns
│   {
│     "patterns": [
│       {"error": "ROl", "correction": "R01"},
│       {"error": "0BS", "correction": "OBS"}
│     ]
│   }
│
└── vendor/
    ├── roche.json              # Roche-specific patterns
    ├── abbott.json             # Abbott-specific patterns
    └── quidel.json             # Quidel-specific patterns
```

---

## Command Reference

### Adding Corrections

```bash
# Device-specific OCR correction
spec-parser feedback add \
    --device {device_name} \
    --type correction \
    --citation {citation_id} \
    --original "{wrong_text}" \
    --corrected "{correct_text}" \
    --reason "{explanation}"

# Device-specific field override
spec-parser feedback add \
    --device {device_name} \
    --type field-override \
    --field-id "MSH-9" \
    --data-type "CM" \
    --optionality "R" \
    --cardinality "1..1" \
    --reason "{explanation}"

# Add missing message (device-specific)
spec-parser feedback add \
    --device {device_name} \
    --type message \
    --message-id "OPL.R01" \
    --direction "lis_to_device" \
    --category "config" \
    --page 87 \
    --reason "Parser missed this message"

# POCT1 standard category (affects ALL devices)
spec-parser feedback add \
    --scope standard \
    --type category \
    --message "QCN" \
    --category "qc" \
    --reason "POCT1-A defines QCN as Quality Control"

# Vendor pattern (affects all devices from vendor)
spec-parser feedback add \
    --scope vendor \
    --vendor roche \
    --type pattern \
    --prefix "ZCFG" \
    --category "config" \
    --reason "Roche configuration segment"

# Global OCR pattern (affects all future OCR)
spec-parser feedback add \
    --scope global \
    --type ocr-pattern \
    --pattern "ROl" \
    --replacement "R01" \
    --reason "Common OCR error: l vs 1"
```

### Confirming Correct Extractions

```bash
# Mark extraction as verified correct
spec-parser feedback confirm \
    --device {device_name} \
    --citation {citation_id}
```

### Regenerating Outputs

```bash
# Regenerate with all corrections applied
spec-parser device regenerate --device {device_name}

# Force full reindex even if only LOW impact changes
spec-parser device regenerate --device {device_name} --force-rebuild
```

### Viewing Current Corrections

```bash
# List all corrections for a device
spec-parser feedback list --device {device_name}

# List all standard corrections
spec-parser feedback list --scope standard

# List all vendor corrections
spec-parser feedback list --scope vendor --vendor roche
```

---

## Summary

| Concept | Description |
|---------|-------------|
| **Preservation** | Original extraction (document.json) never modified |
| **Scoped Corrections** | Device, Vendor, Standard, or Global scope |
| **Additive Feedback** | Corrections added, never deleted |
| **Automatic Application** | Regeneration applies all relevant corrections |
| **Knowledge Accumulation** | Standard/vendor corrections benefit all future devices |
| **Diminishing Effort** | Each device requires fewer manual corrections |

### The Key Insight

> **One human correction today can save work on every future device.**

When you identify that a correction is universal (POCT1 standard) or vendor-wide, adding it at the right scope means:
- The system "learns" without ML training
- Future devices benefit automatically
- Human effort decreases over time
- Knowledge is explicitly captured and auditable

---

## New Device Onboarding: Complete Workflow Example

This section walks through onboarding a completely new device from a new vendor, showing how accumulated knowledge applies automatically and what requires human review.

### Scenario: MonkeyDevice900x

```
CONTEXT:
- New vendor "Monkey Labs" (never seen before)
- Device uses standard POCT1 messages (OBS, QCN, OPL)
- Device has vendor-specific messages (ZMKY, ZBAN)
- You've already onboarded 10 devices from Roche/Abbott/Quidel
```

### Step 1: PDF Extraction

```bash
$ spec-parser device onboard \
    --vendor "MonkeyLabs" \
    --model "Device900x" \
    --device-name "Monkey Labs Device 900x" \
    --spec-version "1.0" \
    --spec-pdf "monkey_spec.pdf"
```

```
┌─────────────────────────────────────────────────────────────────────────┐
│  EXTRACTION PHASE                                                        │
└─────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  monkey_spec.pdf │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  PyMuPDF Extract │
                    │  + Tesseract OCR │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  document.json   │  (Raw extraction)
                    │  - 847 text blocks
                    │  - 42 OCR blocks
                    │  - 15 tables
                    └──────────────────┘
```

### Step 2: System Loads Accumulated Knowledge

Before parsing, the system automatically loads corrections from previous devices:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE LOADING PHASE                                                 │
└─────────────────────────────────────────────────────────────────────────┘

SYSTEM LOADS SHARED KNOWLEDGE:

┌─────────────────────────────────────┐
│  config/poct1_standards.json        │  ◄── From 10 previous devices
│                                     │
│  {                                  │
│    "OBS": {"category": "observation"},
│    "QCN": {"category": "qc"},       │  ◄── Learned from Roche Day 1
│    "OPL": {"category": "config"},   │
│    "ESR": {"category": "observation"}  ◄── Learned from Abbott
│  }                                  │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  config/ocr_corrections.json        │  ◄── Common OCR fixes
│                                     │
│  [                                  │
│    {"error": "ROl", "fix": "R01"},  │  ◄── Learned from many devices
│    {"error": "0BS", "fix": "OBS"},  │
│    {"error": "QCN.ROI", "fix": "QCN.R01"}
│  ]                                  │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  config/vendor/roche.json           │  ◄── Roche patterns (not applicable)
│  config/vendor/abbott.json          │  ◄── Abbott patterns (not applicable)
│  config/vendor/quidel.json          │  ◄── Quidel patterns (not applicable)
│                                     │
│  config/vendor/monkeylabs.json      │  ◄── DOES NOT EXIST YET!
└─────────────────────────────────────┘
```

### Step 3: Message Parsing (With Knowledge Applied)

The parser uses accumulated knowledge to categorize messages:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MESSAGE PARSING PHASE                                                   │
└─────────────────────────────────────────────────────────────────────────┘

Parser encounters messages in Monkey spec:

MESSAGE FOUND          LOOKUP RESULT                    CATEGORY ASSIGNED
─────────────          ─────────────                    ─────────────────
OBS.R01                ✓ In poct1_standards.json        → "observation" ✓
QCN.R01                ✓ In poct1_standards.json        → "qc" ✓
OPL.R01                ✓ In poct1_standards.json        → "config" ✓
ZMKY.R01               ✗ Not in standards               → "vendor_specific" (guess)
ZBAN.R01               ✗ Not in standards               → "vendor_specific" (guess)

┌──────────────────────────────────────────────────────────────────────┐
│  STANDARD MESSAGES: Automatically correct! ✓                         │
│  (Learned from Roche/Abbott/Quidel years ago)                        │
│                                                                      │
│  VENDOR MESSAGES: Need human review ⚠️                               │
│  (New vendor, unknown patterns)                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Step 4: Output Generation

```
┌─────────────────────────────────────────────────────────────────────────┐
│  OUTPUT GENERATION PHASE                                                 │
└─────────────────────────────────────────────────────────────────────────┘

OUTPUT FILES CREATED:

data/spec_output/monkeylabs_device900x/
├── json/document.json              # Raw extraction (never changes)
│
├── markdown/master.md              # Full document markdown
│   (OCR corrections already applied from ocr_corrections.json)
│
├── reports/baseline.md             # Human-readable report
│
└── index/
    ├── faiss_index.faiss           # Vector search
    └── bm25_index.bm25.pkl         # Keyword search
```

The generated `baseline.md` report shows:

```markdown
## Message Inventory

### Observation (1 message)
- OBS.R01 - Observation Result [^p23_text]  ← Correct! ✓

### Quality Control (1 message)
- QCN.R01 - QC Notification [^p45_text]     ← Correct! ✓

### Configuration (1 message)
- OPL.R01 - Option List [^p67_text]         ← Correct! ✓

### Vendor Specific (2 messages) ⚠️ REVIEW NEEDED
- ZMKY.R01 - Unknown [^p89_text]            ← Needs categorization
- ZBAN.R01 - Unknown [^p102_text]           ← Needs categorization
```

### Step 5: Human Reviews and Corrects

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HUMAN REVIEW PHASE                                                      │
└─────────────────────────────────────────────────────────────────────────┘

Human opens baseline.md and sees:

┌─────────────────────────────────────────────────────────────────────────┐
│  "Standard messages look correct! ✓                                     │
│   But what are ZMKY and ZBAN?                                           │
│                                                                         │
│   Looking at page 89... ZMKY is Monkey Labs' custom results format      │
│   Looking at page 102... ZBAN is Banana Sensor calibration data         │
│                                                                         │
│   ZMKY should be 'observation' (custom result wrapper)                  │
│   ZBAN should be 'qc' (calibration = quality control)"                  │
└─────────────────────────────────────────────────────────────────────────┘
```

Human decides these are vendor-specific (only Monkey Labs uses them):

```bash
# Add ZMKY pattern to Monkey Labs vendor config
$ spec-parser feedback add --scope vendor --vendor monkeylabs \
    --type pattern --prefix "ZMKY" --category "observation" \
    --reason "Monkey Labs custom result format"

# Add ZBAN pattern to Monkey Labs vendor config
$ spec-parser feedback add --scope vendor --vendor monkeylabs \
    --type pattern --prefix "ZBAN" --category "qc" \
    --reason "Banana sensor calibration data"
```

This creates a NEW file: `config/vendor/monkeylabs.json`

```json
{
  "vendor": "MonkeyLabs",
  "patterns": {
    "ZMKY": {
      "category": "observation",
      "description": "Monkey Labs custom result format"
    },
    "ZBAN": {
      "category": "qc",
      "description": "Banana sensor calibration data"
    }
  }
}
```

### Step 6: Regenerate with Corrections

```bash
$ spec-parser device regenerate --device monkeylabs_device900x
```

NOW `baseline.md` shows all messages correctly categorized:

```markdown
## Message Inventory

### Observation (2 messages)
- OBS.R01 - Observation Result [^p23_text]
- ZMKY.R01 - Custom Result Format [^p89_text]  ← Now correct!

### Quality Control (2 messages)
- QCN.R01 - QC Notification [^p45_text]
- ZBAN.R01 - Banana Sensor Calibration [^p102_text]  ← Now correct!

### Configuration (1 message)
- OPL.R01 - Option List [^p67_text]

### Vendor Specific (0 messages)  ← Empty now, all categorized!
```

---

## What the LLM Produces

Once all corrections are applied, the corrected data is passed to an LLM which generates a **Device Configuration Blueprint** - a structured JSON output containing all POCT1-A message definitions, field specifications, and TCP communication settings.

> **📄 See [LLM_BLUEPRINT_GENERATION.md](./LLM_BLUEPRINT_GENERATION.md) for complete documentation on:**
> - Blueprint structure and format
> - POCT1-A message definitions (HELLO, DST, OBS, ACK, CONFG, RGT, EOT)
> - TCP communication setup using the blueprint
> - Example device blueprint JSON
> - Knowledge stack for LLM processing

The blueprint is the final output that enables TCP communication with the physical device.

---

## Future Monkey Labs Device: Even Easier!

When Monkey Labs releases a new device model next year:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FUTURE: MonkeyDevice1000x (New Model, Same Vendor)                      │
└─────────────────────────────────────────────────────────────────────────┘

$ spec-parser device onboard --vendor "MonkeyLabs" --model "Device1000x" ...

WHAT HAPPENS AUTOMATICALLY:

1. POCT1 Standards Applied
   OBS.R01, QCN.R01, OPL.R01 → Correct categories ✓
   (Learned from Roche/Abbott/Quidel years ago)

2. OCR Corrections Applied
   "ROl" → "R01", "0BS" → "OBS" ✓
   (Learned from all prior devices)

3. Vendor Patterns Applied
   ZMKY.R01 → "observation" ✓
   ZBAN.R01 → "qc" ✓
   (Learned from MonkeyDevice900x!)    ◄── FROM PREVIOUS MONKEY DEVICE!

HUMAN REVIEW FINDS:
- New message ZNUT.R01 (Nutrition sensor, new feature in 1000x)
- Only needs to categorize this ONE new message!

$ spec-parser feedback add --scope vendor --vendor monkeylabs \
    --type pattern --prefix "ZNUT" --category "observation" \
    --reason "Nutrition sensor results (new in Device1000x)"

RESULT: 1 correction instead of 5!
        (4 messages already known from Device900x)
```

### Correction Count Comparison

| Device | Corrections Needed | Why |
|--------|-------------------|-----|
| MonkeyDevice900x (first Monkey Labs) | 2 | ZMKY, ZBAN unknown |
| MonkeyDevice1000x (second Monkey Labs) | 1 | Only new ZNUT unknown |
| MonkeyDevice2000x (third Monkey Labs) | 0-1 | All patterns likely known |

---

## Connection to System Corrections

### Where Corrections Come From

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CORRECTION SOURCE DIAGRAM                             │
└─────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │   NEW DEVICE    │
                         │   ONBOARDED     │
                         └────────┬────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  LOAD EXISTING          │
                    │  CORRECTIONS            │
                    └─────────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            ▼                     ▼                     ▼
    ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
    │   POCT1       │    │   OCR         │    │   VENDOR      │
    │   STANDARDS   │    │   PATTERNS    │    │   PATTERNS    │
    │               │    │               │    │               │
    │ All devices   │    │ All devices   │    │ Same vendor   │
    │ share this    │    │ share this    │    │ devices share │
    └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  APPLY TO EXTRACTION    │
                    │  BEFORE PARSING         │
                    └─────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  HUMAN REVIEWS          │
                    │  REMAINING ISSUES       │
                    └─────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
            ┌───────────────┐           ┌───────────────┐
            │ DEVICE-ONLY   │           │ SHARED        │
            │ CORRECTION    │           │ CORRECTION    │
            │               │           │               │
            │ feedback/     │           │ config/       │
            │ *.json        │           │ *.json        │
            └───────────────┘           └───────────────┘
                    │                           │
                    │                           │
                    ▼                           ▼
            Affects only             Affects all future
            this device              devices (or vendor)
```

### Correction Priority Order

When multiple corrections could apply, the system uses this priority:

```
PRIORITY    SOURCE                          WINS WHEN CONFLICT
────────    ──────                          ──────────────────
1 (HIGH)    Device feedback/*.json          Device-specific override
2           Vendor config/vendor/*.json     Vendor-wide pattern
3           Standard poct1_standards.json   Universal POCT1 rule
4 (LOW)     Global ocr_corrections.json     Fallback OCR fix
```

### Example: Conflict Resolution

```
SCENARIO: Message "ZCFG.R01" found in Roche spec

CHECK 1: Device feedback/category_overrides.json
         → Not found

CHECK 2: Vendor config/vendor/roche.json
         → Found! ZCFG = "config"
         → USE THIS ✓

CHECK 3: Standard poct1_standards.json
         → (not checked, already found in vendor)

CHECK 4: Global patterns
         → (not checked, already found)

RESULT: ZCFG.R01 categorized as "config" (from Roche vendor patterns)
```

---

## Summary: What You Need to Know

### For New Users

1. **The system learns from every device** - corrections you make today help future devices
2. **Choose the right scope** - standard (all devices), vendor (same manufacturer), or device (this PDF only)
3. **Review baseline.md** - this is your checklist of what needs verification
4. **LLM gets clean data** - by the time the LLM generates the blueprint, all corrections are applied

### For System Administrators

1. **document.json is sacred** - never modify the original extraction
2. **Shared configs are powerful** - one change to `poct1_standards.json` affects all devices
3. **Vendor configs reduce work** - capture vendor patterns once, reuse forever
4. **Regeneration is safe** - outputs can always be rebuilt from document.json + corrections

### For Blueprint Generation (LLM)

1. **LLM generates device blueprints** - not a chatbot, produces structured JSON configuration
2. **Blueprint enables TCP communication** - all messages, fields, and protocol settings
3. **Bidirectional message support** - both Device→LIS and LIS→Device messages defined
4. **Device configuration included** - parameters, constraints, and validation rules
5. **Corrections ensure accuracy** - OCR errors and miscategorizations fixed before blueprint generation
6. **Citations preserved** - blueprint can reference original spec pages for verification

---

## Questions?

For technical details, see:
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) - System architecture
- [PHASE2_DATA_WORKFLOW.md](./PHASE2_DATA_WORKFLOW.md) - Data pipeline details
- [QUICKSTART.md](../QUICKSTART.md) - Getting started guide
