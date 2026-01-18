# Command Reference

Complete reference for all `spec-parser device` commands.

## Commands Overview

| Command | Config Support | Description |
|---------|----------------|-------------|
| `list` | ❌ No params | List all registered devices |
| `onboard` | ✅ Full support | Register new device type |
| `update` | ✅ Full support | Update device to new spec version |
| `review-message` | ✅ Full support | Review unrecognized messages |

---

## 1. List Devices

**No configuration needed** - Lists all registered devices.

```bash
spec-parser device list
```

**Output:**
```
Registered devices (2):
  Roche_CobasLiat: Roche cobas Liat Analyzer (v3.3.1)
  Abbott_InfoHQ: Abbott InfoHQ POCT Analyzer (v2.1.0)
```

---

## 2. Onboard Device

Register a new device type with its first specification version.

### Config File Format

```json
{
  "vendor": "Roche",
  "model": "CobasLiat",
  "device_name": "Roche cobas Liat Analyzer",
  "spec_version": "3.3.1",
  "spec_pdf": "path/to/spec.pdf",
  "output_dir": "data/spec_output"
}
```

**Required:** `vendor`, `model`, `device_name`, `spec_version`, `spec_pdf`  
**Optional:** `output_dir`

### Usage Examples

**With config file:**
```bash
spec-parser device onboard --config examples/onboard_config.json
```

**With CLI options:**
```bash
spec-parser device onboard \
  --vendor "Roche" \
  --model "CobasLiat" \
  --device-name "Roche cobas Liat Analyzer" \
  --spec-version "3.3.1" \
  --spec-pdf "path/to/spec.pdf"
```

**Mix config + CLI (override version):**
```bash
spec-parser device onboard \
  --config examples/onboard_config.json \
  --spec-version "3.3.2"
```

### What It Does

1. ✅ Extracts PDF content (text, images, tables)
2. ✅ Runs OCR on images and graphics
3. ✅ Creates JSON sidecar with provenance
4. ✅ Generates human-readable markdown
5. ✅ Builds FAISS + BM25 search indices
6. ✅ Parses POCT1 messages and fields
7. ✅ Creates baseline report
8. ✅ Registers device in registry

### Output Location

```
data/spec_output/{timestamp}_{vendor}{model}/
├── images/              # Extracted images
├── json/                # Machine-readable data
├── markdown/            # Human-readable document
├── index/               # Search indices
└── BASELINE_*.md        # Initial report
```

---

## 3. Update Device

Update an existing device to a new specification version.

### Config File Format

```json
{
  "device_type": "Roche_CobasLiat",
  "spec_version": "3.4.0",
  "spec_pdf": "path/to/new_spec.pdf",
  "approve": "Reason for approval",
  "output_dir": "data/spec_output"
}
```

**Required:** `device_type`, `spec_version`, `spec_pdf`  
**Optional:** `approve`, `output_dir`

### Usage Examples

**With config file:**
```bash
spec-parser device update --config examples/update_config.json
```

**With CLI options:**
```bash
spec-parser device update \
  --device-type "Roche_CobasLiat" \
  --spec-version "3.4.0" \
  --spec-pdf "path/to/new_spec.pdf" \
  --approve "Added support for new OBS messages"
```

**Without approval (will fail if HIGH/MEDIUM changes):**
```bash
spec-parser device update \
  --device-type "Roche_CobasLiat" \
  --spec-version "3.4.0" \
  --spec-pdf "path/to/new_spec.pdf"
```

### What It Does

1. ✅ Computes PDF hash (skip if unchanged)
2. ✅ Extracts new spec version
3. ✅ Compares with previous version (block-by-block diff)
4. ✅ Classifies impact: HIGH, MEDIUM, LOW
5. ✅ Requires `--approve` for HIGH/MEDIUM changes
6. ✅ Generates change report
7. ✅ Rebuilds indices (if needed)
8. ✅ Updates device registry

### Change Impact Levels

- **HIGH**: Message add/remove, field rename, type/cardinality changes → **Requires approval**
- **MEDIUM**: Optional field additions, vendor extensions → **Requires approval**
- **LOW**: Whitespace, formatting, documentation → **No rebuild needed**

### Output

- `CHANGES_v{old}_to_v{new}_{timestamp}.md` - Change report
- New version directory (if rebuilt)

---

## 4. Review Message

Review and approve/reject/defer unrecognized messages.

### Config File Format

```json
{
  "device_type": "Roche_CobasLiat",
  "message": "ZOP",
  "action": "approve",
  "notes": "Vendor-specific operator update message"
}
```

**Required:** `device_type`, `message`, `action`  
**Optional:** `notes`

**Actions:** `approve`, `reject`, `defer`

### Usage Examples

**Approve with config:**
```bash
spec-parser device review-message --config examples/review_approve.json
```

**Reject with CLI:**
```bash
spec-parser device review-message \
  --device-type "Roche_CobasLiat" \
  --message "ZQC" \
  --action reject \
  --notes "OCR error - not a valid message"
```

**Defer pending vendor info:**
```bash
spec-parser device review-message \
  --device-type "Abbott_InfoHQ" \
  --message "ZXX" \
  --action defer \
  --notes "Awaiting vendor documentation"
```

### What It Does

1. ✅ Loads unrecognized messages from `data/custom_messages.json`
2. ✅ Updates review status
3. ✅ Adds review notes and timestamp
4. ✅ Saves for audit trail

### Use Cases

- **Approve**: Vendor-specific extensions (Z** messages)
- **Reject**: OCR errors or invalid messages
- **Defer**: Need more information from vendor

---

## Example Configs Provided

All config files are in `examples/`:

| Config File | Command | Use Case |
|-------------|---------|----------|
| `onboard_config.json` | onboard | Roche cobas Liat |
| `onboard_abbott.json` | onboard | Abbott InfoHQ |
| `onboard_quidel.json` | onboard | Quidel Sofia |
| `update_config.json` | update | Update to new version |
| `review_approve.json` | review-message | Approve vendor extension |
| `review_reject.json` | review-message | Reject invalid message |
| `review_defer.json` | review-message | Defer pending info |

---

## Config File Best Practices

1. **Use version control** - Track config changes with git
2. **Descriptive filenames** - `roche_cobas_liat_v3.3.1_onboard.json`
3. **Environment-specific** - Separate configs for dev/staging/prod
4. **Relative paths** - Makes configs portable across systems
5. **Document decisions** - Use detailed notes in review configs
6. **Template library** - Keep a set of templates for common devices

---

## CLI Override Priority

When using both config files and CLI options:

```
CLI Options > Config File > Defaults
```

Example:
```bash
# Config has version "3.3.1", CLI overrides to "3.3.2"
spec-parser device onboard \
  --config config.json \
  --spec-version "3.3.2"  # <-- This wins
```

This allows you to:
- Keep common settings in config
- Override specific values per execution
- Reuse configs across similar devices
