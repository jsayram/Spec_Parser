# HuggingFace Provider Setup Guide

Direct local inference without Ollama server - ideal for restricted environments.

## Overview

The HuggingFace provider loads models directly using the `transformers` library. No server needed - models run directly in your Python process.

**Advantages:**
- ✅ No server installation (works anywhere Python runs)
- ✅ Works in Docker, containers, air-gapped environments
- ✅ Fine control over device placement (CPU/GPU/MPS)
- ✅ Quantization support (8-bit, 4-bit for memory efficiency)
- ✅ Direct access to HuggingFace model hub

**Disadvantages:**
- ❌ Higher memory usage (model loaded in Python process)
- ❌ Slower first load (downloads model on first use)
- ❌ Requires PyTorch + transformers dependencies

---

## Quick Start

### 1. Install Dependencies

```bash
# Minimum (CPU-only)
pip install transformers torch

# With GPU support (NVIDIA CUDA)
pip install transformers torch --index-url https://download.pytorch.org/whl/cu121

# With Apple Silicon GPU (MPS)
pip install transformers torch  # MPS included by default on macOS

# With quantization support (8-bit/4-bit)
pip install transformers torch bitsandbytes
```

### 2. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Use HuggingFace provider
LLM_PROVIDER=huggingface

# Choose model (HuggingFace model ID)
LLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct

# Standard settings
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=4000

# Optional: Custom cache directory
# HF_HOME=/path/to/model/cache

# Optional: HuggingFace token (only for gated models)
# HF_TOKEN=hf_...
```

### 3. Run Extraction

```bash
# Verify setup
python scripts/verify_env.py

# Extract blueprint
spec-parser device extract-blueprint <device_id>
```

---

## Supported Models

### Recommended Models

#### **Qwen2.5-Coder** (Best for code/spec extraction)

| Model | Size | VRAM | Speed | Quality |
|-------|------|------|-------|---------|
| `Qwen/Qwen2.5-Coder-1.5B-Instruct` | 1.5B | 3GB | Fast | Good |
| `Qwen/Qwen2.5-Coder-3B-Instruct` | 3B | 6GB | Medium | Better |
| `Qwen/Qwen2.5-Coder-7B-Instruct` | 7B | 14GB | Slow | Best |

#### **Phi-3.5** (Microsoft, compact)

| Model | Size | VRAM | Speed | Quality |
|-------|------|------|-------|---------|
| `microsoft/Phi-3.5-mini-instruct` | 3.8B | 8GB | Medium | Good |

#### **Any Chat Model**

Any HuggingFace model that supports:
- `AutoModelForCausalLM`
- `apply_chat_template()` method

Examples:
- `meta-llama/Llama-3.2-3B-Instruct`
- `mistralai/Mistral-7B-Instruct-v0.3`
- `google/gemma-2-2b-it`

---

## Device Selection

The provider auto-detects the best device:

1. **NVIDIA GPU (CUDA)** - If `torch.cuda.is_available()`
2. **Apple Silicon GPU (MPS)** - If `torch.backends.mps.is_available()`
3. **CPU** - Fallback

### Override Device

Edit `src/spec_parser/llm/llm_interface.py`:

```python
provider = HuggingFaceProvider(
    model=model,
    device="cuda",  # Force CUDA
    # device="cpu",  # Force CPU
    # device="mps",  # Force Apple Silicon
    **kwargs
)
```

---

## Quantization (Memory Optimization)

Reduce memory usage with 8-bit or 4-bit quantization:

### 8-bit (Half memory, minimal quality loss)

```python
provider = HuggingFaceProvider(
    model="Qwen/Qwen2.5-Coder-7B-Instruct",
    device="auto",
    load_in_8bit=True  # 7B model: 14GB → 7GB VRAM
)
```

### 4-bit (Quarter memory, small quality loss)

```python
provider = HuggingFaceProvider(
    model="Qwen/Qwen2.5-Coder-7B-Instruct",
    device="auto",
    load_in_4bit=True  # 7B model: 14GB → 3.5GB VRAM
)
```

**Requirements:**
```bash
pip install bitsandbytes
```

**Note:** Only works with CUDA GPUs (not MPS or CPU)

---

## Model Caching

Models are downloaded once and cached for reuse.

### Default Cache Location

- **Linux/macOS:** `~/.cache/huggingface/hub/`
- **Windows:** `C:\Users\<username>\.cache\huggingface\hub\`

### Custom Cache Directory

Set environment variable:

```bash
# In .env
HF_HOME=/data/models/huggingface

# Or export in shell
export HF_HOME=/data/models/huggingface
```

### Pre-download Models

Download before first use:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "Qwen/Qwen2.5-Coder-7B-Instruct"

# Download model + tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
```

Or use CLI:

```bash
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct
```

---

## Air-Gapped / Offline Usage

For systems without internet access:

### 1. Download Model on Connected Machine

```bash
# Install huggingface-cli
pip install huggingface-hub

# Download model
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct \
    --local-dir ./qwen-model \
    --local-dir-use-symlinks False
```

