# Sofia POCT1-A (POCT1a) message types, directives, and field catalog

This is an extraction-oriented cheat sheet for the **POCT1-A2 XML** messaging defined in the uploaded vendor spec (Quidel **Sofia**).

## Parsing conventions

- Values are stored in the XML attribute `V`:
  - Example: `<HDR.control_id V="00001"/>`
- Many elements are “objects” (HDR, DEV, DSC, ...). Nested elements matter.
- Some coded fields may include an additional attribute like `SN="QUIDEL"` (treat this as a vendor/code-system tag).

## Message flow (high level)

### Introduction phase
1. `HEL.R01` (Sofia -> LIS)
2. `ACK.R01` (LIS -> Sofia)
3. `DST.R01` (Sofia -> LIS)
4. `ACK.R01` (LIS -> Sofia)
5. `DTV.R02` with `SET_TIME` (LIS -> Sofia)
6. `ACK.R01` (LIS -> Sofia)
7. `OPL.R01` operator list (LIS -> Sofia)
8. `ACK.R01` (LIS -> Sofia)
9. `EOT.R01` end of topic (LIS -> Sofia)
10. `ACK.R01` (LIS -> Sofia)
11. `DTV.R01` with `START_CONTINUOUS` (LIS -> Sofia)
12. `ACK.R01` (LIS -> Sofia)

### Continuous phase
- `DST.R01` (Sofia -> LIS) indicates whether new observations exist.
- If observations exist, Sofia sends:
  - `OBS.R01` patient results, or
  - `OBS.R02` non-patient results (QC / CAL)
- LIS responds with `ACK.R01` to each message.

### Termination / error behavior
- `END.R01` terminates the connection (reason code `USR` shown in the spec).
- On unexpected/unsupported input, the spec states Sofia transmits an `ESC` control character and then `END`.

## Supported topics and directives (from HEL)

- **Topics supported:** `DTV`, `OP_LST_I`
- **Directives supported:** `SET_TIME`, `START_CONTINUOUS`

## Field type glossary (practical)

- **TS timestamp:** `YYYY-MM-DDThh:mm:ss±hh:mm` (example: `2019-02-22T11:01:29-00:00`)
- **Date:** `YYYY-MM-DD` (example: `2025-04-03`)
- **Code (enum string):** typically ends in `_cd` (example: `SVC.reason_cd=NEW`)
- **Identifier (string):** typically ends in `_id` (patient_id, order_id, device_id, etc.)
- **Quantity:** typically ends in `_qty` or `_sz` (in this spec transmitted as text digits)

---

# Message definitions

## HEL.R01 (Hello) — Sofia -> LIS

Purpose: announces device identity and capabilities.

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | Unique message identifier | 00001 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2017-12-07T11:48:49-00:00 |
| DEV.device_id | string | Device ID shown as MAC-like | 00:06:66:00:22:A1 |
| DEV.serial_id | string | | 00010387 |
| DEV.manufacturer_name | string | | QUIDEL |
| DEV.hw_version | string | | 00.03.01 |
| DEV.sw_version | string | | 02.03.01 |
| DEV.device_name | string | | Sofia |
| DCP.application_timeout | quantity | Timeout in seconds (as text) | 100 |
| DSC.connection_profile_cd | code | Connection profile | CS |
| DSC.topics_supported_cd | code (repeatable) | Supported topics | DTV ; OP_LST_I |
| DSC.directives_supported_cd | code (repeatable) | Supported directives | SET_TIME ; START_CONTINUOUS |
| DSC.max_message_sz | quantity | Max message size bytes | 1000 |

## ACK.R01 (Acknowledge) — LIS -> Sofia

Purpose: acknowledges a received message (accepted or error).

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | Control id for the ACK itself | 4011 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2019-05-20T08:21:50-00:00 |
| ACK.type_id | code | `AA` accepted; `AE` error (as shown) | AA |
| ACK.control_id | string (int-as-text) | Control id of the message being ACKed | 1 |

## DST.R01 (Device status) — Sofia -> LIS

Purpose: status heartbeat; indicates whether new observations exist.

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 00002 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2017-12-07T11:48:52-00:00 |
| DST.status_dttm | TS timestamp | Status time | 2017-12-07T11:48:52-00:00 |
| DST.new_observations_qty | quantity | Count of new observations | 0 |
| DST.condition_cd | code | Condition code shown as `R` | R |

## DTV.R02 (Complex directive) — LIS -> Sofia

Purpose: send a directive with associated data. In this spec it is used for `SET_TIME`.

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 00003 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2017-12-07T11:48:52-00:00 |
| DTV.command_cd | code | Always `SET_TIME` | SET_TIME |
| TM.dttm | TS timestamp | Clock value to set | 2017-12-07T11:48:52-00:00 |

## OPL.R01 (Operator list) — LIS -> Sofia

