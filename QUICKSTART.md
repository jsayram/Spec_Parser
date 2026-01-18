# Quick Start Guide

## Using Configuration Files (Recommended)

The easiest way to use spec-parser is with JSON configuration files.

### 1. Create Your Config File

Copy an example and customize:

```bash
cp examples/onboard_config.json my_device_config.json
```

Edit `my_device_config.json`:

```json
{
  "vendor": "YourVendor",
  "model": "YourModel",
  "device_name": "Your Device Full Name",
  "spec_version": "1.0.0",
  "spec_pdf": "path/to/your/spec.pdf",
  "output_dir": "data/spec_output"
}
```

### 2. Onboard Your Device

```bash
spec-parser device onboard --config my_device_config.json
```

That's it! The tool will:
- ✅ Extract PDF content with OCR
- ✅ Parse POCT1 messages and fields
- ✅ Build search indices
- ✅ Generate baseline report
- ✅ Register device in registry

### 3. View Results

Check the output directory:
```
data/spec_output/{timestamp}_{vendor}{model}/
├── images/              # Extracted images
├── json/                # Machine-readable data
├── markdown/            # Human-readable document
├── index/               # Search indices
└── BASELINE_*.md        # Initial report
```

### 4. Update Your Device

When a new spec version is released:

1. Create update config:
```json
{
  "device_type": "YourVendor_YourModel",
  "spec_version": "1.1.0",
  "spec_pdf": "path/to/new/spec.pdf"
}
```

2. Run update:
```bash
spec-parser device update --config update_config.json
```

3. If HIGH/MEDIUM changes detected, approve:
```bash
spec-parser device update \
  --config update_config.json \
  --approve "Reason for approval"
```

## Command-Line Options (Alternative)

You can also use CLI options directly:

```bash
# Onboard
spec-parser device onboard \
  --vendor "Roche" \
  --model "CobasLiat" \
  --device-name "Roche cobas Liat Analyzer" \
  --spec-version "3.3.1" \
  --spec-pdf "path/to/spec.pdf"

# Update
spec-parser device update \
  --device-type "Roche_CobasLiat" \
  --spec-version "3.4.0" \
  --spec-pdf "path/to/new/spec.pdf" \
  --approve "Updated for new messages"
```

## Mixing Config and CLI

CLI options override config file values:

```bash
# Use config but override version
spec-parser device onboard \
  --config my_device_config.json \
  --spec-version "1.0.1"
```

## Common Tasks

### List All Devices
```bash
spec-parser device list
```

### Review Unrecognized Messages

With config file:
```bash
spec-parser device review-message --config examples/review_approve.json
```

With CLI options:
```bash
spec-parser device review-message \
  --device-type "YourVendor_YourModel" \
  --message "ZXX" \
  --action approve \
  --notes "Vendor-specific extension"
```

## Tips

1. **Store configs in version control** - Track device configurations
2. **Use descriptive names** - `roche_cobas_liat_v3.3.1.json`
3. **Relative paths** - Makes configs portable
4. **Separate configs per environment** - dev, staging, prod

## Troubleshooting

**"Device already registered"**
- Use `device update` instead of `device onboard`

**"Missing required parameters"**
- Check your config file has all required fields
- Run with `--help` to see required options

**"HIGH/MEDIUM changes require approval"**
- Add `--approve "reason"` to your command

## Next Steps

- See [examples/README.md](examples/README.md) for more config examples
- See [README.md](../README.md) for full documentation
