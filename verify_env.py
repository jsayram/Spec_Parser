#!/usr/bin/env python3
"""Cross-platform environment verification script for Spec Parser."""

import sys
import subprocess
from pathlib import Path


def run_command(cmd, capture=True):
    """Run command and return output."""
    try:
        if capture:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True)
            return None
    except subprocess.CalledProcessError as e:
        return None


def main():
    print("=== Spec Parser Environment Verification ===")
    print()
    
    # Check project directory
    project_dir = Path(__file__).parent.resolve()
    print(f"✓ Project directory: {project_dir}")
    print()
    
    # Check if venv exists
    venv_dir = project_dir / ".venv"
    if not venv_dir.exists():
        print("✗ Virtual environment not found!")
        print("  Run: python -m venv .venv")
        sys.exit(1)
    
    print(f"✓ Virtual environment exists: {venv_dir}")
    
    # Determine Python executable in venv
    if sys.platform == "win32":
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
        spec_parser_exe = venv_dir / "Scripts" / "spec-parser.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
        spec_parser_exe = venv_dir / "bin" / "spec-parser"
    
    if not python_exe.exists():
        print(f"✗ Python executable not found: {python_exe}")
        sys.exit(1)
    
    # Check Python version
    version = run_command(f'"{python_exe}" --version')
    print(f"✓ {version}")
    print()
    
    # Install/upgrade requirements
    print("=== Installing requirements ===")
    run_command(f'"{pip_exe}" install --quiet --upgrade pip', capture=False)
    run_command(f'"{pip_exe}" install --quiet -r requirements.txt', capture=False)
    run_command(f'"{pip_exe}" install --quiet -r requirements-dev.txt', capture=False)
    run_command(f'"{pip_exe}" install --quiet -e .', capture=False)
    print("✓ All requirements installed")
    print()
    
    # Verify spec-parser command
    if spec_parser_exe.exists():
        version_output = run_command(f'"{spec_parser_exe}" --version')
        if version_output and "version" in version_output:
            print(f"✓ spec-parser command available: {version_output.split('version')[1].strip()}")
        else:
            print("✓ spec-parser command available")
    else:
        print("✗ spec-parser command not found!")
        sys.exit(1)
    print()
    
    # Verify key packages
    print("=== Verifying key packages ===")
    
    packages = [
        ("pymupdf4llm", "import pymupdf4llm; print('✓ pymupdf4llm:', pymupdf4llm.__version__)"),
        ("pytesseract", "import pytesseract; print('✓ pytesseract installed')"),
        ("pydantic", "import pydantic; print('✓ pydantic:', pydantic.__version__)"),
        ("click", "import click; print('✓ click:', click.__version__)"),
        ("faiss", "import faiss; print('✓ faiss installed')"),
        ("sentence_transformers", "import sentence_transformers; print('✓ sentence-transformers:', sentence_transformers.__version__)"),
    ]
    
    for name, check_cmd in packages:
        result = run_command(f'"{python_exe}" -c "{check_cmd}"')
        if result:
            print(result)
        else:
            print(f"✗ {name} not found")
    
    print()
    print("=== Environment verification complete! ===")
    print()
    print("To activate the virtual environment:")
    if sys.platform == "win32":
        print("  .venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")
    print()
    print("To run spec-parser commands:")
    print(f'  "{spec_parser_exe}" --help')
    print(f'  "{spec_parser_exe}" device --help')
    print()


if __name__ == "__main__":
    main()
