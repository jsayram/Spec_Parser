#!/bin/bash
# Verification script to ensure virtual environment is active and all requirements are installed

set -e  # Exit on error

echo "=== Spec Parser Environment Verification ==="
echo ""

# Check if we're in the project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "✓ Project directory: $SCRIPT_DIR"
echo ""

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "✗ Virtual environment not found!"
    echo "  Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
fi

# Activate venv
source .venv/bin/activate
echo "✓ Virtual environment activated: $VIRTUAL_ENV"
echo ""

# Check Python version
PYTHON_VERSION=$(.venv/bin/python --version)
echo "✓ Python version: $PYTHON_VERSION"
echo ""

# Install/upgrade requirements
echo "=== Installing requirements ==="
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
.venv/bin/pip install --quiet -r requirements-dev.txt
.venv/bin/pip install --quiet -e .
echo "✓ All requirements installed"
echo ""

# Verify spec-parser command
if command -v spec-parser &> /dev/null; then
    SPEC_VERSION=$(spec-parser --version 2>&1 | grep -o 'version [0-9.]*' || echo "unknown")
    echo "✓ spec-parser command available: $SPEC_VERSION"
else
    echo "✗ spec-parser command not found!"
    exit 1
fi
echo ""

# Verify key packages
echo "=== Verifying key packages ==="
.venv/bin/python -c "import pymupdf4llm; print('✓ pymupdf4llm:', pymupdf4llm.__version__)" 2>/dev/null || echo "✗ pymupdf4llm not found"
.venv/bin/python -c "import pytesseract; print('✓ pytesseract installed')" 2>/dev/null || echo "✗ pytesseract not found"
.venv/bin/python -c "import pydantic; print('✓ pydantic:', pydantic.__version__)" 2>/dev/null || echo "✗ pydantic not found"
.venv/bin/python -c "import click; print('✓ click:', click.__version__)" 2>/dev/null || echo "✗ click not found"
.venv/bin/python -c "import faiss; print('✓ faiss installed')" 2>/dev/null || echo "✗ faiss not found"
.venv/bin/python -c "import sentence_transformers; print('✓ sentence-transformers:', sentence_transformers.__version__)" 2>/dev/null || echo "✗ sentence-transformers not found"
echo ""

echo "=== Environment verification complete! ==="
echo ""
echo "To activate the virtual environment manually, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To run spec-parser commands:"
echo "  spec-parser --help"
echo "  spec-parser device --help"
echo ""
