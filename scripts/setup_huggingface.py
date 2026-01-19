#!/usr/bin/env python3
"""
Quick setup script for HuggingFace provider.

Installs dependencies and pre-downloads model.

Usage:
    python scripts/setup_huggingface.py [model_id]
    
Examples:
    python scripts/setup_huggingface.py                                    # Default: Qwen2.5-Coder-7B
    python scripts/setup_huggingface.py Qwen/Qwen2.5-Coder-3B-Instruct    # 3B model
    python scripts/setup_huggingface.py microsoft/Phi-3.5-mini-instruct   # Phi-3.5
"""

import os
import sys
import subprocess
from pathlib import Path

# Default model if not specified
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"


def check_icon(passed: bool) -> str:
    """Return check or X icon."""
    return "✅" if passed else "❌"


def install_dependencies():
    """Install transformers and torch."""
    print("\n" + "=" * 70)
    print("INSTALLING DEPENDENCIES")
    print("=" * 70)
    
    try:
        import torch
        import transformers
        print(f"{check_icon(True)} transformers already installed: {transformers.__version__}")
        print(f"{check_icon(True)} torch already installed: {torch.__version__}")
        return True
    except ImportError:
        pass
    
    print("\nInstalling transformers and torch...")
    print("This may take a few minutes...\n")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "transformers", "torch"],
            check=True
        )
        print(f"\n{check_icon(True)} Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{check_icon(False)} Failed to install dependencies: {e}")
        return False


def check_device():
    """Check available compute devices."""
    print("\n" + "=" * 70)
    print("CHECKING COMPUTE DEVICES")
    print("=" * 70)
    
    try:
        import torch
        
        if torch.cuda.is_available():
            print(f"{check_icon(True)} CUDA GPU detected: {torch.cuda.get_device_name(0)}")
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"   VRAM: {vram:.1f} GB")
            
            if vram < 6:
                print("\n⚠️  Warning: Low VRAM detected")
                print("   Recommended: Use Qwen2.5-Coder-1.5B-Instruct (3GB) or enable quantization")
            
            return "cuda"
        
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print(f"{check_icon(True)} Apple Silicon GPU (MPS) detected")
            print("   Note: Quantization not supported on MPS")
            return "mps"
        
        else:
            print(f"{check_icon(True)} Using CPU (no GPU detected)")
            print("   Note: Inference will be slower on CPU")
            print("   Recommended: Use smaller model (1.5B or 3B)")
            return "cpu"
    
    except ImportError:
        print(f"{check_icon(False)} torch not installed")
        return None


def download_model(model_id: str):
    """Pre-download model for faster first use."""
    print("\n" + "=" * 70)
    print(f"DOWNLOADING MODEL: {model_id}")
    print("=" * 70)
    
    print("\nThis will download the model to your HuggingFace cache.")
    print("This may take several minutes depending on model size and network speed.\n")
    
    # Check cache location
    hf_home = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    print(f"Cache directory: {hf_home}\n")
    
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        print("Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        print(f"{check_icon(True)} Tokenizer downloaded")
        
        print("\nDownloading model (this may take a while)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="cpu"  # Just download, don't load to GPU yet
        )
        print(f"{check_icon(True)} Model downloaded")
        
        # Clean up to free memory
        del model
        del tokenizer
        
        return True
    
    except Exception as e:
        print(f"\n{check_icon(False)} Failed to download model: {e}")
        print("\nTroubleshooting:")
        print("1. Check network connection")
        print("2. Verify model ID is correct: https://huggingface.co/models")
        print("3. If model is gated, set HF_TOKEN in .env")
        return False


def update_env(model_id: str):
    """Update .env file with HuggingFace configuration."""
    print("\n" + "=" * 70)
    print("UPDATING CONFIGURATION")
    print("=" * 70)
    
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    
    if not env_path.exists():
        print(f"\n{check_icon(False)} .env file not found")
        print(f"   Run: cp .env.example .env")
        return False
    
    # Read current .env
    env_content = env_path.read_text()
    
    # Update provider and model
    lines = env_content.split("\n")
    updated = False
    
    for i, line in enumerate(lines):
        if line.startswith("LLM_PROVIDER="):
            lines[i] = "LLM_PROVIDER=huggingface"
            updated = True
        elif line.startswith("LLM_MODEL="):
            lines[i] = f"LLM_MODEL={model_id}"
            updated = True
    
    if updated:
        env_path.write_text("\n".join(lines))
        print(f"{check_icon(True)} Updated .env:")
        print(f"   LLM_PROVIDER=huggingface")
        print(f"   LLM_MODEL={model_id}")
        return True
    else:
        print(f"{check_icon(False)} Could not update .env (LLM_PROVIDER or LLM_MODEL not found)")
        return False


def main():
    """Run setup workflow."""
    print("=" * 70)
    print("HUGGINGFACE PROVIDER SETUP")
    print("=" * 70)
    
    # Get model ID from args or use default
    model_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    print(f"\nModel: {model_id}")
    
    # Step 1: Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed: Could not install dependencies")
        return 1
    
    # Step 2: Check compute device
    device = check_device()
    if device is None:
        print("\n❌ Setup failed: Could not detect compute device")
        return 1
    
    # Step 3: Download model
    print("\nProceed with model download?")
    response = input("Download now? [Y/n]: ").strip().lower()
    
    if response in ["", "y", "yes"]:
        if not download_model(model_id):
            print("\n❌ Setup failed: Could not download model")
            return 1
    else:
        print("\nSkipping model download. Model will download on first use.")
    
    # Step 4: Update .env
    if not update_env(model_id):
        print("\n⚠️  Warning: Could not update .env automatically")
        print(f"\nManually add to .env:")
        print(f"   LLM_PROVIDER=huggingface")
        print(f"   LLM_MODEL={model_id}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    
    print(f"\n{check_icon(True)} HuggingFace provider ready")
    print(f"{check_icon(True)} Model: {model_id}")
    print(f"{check_icon(True)} Device: {device}")
    
    print("\nNext steps:")
    print("1. Verify setup: python scripts/verify_env.py")
    print("2. Run extraction: spec-parser device extract-blueprint <device_id>")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
