# Example Configuration Files

This directory contains example JSON configuration files for device onboarding and updates.

## Usage

Instead of typing long command-line arguments, you can use a JSON config file:

```bash
# Using config file
spec-parser device onboard --config examples/onboard_config.json

# CLI options override config file values
spec-parser device onboard --config examples/onboard_config.json --spec-version "3.3.2"
```

## Configuration File Formats

### Onboarding Config (`onboard_config.json`)

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

**Required fields:**
- `vendor` - Vendor name (e.g., "Roche", "Abbott")
- `model` - Model name (e.g., "CobasLiat", "InfoHQ")
- `device_name` - Human-readable device name
- `spec_version` - Specification version (e.g., "3.3.1")
- `spec_pdf` - Path to PDF specification file

**Optional fields:**
- `output_dir` - Output directory (default: "data/spec_output")

### Update Config (`update_config.json`)

```json
{
  "device_type": "Roche_CobasLiat",
  "spec_version": "3.4.0",
  "spec_pdf": "path/to/new_spec.pdf",
  "approve": "Reason for approval",
  "output_dir": "data/spec_output"
}
```

**Required fields:**
- `device_type` - Device type ID (format: `vendor_model`)
- `spec_version` - New specification version
- `spec_pdf` - Path to new PDF specification

**Optional fields:**
- `approve` - Approval reason (required if HIGH/MEDIUM changes detected)
- `output_dir` - Output directory (default: "data/spec_output")

### Review Message Config (`review_approve.json`)

```json
{
  "device_type": "Roche_CobasLiat",
  "message": "ZOP",
  "action": "approve",
  "notes": "Reason for approval/rejection/deferral"
}
```

**Required fields:**
- `device_type` - Device type ID (format: `vendor_model`)
- `message` - Message ID to review (e.g., "ZOP", "ZXX")
- `action` - Review action: `approve`, `reject`, or `defer`

**Optional fields:**
- `notes` - Review notes explaining the decision (default: "")

## Examples

### 1. Roche cobas Liat

```bash
spec-parser device onboard --config examples/onboard_config.json
```

### 2. Abbott InfoHQ

```bash
spec-parser device onboard --config examples/onboard_abbott.json
```

### 3. Quidel Sofia

```bash
spec-parser device onboard --config examples/onboard_quidel.json
```

### 4. Update Existing Device

```bash
spec-parser device update --config examples/update_config.json
```

### 5. Review Unrecognized Messages

```bash
# Approve a vendor extension
spec-parser device review-message --config examples/review_approve.json

# Reject an invalid message
spec-parser device review-message --config examples/review_reject.json

# Defer pending vendor clarification
spec-parser device review-message --config examples/review_defer.json
```

## Mixing Config Files and CLI Options

CLI options always override config file values:

```bash
# Use config but override spec version
spec-parser device onboard \
  --config examples/onboard_config.json \
  --spec-version "3.3.2"

# Use config but override approval reason
spec-parser device update \
  --config examples/update_config.json \
  --approve "Critical security update"
```

## Tips

1. **Store configs in version control** - Track device configurations alongside code
2. **Use relative paths** - Make configs portable across environments
3. **Environment-specific configs** - Create separate configs for dev/staging/prod
4. **Template configs** - Copy examples and customize for your devices
