# POCT1 Spec Parser - Blueprint Code Generation

This document explains how the Device Blueprint serves as a universal source of truth that can generate device drivers, services, and integrations in **any language** for **any target system**.

For how blueprints are generated, see [LLM_BLUEPRINT_GENERATION.md](./LLM_BLUEPRINT_GENERATION.md).
For the correction system that prepares data, see [CORRECTION_SYSTEM.md](./CORRECTION_SYSTEM.md).

---

## Table of Contents

1. [Overview](#overview)
2. [Blueprint as Universal Adapter](#blueprint-as-universal-adapter)
3. [Target System Generation](#target-system-generation)
4. [Integration with RALS and AegisPOC](#integration-with-rals-and-aegispoc)
5. [Analyte Auto-Discovery](#analyte-auto-discovery)
6. [Device Configuration GUI](#device-configuration-gui)
7. [Code Generation Pipeline](#code-generation-pipeline)
8. [Example Generated Code](#example-generated-code)
9. [Benefits](#benefits)
10. [Complete Workflow](#complete-workflow)

---

## Overview

The Device Blueprint is a **language-agnostic JSON specification** that completely describes a POCT device's communication protocol, messages, analytes, and configuration options. From this single source of truth, we can generate:

- **Device drivers** in any programming language
- **API endpoints** for any backend framework
- **UI components** for any frontend framework
- **Test harnesses** and simulators
- **Documentation** and API specs

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PDF → BLUEPRINT → EVERYTHING                          │
└─────────────────────────────────────────────────────────────────────────┘

  PDF Spec                    Device Blueprint              Generated Outputs
  ─────────                   ────────────────              ─────────────────
  ┌─────────┐                 ┌─────────────┐               ┌─────────────────┐
  │ Vendor  │  ──► Parse ──►  │   JSON      │  ──► LLM ──► │ C# Driver       │
  │ Spec    │      + LLM      │  Blueprint  │     Code     │ TypeScript Svc  │
  │ (PDF)   │                 │             │     Gen      │ Python Handler  │
  └─────────┘                 │ • Messages  │              │ Java Client     │
                              │ • Fields    │              │ Go Service      │
                              │ • Analytes  │              │ API Endpoints   │
                              │ • Settings  │              │ UI Components   │
                              │ • Protocol  │              │ Test Harness    │
                              └─────────────┘              └─────────────────┘
```

---

## Blueprint as Universal Adapter

The Blueprint acts as a **Device Interface Definition Language (IDL)** - similar to how Protocol Buffers (`.proto`) or OpenAPI specs generate code for any language, the Blueprint generates device drivers for any system.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ONE BLUEPRINT → ANY OUTPUT                            │
└─────────────────────────────────────────────────────────────────────────┘

                          device_blueprint.json
                          (Language-Agnostic)
                                   │
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │  AegisPOC   │         │    RALS     │         │   Other     │
    │             │         │             │         │             │
    │  C# Driver  │         │  TypeScript │         │  Python     │
    │  .cs file   │         │  + C# API   │         │  Java       │
    │             │         │  .ts + .cs  │         │  Go         │
    └─────────────┘         └─────────────┘         └─────────────┘
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │ Drop into   │         │ Drop into   │         │ Any future  │
    │ AegisPOC    │         │ RALS        │         │ system      │
    │ project     │         │ project     │         │             │
    └─────────────┘         └─────────────┘         └─────────────┘
```

### Comparison to Other IDLs

| Technology | Source | Generates |
|------------|--------|-----------|
| Protocol Buffers | `.proto` file | Serializers in any language |
| OpenAPI | `openapi.yaml` | API clients in any language |
| GraphQL | `.graphql` schema | Typed clients in any language |
| **Device Blueprint** | `.json` blueprint | Device drivers in any language |

---

## Target System Generation

### AegisPOC (C#)

```
TARGET: AegisPOC (C#)
═════════════════════
LLM Prompt: "Generate C# device driver class from this blueprint"

Output:
├─► MonkeyDevice900xDriver.cs      (Main driver class)
├─► MonkeyDevice900xMessages.cs    (Message type definitions)
├─► MonkeyDevice900xAnalytes.cs    (Analyte mappings)
└─► MonkeyDevice900xSettings.cs    (Configuration schema)
```

### RALS (Angular + C# API)

```
TARGET: RALS (Angular + C# API)
═══════════════════════════════
LLM Prompt: "Generate TypeScript service + C# API controller from this blueprint"

Output:
├─► Frontend (Angular/TypeScript):
│   ├─► monkey-device.service.ts       (Device communication)
│   ├─► monkey-device.model.ts         (Message interfaces)
│   ├─► monkey-device-config.component.ts  (Settings UI)
│   └─► monkey-device-monitor.component.ts (Live data view)
│
└─► Backend (C# API):
    ├─► MonkeyDeviceController.cs      (REST endpoints)
    ├─► MonkeyDeviceParser.cs          (Message parsing)
    └─► MonkeyDeviceHub.cs             (SignalR for real-time)
```

### Future Systems

```
TARGET: Future System (Python/FastAPI)
══════════════════════════════════════
LLM Prompt: "Generate Python device handler from this blueprint"

Output:
├─► monkey_device_driver.py        (Async TCP handler)
├─► monkey_device_models.py        (Pydantic models)
└─► monkey_device_api.py           (FastAPI endpoints)
```

### All Outputs from One Blueprint

For a single device (e.g., MonkeyDevice900x), one blueprint generates:

| System | Files Generated | Purpose |
|--------|-----------------|---------|
| **AegisPOC** | `MonkeyDevice900xDriver.cs` | Full C# driver |
| **RALS Frontend** | `monkey-device.service.ts`, `monkey-device.model.ts` | Angular integration |
| **RALS Backend** | `MonkeyDeviceController.cs`, `MonkeyDeviceHub.cs` | API + WebSocket |
| **Test Harness** | `monkey_device_simulator.py` | Python device simulator |
| **Documentation** | `MonkeyDevice900x.md` | Auto-generated docs |
| **Postman Collection** | `monkey-device-api.json` | API testing |

---

## Integration with RALS and AegisPOC

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│           BLUEPRINT → DEVICE DRIVER FOR RALS/AegisPOC                   │
└─────────────────────────────────────────────────────────────────────────┘

                                                    EXISTING INFRASTRUCTURE
                                                    ═══════════════════════
  ┌─────────┐     ┌─────────────┐     ┌──────────────────────────────────────┐
  │  PDF    │     │  Blueprint  │     │  RALS / AegisPOC                     │
  │  Spec   │────►│   (JSON)    │     │                                      │
  └─────────┘     └──────┬──────┘     │  ┌──────────────────────────────┐   │
                         │            │  │ Device Configuration Engine  │   │
                         ▼            │  │                              │   │
                  ┌─────────────┐     │  │  • Analyte mappings         │   │
                  │  LLM Code   │     │  │  • Result processing        │   │
                  │  Generator  │     │  │  • QC/QA handling           │   │
                  └──────┬──────┘     │  │  • Reagent tracking         │   │
                         │            │  │  • Patient results          │   │
                         ▼            │  │  • Linearity validation     │   │
              ┌────────────────────┐  │  └──────────────────────────────┘   │
              │ MonkeyDevice900x   │  │                 ▲                   │
              │ DeviceDriver.cs    │──┼─────────────────┘                   │
              │                    │  │  DROP-IN                            │
              │ (Generated)        │  │  INTEGRATION                        │
              └────────────────────┘  │                                      │
                                      └──────────────────────────────────────┘
```

### What the Generated Driver Provides

The generated driver is a **drop-in component** that plugs into RALS/AegisPOC's existing device configuration engine:

| Feature | Description |
|---------|-------------|
| **Message Parsing** | Parse all incoming POCT1-A messages (OBS, QCN, DST, etc.) |
| **Message Building** | Construct outgoing messages (ACK, REQ, CONFG) |
| **Analyte Mappings** | Map device analyte codes to system codes (LOINC) |
| **Result Processing** | Handle patient results, QC, linearity, QA |
| **Reagent Tracking** | Parse reagent status and expiration |
| **Device Settings** | Expose configurable settings for the GUI |
| **Connection Handling** | TCP connection with proper POCT1-A handshake |

---

## Analyte Auto-Discovery

One of the most powerful features is automatic discovery of new analytes not yet in the system.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ANALYTE AUTO-DISCOVERY FLOW                           │
└─────────────────────────────────────────────────────────────────────────┘

  Blueprint Extraction                    System Integration
  ════════════════════                    ═══════════════════

  PDF Spec lists analytes:               RALS/AegisPOC has:
  ├─► GLU (Glucose)                      ├─► GLU → LOINC 2345-7 ✓
  ├─► LAC (Lactate)                      ├─► LAC → LOINC 2518-5 ✓
  ├─► BANA (Banana Sensor)   ◄── NEW!    ├─► BANA → ??? (NOT FOUND)
  └─► MNKY (Monkey Factor)   ◄── NEW!    └─► MNKY → ??? (NOT FOUND)

                      │
                      ▼
        ┌─────────────────────────────┐
        │  GENERATED DRIVER MARKS:    │
        │                             │
        │  • GLU, LAC = Mapped        │
        │  • BANA, MNKY = New         │
        │    (Flagged for review)     │
        └─────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  ADMIN NOTIFICATION:        │
        │                             │
        │  "New analytes found:       │
        │   BANA - Banana Sensor      │
        │   MNKY - Monkey Factor      │
        │                             │
        │   Please map to LOINC or    │
        │   create new analyte codes" │
        └─────────────────────────────┘
```

### Analyte Mapping in Generated Code

```csharp
// Generated from blueprint - analyte mappings
public static readonly Dictionary<string, AnalyteMapping> AnalyteMappings = new()
{
    // Known analytes - mapped to system codes
    ["GLU"] = new AnalyteMapping("GLU", "Glucose", "2345-7", KnownStatus.Mapped),
    ["LAC"] = new AnalyteMapping("LAC", "Lactate", "2518-5", KnownStatus.Mapped),
    ["NA"]  = new AnalyteMapping("NA", "Sodium", "2947-0", KnownStatus.Mapped),
    ["K"]   = new AnalyteMapping("K", "Potassium", "2823-3", KnownStatus.Mapped),
    
    // NEW: Auto-discovered from blueprint, needs review
    ["BANA"] = new AnalyteMapping("BANA", "Banana Sensor", null, KnownStatus.New),
    ["MNKY"] = new AnalyteMapping("MNKY", "Monkey Factor", null, KnownStatus.New),
};
```

---

## Device Configuration GUI

The generated driver provides data that powers a **standardized device configuration GUI** in RALS/AegisPOC.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STANDARDIZED DEVICE CONFIGURATION GUI                 │
└─────────────────────────────────────────────────────────────────────────┘

  RALS/AegisPOC provides the GUI framework.
  The generated driver provides the DATA.

  ┌─────────────────────────────────────────────────────────────────────┐
  │  Device Configuration: MonkeyLabs Device900x                        │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  Connection                                                         │
  │  ──────────                                                         │
  │  IP Address:  [192.168.1.100    ]     Port: [5000]                 │
  │  Status:      ● Connected                                          │
  │                                                                     │
  │  Settings (from driver.ConfigurableSettings)                        │
  │  ────────────────────────────────────────────                       │
  │  [✓] Auto-Send Results                                              │
  │  [✓] QC Lockout Enabled                                             │
  │  Result Format: [Standard     ▼]                                    │
  │                                                                     │
  │  Analyte Mappings (from driver.AnalyteMappings)                     │
  │  ───────────────────────────────────────────────                    │
  │  Device Code  │ Device Name      │ System Code │ Status            │
  │  ─────────────┼──────────────────┼─────────────┼─────────          │
  │  GLU          │ Glucose          │ 2345-7      │ ✓ Mapped          │
  │  LAC          │ Lactate          │ 2518-5      │ ✓ Mapped          │
  │  BANA         │ Banana Sensor    │ [____]      │ ⚠ NEW - Map Now   │
  │  MNKY         │ Monkey Factor    │ [____]      │ ⚠ NEW - Map Now   │
  │                                                                     │
  │  [Save Configuration]  [Test Connection]  [View Live Data]          │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```

### Settings Schema in Generated Code

```csharp
// Generated from blueprint - configurable settings
public static readonly DeviceSettings[] ConfigurableSettings = new[]
{
    new DeviceSetting("auto_send_results", "Auto-Send Results", 
        SettingType.Boolean, defaultValue: true),
    new DeviceSetting("qc_lockout", "QC Lockout Enabled", 
        SettingType.Boolean, defaultValue: true),
    new DeviceSetting("result_format", "Result Format", 
        SettingType.Enum, defaultValue: "standard", 
        options: new[] { "standard", "extended", "zmky" }),
    new DeviceSetting("lis_port", "LIS Port", 
        SettingType.Integer, defaultValue: 5000, min: 1, max: 65535),
};
```

---

## Code Generation Pipeline

### LLM Prompt Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LLM CODE GENERATION PROMPT                            │
└─────────────────────────────────────────────────────────────────────────┘

SYSTEM: You are a code generator for medical device integration.

INPUT:
  1. Device Blueprint (JSON) - Complete device specification
  2. Target System: "RALS" 
  3. Target Languages: ["TypeScript", "C#"]
  4. Framework: "Angular 17 + .NET 8 API"
  5. Integration Pattern: "REST + SignalR WebSocket"

TASK:
  Generate all necessary files for integrating this device into RALS.
  Follow RALS coding conventions and existing patterns.
  Include:
    - TypeScript service for Angular frontend
    - TypeScript interfaces for type safety
    - C# API controller for backend
    - C# message parser
    - SignalR hub for real-time device data

OUTPUT FORMAT:
  Return as JSON with file paths and contents:
  {
    "files": [
      {"path": "src/app/devices/monkey-device/...", "content": "..."},
      {"path": "Controllers/MonkeyDeviceController.cs", "content": "..."}
    ]
  }
```

### Multi-Stage Pipeline

```
STAGE 1: Parse PDF → Blueprint
══════════════════════════════
Input:  PDF Spec + Corrections
Output: device_blueprint.json
LLM:    "Extract all messages, fields, protocol details"


STAGE 2: Blueprint → Code Generation
═════════════════════════════════════
Input:  device_blueprint.json + Target Language/Framework
Output: Device driver files (.cs, .ts, .py, etc.)
LLM:    "Generate code that parses these messages for [target system]"


STAGE 3: Blueprint → Integration Adapter (Optional)
═══════════════════════════════════════════════════
Input:  device_blueprint.json + POCC API Spec (AegisPOC/RALS)
Output: integration_adapter (translates device format to POCC format)
LLM:    "Generate adapter that transforms POCT1-A to POCC API format"
```

---

## Example Generated Code

### C# Driver (for AegisPOC)

```csharp
// AUTO-GENERATED FROM BLUEPRINT: monkey_device_900x_blueprint.json
// Generated: 2026-01-18
// Spec Version: 1.0
// DO NOT MANUALLY EDIT - Regenerate from blueprint

namespace AegisPOC.DeviceDrivers.MonkeyLabs
{
    [DeviceDriver("MonkeyLabs", "Device900x", "POCT1-A")]
    public class MonkeyDevice900xDriver : IDeviceDriver
    {
        // ═══════════════════════════════════════════════════════════════
        // DEVICE METADATA (from blueprint.device)
        // ═══════════════════════════════════════════════════════════════
        public string VendorName => "MonkeyLabs";
        public string ModelName => "Device900x";
        public string Protocol => "POCT1-A";
        public string DriverVersion => "1.0.0";
        
        // ═══════════════════════════════════════════════════════════════
        // COMMUNICATION SETTINGS (from blueprint.communication)
        // ═══════════════════════════════════════════════════════════════
        public int DefaultPort => 5000;
        public string Encoding => "UTF-8";
        public int TimeoutMs => 30000;
        public string StartBlock => "\x0B";
        public string EndBlock => "\x1C\r";
        
        // ═══════════════════════════════════════════════════════════════
        // MESSAGE PARSERS (from blueprint.messages)
        // ═══════════════════════════════════════════════════════════════
        
        public DeviceMessage ParseMessage(string rawMessage)
        {
            var fields = rawMessage.Split('|');
            var messageType = fields[0];
            
            return messageType switch
            {
                "HELLO" => ParseHello(fields),
                "DST"   => ParseDeviceStatus(fields),
                "OBS"   => ParseObservation(fields),
                "QCN"   => ParseQCNotification(fields),
                "RGT"   => ParseReagentStatus(fields),
                "EOT"   => ParseEndOfTransaction(fields),
                "ZMKY"  => ParseVendorZMKY(fields),  // Vendor-specific
                "ZBAN"  => ParseVendorZBAN(fields),  // Vendor-specific
                _ => throw new UnknownMessageTypeException(messageType)
            };
        }
        
        private ObservationResult ParseObservation(string[] fields)
        {
            // Field positions from blueprint.messages["OBS"].fields
            return new ObservationResult
            {
                Sequence = int.Parse(fields[1]),
                PatientId = fields[2],
                SampleId = fields[3],
                AnalyteCode = fields[4],
                AnalyteName = fields[5],
                ResultValue = decimal.Parse(fields[6]),
                Units = fields[7],
                ReferenceRange = fields[8],
                AbnormalFlag = ParseFlag(fields[9]),
                ResultStatus = ParseStatus(fields[10]),
                Timestamp = ParseTimestamp(fields[11]),
                OperatorId = fields.Length > 12 ? fields[12] : null,
                
                // Auto-map to system analyte
                SystemAnalyte = MapToSystemAnalyte(fields[4])
            };
        }
        
        // ═══════════════════════════════════════════════════════════════
        // RESULT TYPE HANDLERS (Patient, QC, Linearity, QA)
        // ═══════════════════════════════════════════════════════════════
        
        public ProcessedResult ProcessResult(ObservationResult obs)
        {
            var resultType = DetermineResultType(obs);
            
            return resultType switch
            {
                ResultType.PatientResult => ProcessPatientResult(obs),
                ResultType.QCResult => ProcessQCResult(obs),
                ResultType.LinearityResult => ProcessLinearityResult(obs),
                ResultType.QAResult => ProcessQAResult(obs),
                _ => throw new UnknownResultTypeException(resultType)
            };
        }
        
        // ═══════════════════════════════════════════════════════════════
        // MESSAGE BUILDERS (Send to device)
        // ═══════════════════════════════════════════════════════════════
        
        public string BuildAck(int sequence, AckCode code, string errorText = null)
        {
            return $"ACK|{sequence}|{code}|{errorText ?? ""}|";
        }
        
        public string BuildHelloResponse(string lisId, string lisName, string facility)
        {
            return $"HELLO|{lisId}|{lisName}|{facility}|1.0|";
        }
        
        public string BuildConfigMessage(string settingName, object value)
        {
            return $"CONFG|{NextSequence()}|SET|{settingName}|{value}|";
        }
    }
}
```

### TypeScript Service (for RALS Angular)

```typescript
// AUTO-GENERATED FROM BLUEPRINT: monkey_device_900x_blueprint.json
// Generated: 2026-01-18
// DO NOT MANUALLY EDIT - Regenerate from blueprint

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';
import { HubConnection, HubConnectionBuilder } from '@microsoft/signalr';

export interface ObservationResult {
  sequence: number;
  patientId: string;
  sampleId?: string;
  analyteCode: string;
  analyteName: string;
  resultValue: number;
  units: string;
  referenceRange?: string;
  abnormalFlag?: 'N' | 'L' | 'H' | 'LL' | 'HH';
  resultStatus: 'F' | 'P' | 'C';
  timestamp: Date;
  operatorId?: string;
}

export interface DeviceStatus {
  statusCode: 'READY' | 'BUSY' | 'ERROR' | 'MAINT';
  statusText?: string;
  timestamp: Date;
}

export interface AnalyteMapping {
  deviceCode: string;
  deviceName: string;
  systemCode: string | null;
  status: 'mapped' | 'new';
}

@Injectable({ providedIn: 'root' })
export class MonkeyDeviceService {
  
  // Device metadata (from blueprint.device)
  readonly vendorName = 'MonkeyLabs';
  readonly modelName = 'Device900x';
  readonly protocol = 'POCT1-A';
  
  // Analyte mappings (from blueprint + system lookup)
  readonly analyteMappings: AnalyteMapping[] = [
    { deviceCode: 'GLU', deviceName: 'Glucose', systemCode: '2345-7', status: 'mapped' },
    { deviceCode: 'LAC', deviceName: 'Lactate', systemCode: '2518-5', status: 'mapped' },
    { deviceCode: 'BANA', deviceName: 'Banana Sensor', systemCode: null, status: 'new' },
    { deviceCode: 'MNKY', deviceName: 'Monkey Factor', systemCode: null, status: 'new' },
  ];
  
  // Real-time data streams
  private resultsSubject = new Subject<ObservationResult>();
  private statusSubject = new Subject<DeviceStatus>();
  
  results$ = this.resultsSubject.asObservable();
  status$ = this.statusSubject.asObservable();
  
  private hubConnection: HubConnection;
  
  constructor(private http: HttpClient) {
    this.setupSignalR();
  }
  
  private setupSignalR(): void {
    this.hubConnection = new HubConnectionBuilder()
      .withUrl('/hubs/monkey-device')
      .withAutomaticReconnect()
      .build();
    
    this.hubConnection.on('ReceiveResult', (result: ObservationResult) => {
      this.resultsSubject.next(result);
    });
    
    this.hubConnection.on('ReceiveStatus', (status: DeviceStatus) => {
      this.statusSubject.next(status);
    });
  }
  
  connect(ipAddress: string, port: number): Observable<boolean> {
    return this.http.post<boolean>('/api/monkey-device/connect', { ipAddress, port });
  }
  
  disconnect(): Observable<void> {
    return this.http.post<void>('/api/monkey-device/disconnect', {});
  }
  
  getConfiguration(): Observable<DeviceConfiguration> {
    return this.http.get<DeviceConfiguration>('/api/monkey-device/configuration');
  }
  
  updateSetting(settingName: string, value: any): Observable<void> {
    return this.http.put<void>(`/api/monkey-device/settings/${settingName}`, { value });
  }
}
```

---

## Benefits

### Traditional vs Blueprint Approach

| Traditional Approach | Blueprint Approach |
|----------------------|---------------------|
| Write C# driver manually | Generate from blueprint |
| Write TypeScript manually | Generate from blueprint |
| Maintain both separately | Change blueprint → regenerate both |
| Different devs, different styles | Consistent generated code |
| Integration bugs from mismatch | Same source of truth |
| 6-12 months per device | Days to weeks |
| Each device = new project | Each device = new blueprint input |

### Key Benefits

1. **Single Source of Truth** - Blueprint defines device, all code is derived
2. **Language Agnostic** - Generate for any target system
3. **Consistency** - All drivers follow same patterns
4. **Speed** - Days instead of months
5. **Maintainability** - Change blueprint, regenerate code
6. **Auto-Discovery** - New analytes flagged automatically
7. **Plug-and-Play** - Drop-in integration with RALS/AegisPOC

---

## Complete Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PDF → PRODUCTION IN DAYS                              │
└─────────────────────────────────────────────────────────────────────────┘

DAY 1: PDF Processing
═════════════════════
  Vendor PDF ──► spec-parser onboard ──► document.json + baseline.md

DAY 2: Human Review + Corrections
═════════════════════════════════
  Review baseline.md ──► Add corrections ──► Regenerate

DAY 3: Blueprint Generation
═══════════════════════════
  Corrected data ──► LLM ──► device_blueprint.json

DAY 4: Driver Generation
════════════════════════
  Blueprint ──► LLM Code Gen ──► 
    • MonkeyDevice900xDriver.cs (AegisPOC)
    • monkey-device.service.ts (RALS)
    • MonkeyDeviceController.cs (RALS API)

DAY 5: Integration + Testing
════════════════════════════
  Drop drivers into RALS/AegisPOC ──► Configure analyte mappings ──► Test

DAY 6-7: Validation
═══════════════════
  Run QC samples ──► Verify patient results ──► Sign off


TRADITIONAL: 6-12 months
BLUEPRINT APPROACH: 5-7 days (with proper QA)
```

---

## Self-Integrating Device Pipeline

The ultimate goal is a **self-integrating device pipeline**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│              SELF-INTEGRATING DEVICE PIPELINE                            │
└─────────────────────────────────────────────────────────────────────────┘

  New Device Spec (PDF)
         │
         ▼
  ┌─────────────────┐
  │  Spec Parser    │ ──► Corrections (if needed)
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Blueprint Gen  │ ──► device_blueprint.json
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Code Generator │ ──► Driver files for target system
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Auto-Discovery │ ──► Flag new analytes for review
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Drop into      │
  │  RALS/AegisPOC  │ ──► Device is ready to use!
  └─────────────────┘

NOT shipped with the software.
IS the middleware for QUICKLY integrating new devices.
PLUG AND PLAY device onboarding.
```

---

## Related Documentation

- [LLM_BLUEPRINT_GENERATION.md](./LLM_BLUEPRINT_GENERATION.md) - How blueprints are generated from specs
- [CORRECTION_SYSTEM.md](./CORRECTION_SYSTEM.md) - How corrections improve extraction accuracy
- [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) - System architecture overview