Purpose: deliver an operator record (repeatable) with access control.

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 00004 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2017-12-07T11:48:52-00:00 |
| OPR.operator_id | string | Operator identifier | 5047 |
| OPR.name | string | Display name | Supervisor |
| ACC.method_cd | code | Always `ALL` | ALL |
| ACC.permision_level_cd | code | Spec shows 4=supervisor, 1=user | 4 |
| NTE.text | string | Optional note text | (blank in example) |

## EOT.R01 (End of topic) — LIS -> Sofia

Purpose: signals end of a topic transmission (here: end of operator list topic).

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 00005 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2017-12-07T11:48:52-00:00 |
| EOT.topic_cd | code | Topic id (shown: `OPL`) | OPL |

## DTV.R01 (Basic directive) — LIS -> Sofia

Purpose: directive without extra payload. In this spec it is used for `START_CONTINUOUS`.

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 4016 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2019-05-04T11:53:54-05:00 |
| DTV.command_cd | code | Always `START_CONTINUOUS` | START_CONTINUOUS |

## OBS.R01 (Patient observation) — Sofia -> LIS

Purpose: patient results. Structure nests service info, patient id, one-or-more observations, and supporting metadata.

Notes:
- `SVC` wraps service metadata.
- `PT` wraps patient id and contains one or more `OBS` elements.
- `OBS` repeats for multiple analytes (example includes Flu A and Flu B).
- `OBS.observation_id` in the example has `SN="QUIDEL"` (treat `SN` as a code-system/vendor tag).

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 00027 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2019-02-22T11:02:44-00:00 |
| SVC.role_cd | code | Patient tests shown as `OBS` | OBS |
| SVC.observation_dttm | TS timestamp | Observation time | 2019-02-22T11:01:29-00:00 |
| SVC.reason_cd | code | NEW or RES | NEW |
| PT.patient_id | string | Patient identifier (treat as opaque) | Y B1232 |
| OBS.observation_id | string / code | Analyte/test id (repeatable) | Flu A ; Flu B |
| OBS.qualitative_value | string / code | Result (qualitative) | negative |
| OBS.method_cd | code | Spec shows `M` or `C`; example uses `M` | M |
| OPR.operator_id | string | Operator performing test | Y B LAST |
| ORD.universal_service_id | string | Test/service name | Sofia Flu A+B |
| ORD.order_id | string | Order id (example uses `SN="Sofia"`) | 1232Y B |
| RGT.name | string | Reagent/cassette name | Sofia Flu A+B |
| RGT.lot_number | string | Reagent/cassette lot | 140403 |
| RGT.expiration_date | date | Reagent/cassette expiration | 2025-04-03 |

## OBS.R02 (Non-patient observation: QC / CAL) — Sofia -> LIS

Purpose: non-patient results such as calibration and liquid QC.

Notes:
- Spec states `SVC.role_cd` should be `CAL` for calibration and `LQC` for QC, but the provided example uses `OBS`.
- `CTC` describes the control/calibration material.

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 00018 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2019-02-22T11:02:25-00:00 |
| SVC.role_cd | code | CAL or LQC (see note) | OBS (example) |
| SVC.observation_dttm | TS timestamp | | 2018-05-19T07:51:22-00:00 |
| SVC.reason_cd | code | NEW or RES | RES |
| CTC.name | string | Control/calibration name | Calibration Result |
| CTC.lot_number | string | | 103533 |
| CTC.expiration_date | date | If present | 2020-06-30 |
| CTC.level_cd | code | For QC: Positive/Negative Control | Positive Control |
| OBS.observation_id | string / code | Example: overall result | Overall Result |
| OBS.qualitative_value | string / code | Example: passed/failed | passed |
| OBS.method_cd | code | M or C; example uses M | M |
| OPR.operator_id | string | | Supervisor |
| RGT.name | string | QC reagent name (for QC tests) | Sofia Strep A |
| RGT.lot_number | string | QC reagent lot | 30437 |
| RGT.expiration_date | date | QC reagent expiration | 2025-06-21 |

## END.R01 (Termination) — Sofia -> LIS

Purpose: terminate the POCT1-A session.

| Field | Type / format | Notes / allowed values | Example |
|---|---|---|---|
| HDR.control_id | string (int-as-text) | | 00044 |
| HDR.version_id | code | Always `POCT1` | POCT1 |
| HDR.creation_dttm | TS timestamp | | 2018-06-14T13:11:20-00:00 |
| TRM.reason_cd | code | Termination reason (shown: USR) | USR |

---

## Vendor-specific implementation notes (things your parser should not assume away)

- Many identifiers contain spaces (patient_id, operator_id, order_id). Treat them as opaque strings.
- The same logical field appears in multiple contexts (e.g., `HDR.control_id` exists in every message).
- Observation groups are nested and repeating. Do not assume a single `OBS`.
- A few typos exist in field names in the vendor doc (e.g., `ACC.permision_level_cd`). For extraction, you may need to accept both spellings if they show up in real traffic.
