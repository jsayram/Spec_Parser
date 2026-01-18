# Spec Parser and Normalizer

A tool for parsing and normalizing publicly available specifications for POCT1 (Point-of-Care Testing) protocol compliance.

## Overview

This project utilizes publicly available specifications normalized for POCT1 parsing, enabling standardized data exchange between point-of-care testing devices and healthcare information systems.

## Features

- Parse POCT1 specification documents
- Normalize data formats for consistent processing
- Support for publicly available specification sources
- Device lifecycle management (onboard, update, version tracking)
- Cross-platform support (Windows, macOS, Linux)

## Installation

### Prerequisites
- Python 3.10+
- Git
- Tesseract OCR (for image text extraction)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/jsayram/Spec_Parser.git
cd Spec_Parser
```

2. Create and activate virtual environment:

**Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

4. Verify installation:

**Cross-platform (Python):**
```bash
python verify_env.py
```

**Windows:**
```cmd
verify_env.bat
```

**macOS/Linux:**
```bash
./verify_env.sh
```

## Usage

### Device Lifecycle Commands

#### Quick Start with Config Files

The easiest way to use the CLI is with JSON configuration files:

```bash
# Onboard a new device
spec-parser device onboard --config examples/onboard_config.json

# Update existing device
spec-parser device update --config examples/update_config.json
```

See [examples/README.md](examples/README.md) for configuration file formats and more examples.

#### Command-Line Options

**List registered devices:**
```bash
spec-parser device list
```

**Onboard new device (with config file):**
```bash
spec-parser device onboard --config examples/onboard_config.json
```

**Onboard new device (with CLI options):**
```bash
spec-parser device onboard \
  --vendor "Abbott" \
  --model "InfoHQ" \
  --device-name "Abbott InfoHQ POCT Analyzer" \
  --spec-version "3.3.1" \
  --spec-pdf path/to/spec.pdf
```

**Update device specification (with config file):**
```bash
spec-parser device update --config examples/update_config.json
```

**Update device specification (with CLI options):**
```bash
spec-parser device update \
  --device-type "Abbott_InfoHQ" \
  --spec-version "3.4.0" \
  --spec-pdf path/to/new_spec.pdf \
  --approve "Added support for new OBS messages"
```

**Review unrecognized messages (with config file):**
```bash
spec-parser device review-message --config examples/review_approve.json
```

**Review unrecognized messages (with CLI options):**
```bash
spec-parser device review-message \
  --device-type "Abbott_InfoHQ" \
  --message "ZXX" \
  --action approve \
  --notes "Vendor-specific extension for device status"
```

**Mix config files with CLI options (CLI overrides config):**
```bash
spec-parser device onboard \
  --config examples/onboard_config.json \
  --spec-version "3.3.2"
```

## Cross-Platform Compatibility

This project is designed to work seamlessly on Windows, macOS, and Linux:

- Uses `pathlib.Path` for all file operations
- Cross-platform virtual environment support
- Platform-agnostic CLI commands
- Verified on Windows 10/11, macOS, and Linux

## License

*License information to be added*