### 2. Transfer to Air-Gapped Machine

```bash
# Copy entire directory
scp -r ./qwen-model user@airgapped:/data/models/
```

### 3. Configure Local Path

Edit `.env`:

```bash
LLM_PROVIDER=huggingface
LLM_MODEL=/data/models/qwen-model  # Local path instead of HF ID
```

---

## Gated Models

Some models require HuggingFace access tokens:

### 1. Get Token

Visit: https://huggingface.co/settings/tokens

Create token with `read` permission.

### 2. Configure Token

```bash
# In .env
HF_TOKEN=hf_abcdefghijklmnopqrstuvwxyz123456
```

Or use CLI:

```bash
huggingface-cli login
```

---

## Troubleshooting

### Out of Memory (OOM)

**Symptoms:**
```
RuntimeError: CUDA out of memory
```

**Solutions:**

1. **Use smaller model:**
   ```bash
   LLM_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct  # 6GB instead of 14GB
   ```

2. **Enable quantization:**
   ```python
   load_in_8bit=True  # Half memory
   ```

3. **Use CPU (slower but works):**
   ```python
   device="cpu"
   ```

### Slow Generation

**Symptoms:**
- Takes >1 minute per extraction

**Solutions:**

1. **Use GPU:**
   ```bash
   # Check GPU availability
   python -c "import torch; print(torch.cuda.is_available())"
   ```

2. **Use smaller model:**
   ```bash
   LLM_MODEL=Qwen/Qwen2.5-Coder-1.5B-Instruct  # 10x faster
   ```

3. **Reduce max_tokens:**
   ```bash
   LLM_MAX_TOKENS=2000  # Faster generation
   ```

### Model Not Found

**Symptoms:**
```
OSError: Qwen/Qwen2.5-Coder-7B-Instruct does not exist
```

**Solutions:**

1. **Check model ID:**
   - Visit: https://huggingface.co/models
   - Verify exact model name

2. **Check network access:**
   ```bash
   curl https://huggingface.co
   ```

3. **Use gated model token:**
   ```bash
   HF_TOKEN=hf_...
   ```

### ImportError: No module named 'transformers'

**Solution:**
```bash
pip install transformers torch
```

---

## Performance Comparison

| Provider | Setup | First Run | Cached Run | Memory | Pros | Cons |
|----------|-------|-----------|------------|--------|------|------|
| **HuggingFace** | Install deps | 30s (download) | 10s (load) | 14GB | No server, works anywhere | High memory |
| **Ollama** | Install server | 5s | 0.1s | 4GB | Fast, low memory | Requires server |
| **Anthropic** | Get API key | 2s | 2s | 0MB | Fast, cloud | Costs money |
| **OpenAI** | Get API key | 2s | 2s | 0MB | Fast, cloud | Costs money |

**Recommendation:**
- **Development:** Ollama (fast iteration)
- **Production:** Anthropic/OpenAI (quality + speed)
- **Restricted/Air-gapped:** HuggingFace (works anywhere)

---

## Example Configurations

### Minimal (CPU, 1.5B model)

```bash
LLM_PROVIDER=huggingface
LLM_MODEL=Qwen/Qwen2.5-Coder-1.5B-Instruct
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=2000
```

**Memory:** ~3GB RAM  
**Speed:** ~60s per device  
**Quality:** Good for simple specs

### Balanced (GPU, 3B model)

```bash
LLM_PROVIDER=huggingface
LLM_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=4000
```

**Memory:** ~6GB VRAM  
**Speed:** ~15s per device  
**Quality:** Better for complex specs

### High Quality (GPU, 7B model with 8-bit)

```bash
LLM_PROVIDER=huggingface
LLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=4000
```

**Memory:** ~7GB VRAM (with 8-bit quantization)  
**Speed:** ~30s per device  
**Quality:** Best for production

---

## Docker Deployment

```dockerfile
FROM python:3.11-slim

# Install dependencies
RUN pip install transformers torch bitsandbytes

# Copy application
COPY . /app
WORKDIR /app

# Set cache directory
ENV HF_HOME=/app/.cache/huggingface

# Pre-download model (optional, for faster startup)
RUN python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; \
    AutoTokenizer.from_pretrained('Qwen/Qwen2.5-Coder-3B-Instruct'); \
    AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-Coder-3B-Instruct')"

# Configure environment
ENV LLM_PROVIDER=huggingface
ENV LLM_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct

CMD ["spec-parser", "device", "extract-blueprint", "--help"]
```

---

## Next Steps

1. **Verify setup:**
   ```bash
   python scripts/verify_env.py
   ```

2. **Test generation:**
   ```bash
   python examples/llm_correction_workflow.py
   ```

3. **Run extraction:**
   ```bash
   spec-parser device extract-blueprint <device_id>
   ```

4. **Review results:**
   ```bash
   python examples/llm_correction_workflow.py
   ```

---

## Support

- **HuggingFace Docs:** https://huggingface.co/docs/transformers
- **Model Selection:** https://huggingface.co/models
- **GPU Support:** https://pytorch.org/get-started/locally/
