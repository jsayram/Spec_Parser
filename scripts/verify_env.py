#!/usr/bin/env python3
"""
Verify environment configuration for LLM extraction.

Checks:
- .env file exists and is readable
- Required settings are present
- API keys are set (if using external providers)
- Ollama is running (if using ollama provider)
- Cache directory is writable
- No sensitive data in git

Usage:
    python scripts/verify_env.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from spec_parser.config import settings


def check_icon(passed: bool) -> str:
    """Return check or X icon."""
    return "✅" if passed else "❌"


def check_env_file():
    """Check .env file exists and is readable."""
    env_path = project_root / ".env"
    
    print("\n" + "=" * 70)
    print("ENVIRONMENT FILE CHECK")
    print("=" * 70)
    
    if env_path.exists():
        print(f"{check_icon(True)} .env file found: {env_path}")
        
        # Check it's not tracked by git
        import subprocess
        try:
            result = subprocess.run(
                ["git", "check-ignore", ".env"],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"{check_icon(True)} .env is properly ignored by git")
            else:
                print(f"{check_icon(False)} WARNING: .env may not be in .gitignore!")
        except:
            print("   (Could not verify git ignore status)")
        
        return True
    else:
        print(f"{check_icon(False)} .env file NOT found: {env_path}")
        print("\n   Run: cp .env.example .env")
        return False


def check_llm_config():
    """Check LLM configuration."""
    print("\n" + "=" * 70)
    print("LLM CONFIGURATION")
    print("=" * 70)
    
    print(f"\nProvider: {settings.llm_provider}")
    print(f"Model: {settings.llm_model}")
    print(f"Temperature: {settings.llm_temperature}")
    print(f"Max Tokens: {settings.llm_max_tokens}")
    
    checks_passed = True
    
    # Check provider-specific requirements
    if settings.llm_provider == "huggingface":
        print(f"\nModel: {settings.llm_model}")
        
        # Check dependencies
        try:
            import torch
            import transformers
            print(f"{check_icon(True)} transformers installed: {transformers.__version__}")
            print(f"{check_icon(True)} torch installed: {torch.__version__}")
            
            # Check device availability
            if torch.cuda.is_available():
                print(f"{check_icon(True)} CUDA GPU available: {torch.cuda.get_device_name(0)}")
                print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                print(f"{check_icon(True)} Apple Silicon GPU (MPS) available")
            else:
                print(f"{check_icon(True)} CPU only (GPU not detected)")
                print("   Note: GPU recommended for faster inference")
            
            # Check cache directory
            hf_home = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
            print(f"\nModel cache: {hf_home}")
            if Path(hf_home).exists():
                print(f"{check_icon(True)} Cache directory exists")
            else:
                print(f"{check_icon(False)} Cache directory not found (will be created on first use)")
            
            # Check token (optional)
            hf_token = os.getenv("HF_TOKEN")
            if hf_token:
                print(f"{check_icon(True)} HF_TOKEN is set (for gated models)")
            else:
                print("   HF_TOKEN not set (only needed for gated models)")
            
        except ImportError as e:
            print(f"{check_icon(False)} Missing dependencies: {e}")
            print("\n   Install with: pip install transformers torch")
            checks_passed = False
    
    elif settings.llm_provider == "ollama":
        print(f"\nOllama Base URL: {settings.llm_base_url}")
        
        # Test Ollama connection
        try:
            import requests
            response = requests.get(f"{settings.llm_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"{check_icon(True)} Ollama is running")
                
                # Check if model is available
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models]
                if settings.llm_model in model_names:
                    print(f"{check_icon(True)} Model '{settings.llm_model}' is available")
                else:
                    print(f"{check_icon(False)} Model '{settings.llm_model}' NOT found")
                    print(f"\n   Available models: {model_names}")
                    print(f"   Run: ollama pull {settings.llm_model}")
                    checks_passed = False
            else:
                print(f"{check_icon(False)} Ollama responded with error: {response.status_code}")
                checks_passed = False
        except Exception as e:
            print(f"{check_icon(False)} Cannot connect to Ollama: {e}")
            print(f"\n   Run: ollama serve")
            checks_passed = False
    
    elif settings.llm_provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            print(f"{check_icon(True)} ANTHROPIC_API_KEY is set ({len(api_key)} chars)")
            if api_key.startswith("sk-ant-"):
                print(f"{check_icon(True)} API key format looks valid")
            else:
                print(f"{check_icon(False)} API key format may be invalid (should start with 'sk-ant-')")
                checks_passed = False
        else:
            print(f"{check_icon(False)} ANTHROPIC_API_KEY is NOT set")
            print("\n   Add to .env: ANTHROPIC_API_KEY=sk-ant-...")
            checks_passed = False
    
    elif settings.llm_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            print(f"{check_icon(True)} OPENAI_API_KEY is set ({len(api_key)} chars)")
            if api_key.startswith("sk-"):
                print(f"{check_icon(True)} API key format looks valid")
            else:
                print(f"{check_icon(False)} API key format may be invalid (should start with 'sk-')")
                checks_passed = False
        else:
            print(f"{check_icon(False)} OPENAI_API_KEY is NOT set")
            print("\n   Add to .env: OPENAI_API_KEY=sk-...")
            checks_passed = False
    
    else:
        print(f"{check_icon(False)} Unknown LLM provider: {settings.llm_provider}")
        print("   Valid options: ollama, anthropic, openai")
        checks_passed = False
    
    return checks_passed


def check_cache_directory():
    """Check cache directory is writable."""
    print("\n" + "=" * 70)
    print("CACHE DIRECTORY CHECK")
    print("=" * 70)
    
    cache_dir = settings.llm_cache_dir
    
    if cache_dir.exists():
        print(f"{check_icon(True)} Cache directory exists: {cache_dir}")
    else:
        print(f"{check_icon(False)} Cache directory does NOT exist: {cache_dir}")
        print("   Creating...")
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            print(f"{check_icon(True)} Created successfully")
        except Exception as e:
            print(f"{check_icon(False)} Failed to create: {e}")
            return False
    
    # Test write permissions
    test_file = cache_dir / ".write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print(f"{check_icon(True)} Cache directory is writable")
        return True
    except Exception as e:
        print(f"{check_icon(False)} Cache directory is NOT writable: {e}")
        return False


def check_gitignore():
    """Check sensitive files are in .gitignore."""
    print("\n" + "=" * 70)
    print("GIT SECURITY CHECK")
    print("=" * 70)
    
    gitignore_path = project_root / ".gitignore"
    
    if not gitignore_path.exists():
        print(f"{check_icon(False)} .gitignore NOT found!")
        return False
    
    gitignore_content = gitignore_path.read_text()
    
    checks = [
        (".env", "Environment file with API keys"),
        ("*.db", "SQLite cache databases"),
        ("llm_corrections.db", "LLM correction cache"),
    ]
    
    all_passed = True
    for pattern, description in checks:
        if pattern in gitignore_content:
            print(f"{check_icon(True)} {pattern} is ignored ({description})")
        else:
            print(f"{check_icon(False)} {pattern} NOT in .gitignore ({description})")
            all_passed = False
    
    return all_passed


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("SPEC PARSER ENVIRONMENT VERIFICATION")
    print("=" * 70)
    print(f"\nProject Root: {project_root}")
    
    results = {
        "env_file": check_env_file(),
        "llm_config": check_llm_config(),
        "cache_dir": check_cache_directory(),
        "gitignore": check_gitignore(),
    }
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = all(results.values())
    
    for check, passed in results.items():
        status = "PASS" if passed else "FAIL"
        icon = check_icon(passed)
        print(f"{icon} {check.replace('_', ' ').title()}: {status}")
    
    if all_passed:
        print("\n✅ All checks passed! Environment is ready.")
        print("\nNext step: Run blueprint extraction")
        print("   spec-parser device extract-blueprint --help")
        return 0
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
