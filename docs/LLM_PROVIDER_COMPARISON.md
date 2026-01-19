# LLM Provider Comparison

Quick reference for choosing the right LLM provider for your use case.

## Quick Decision Matrix

| Your Situation | Recommended Provider |
|----------------|---------------------|
| **Can't install Ollama** (restricted environment, Docker, air-gapped) | **HuggingFace** |
| **Development/Iteration** (need fast responses) | **Ollama** |
| **Production/Quality** (willing to pay for best results) | **Anthropic (Claude)** |
| **Budget-conscious** (free local inference) | **HuggingFace or Ollama** |
| **Low VRAM** (<8GB GPU or CPU only) | **HuggingFace 1.5B/3B models** |
| **High VRAM** (>16GB GPU) | **HuggingFace 7B or Ollama** |

---

## Provider Comparison Table

| Feature | HuggingFace | Ollama | Anthropic | OpenAI |
|---------|-------------|--------|-----------|--------|
| **Installation** | `pip install` | Server install | API key only | API key only |
| **Dependencies** | PyTorch + transformers | Ollama binary | `pip install anthropic` | `pip install openai` |
| **Server Required** | ❌ No | ✅ Yes | ❌ No (cloud) | ❌ No (cloud) |
| **First Run** | 30s (download) | 5s (if model pulled) | 2s | 2s |
| **Cached Run** | 10s (model load) | 0.1s | 2s | 2s |
| **Cost** | Free | Free | ~$3 per 1M tokens | ~$2.50 per 1M tokens |
| **Network Required** | First use only | First use only | Always | Always |
| **Works Offline** | ✅ After download | ✅ After download | ❌ No | ❌ No |
| **Memory (7B model)** | 14GB VRAM / 28GB RAM | 4GB RAM | 0MB (cloud) | 0MB (cloud) |
| **Memory (3B model)** | 6GB VRAM / 12GB RAM | 2GB RAM | N/A | N/A |
| **GPU Acceleration** | ✅ CUDA, MPS | ✅ CUDA, Metal | ✅ (cloud) | ✅ (cloud) |
| **Quantization** | ✅ 8-bit, 4-bit | ✅ Built-in | N/A | N/A |
| **Air-gapped** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Docker/Container** | ✅ Easy | ⚠️ Requires server setup | ✅ Easy | ✅ Easy |
| **Quality (7B)** | Good | Good | Excellent | Excellent |
| **Quality (3B)** | Fair | Fair | N/A | N/A |
| **Quality (1.5B)** | Fair | N/A | N/A | N/A |
| **Speed (GPU)** | Fast (10-30s) | Very fast (0.1s) | Fast (2s) | Fast (2s) |
| **Speed (CPU)** | Slow (60s+) | Slow (30s+) | Fast (2s) | Fast (2s) |
| **Rate Limiting** | None | None | 60 req/min | 60 req/min |
| **Best For** | Restricted environments, offline, containers | Development, fast iteration | Production, quality | Production, quality |

---

## Model Selection Guide

### HuggingFace Models

| Model | Size | VRAM | RAM (CPU) | Quality | Speed (GPU) | Speed (CPU) |
|-------|------|------|-----------|---------|-------------|-------------|
| `Qwen/Qwen2.5-Coder-1.5B-Instruct` | 1.5B | 3GB | 6GB | Fair | 5s | 30s |
| `Qwen/Qwen2.5-Coder-3B-Instruct` | 3B | 6GB | 12GB | Good | 15s | 60s |
| `Qwen/Qwen2.5-Coder-7B-Instruct` | 7B | 14GB | 28GB | Best | 30s | 120s+ |
| `microsoft/Phi-3.5-mini-instruct` | 3.8B | 8GB | 16GB | Good | 20s | 80s |

**With 8-bit quantization:** Half the VRAM (e.g., 7B: 14GB → 7GB)  
**With 4-bit quantization:** Quarter the VRAM (e.g., 7B: 14GB → 3.5GB)

### Ollama Models

| Model | Size | RAM | Quality | Speed |
|-------|------|-----|---------|-------|
| `qwen2.5-coder:1.5b` | 1.5B | 2GB | Fair | Very fast |
| `qwen2.5-coder:3b` | 3B | 2GB | Good | Fast |
| `qwen2.5-coder:7b` | 7B | 4GB | Best | Medium |
| `llama3.2:3b` | 3B | 2GB | Good | Fast |

### Cloud Models

| Provider | Model | Quality | Cost (per 1M tokens) |
|----------|-------|---------|---------------------|
| Anthropic | `claude-3-5-sonnet-20241022` | Excellent | ~$3 |
| OpenAI | `gpt-4o` | Excellent | ~$2.50 |

---

## Setup Instructions

### HuggingFace

```bash
# Quick setup
python scripts/setup_huggingface.py

# Or manual
pip install transformers torch
echo "LLM_PROVIDER=huggingface" >> .env
echo "LLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct" >> .env
```

**Docs:** [docs/HUGGINGFACE_SETUP.md](HUGGINGFACE_SETUP.md)

### Ollama

```bash
# Install: https://ollama.com/download
ollama serve
ollama pull qwen2.5-coder:7b

# Configure
echo "LLM_PROVIDER=ollama" >> .env
echo "LLM_MODEL=qwen2.5-coder:7b" >> .env
```

### Anthropic

```bash
pip install anthropic
echo "LLM_PROVIDER=anthropic" >> .env
echo "LLM_MODEL=claude-3-5-sonnet-20241022" >> .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

### OpenAI

```bash
pip install openai
echo "LLM_PROVIDER=openai" >> .env
echo "LLM_MODEL=gpt-4o" >> .env
echo "OPENAI_API_KEY=sk-..." >> .env
```

---

## Use Case Recommendations

### Scenario: Air-gapped / Restricted Environment

**Problem:** Can't install Ollama server, no internet after initial setup

**Solution:** HuggingFace + pre-downloaded model

```bash
# On connected machine
pip install transformers torch
python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; \
    AutoTokenizer.from_pretrained('Qwen/Qwen2.5-Coder-3B-Instruct'); \
    AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-Coder-3B-Instruct')"

# Transfer ~/.cache/huggingface to air-gapped machine
# Configure .env with LLM_PROVIDER=huggingface
```

**Why:** No server required, works completely offline after download

---

### Scenario: Docker Container

**Problem:** Need portable container without external servers

**Solution:** HuggingFace with pre-baked model

```dockerfile
FROM python:3.11-slim
RUN pip install transformers torch
COPY . /app
WORKDIR /app

# Pre-download model at build time
RUN python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; \
    AutoTokenizer.from_pretrained('Qwen/Qwen2.5-Coder-3B-Instruct'); \
    AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-Coder-3B-Instruct')"

ENV LLM_PROVIDER=huggingface
ENV LLM_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct
```

**Why:** Self-contained, no external dependencies

---

### Scenario: Development Iteration

**Problem:** Need fast feedback loop for testing

**Solution:** Ollama with cached responses

```bash
ollama serve
ollama pull qwen2.5-coder:7b
echo "LLM_PROVIDER=ollama" >> .env
```

**Why:** 0.1s response time after first run (vs 10-30s for HuggingFace)

---

### Scenario: Production Deployment

**Problem:** Need highest quality, willing to pay

**Solution:** Anthropic Claude with correction cache

```bash
echo "LLM_PROVIDER=anthropic" >> .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

**Why:** Best quality, fast (2s), no infrastructure to maintain

**Cost:** ~$3 per device (25 extractions × 1000 tokens × $3/1M)

---

### Scenario: Low VRAM (<8GB GPU or CPU only)

**Problem:** Can't fit 7B model in memory

**Solution:** HuggingFace with smaller model or quantization

```bash
# Option 1: Smaller model (3B)
echo "LLM_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct" >> .env

# Option 2: Quantization (in llm_interface.py)
provider = HuggingFaceProvider(
    model="Qwen/Qwen2.5-Coder-7B-Instruct",
    load_in_8bit=True  # 14GB → 7GB VRAM
)
```

**Why:** Fits in available memory while maintaining reasonable quality

---

### Scenario: High Volume Processing

**Problem:** Need to process 100+ devices

**Solution:** HuggingFace (free) or Ollama (fast), with correction cache

```bash
# Use correction cache to avoid re-processing similar messages
echo "LLM_CACHE_DIR=config" >> .env
echo "LLM_GLOBAL_CACHE=llm_corrections.db" >> .env
```

**Why:** 
- After first few devices, cache hit rate >80%
- Cache responses are 100-200x faster (0.001s vs 10s)
- Free (no API costs)

**Cost:** $0 for HuggingFace/Ollama vs ~$300 for Claude (100 devices × $3/device)

---

## Performance Comparison

### First Device (No Cache)

| Provider | Model | Time | Quality | Cost |
|----------|-------|------|---------|------|
| HuggingFace (GPU) | Qwen2.5-Coder-7B | 8 min | Good | $0 |
| HuggingFace (GPU) | Qwen2.5-Coder-3B | 6 min | Good | $0 |
| HuggingFace (CPU) | Qwen2.5-Coder-3B | 30 min | Good | $0 |
| Ollama | qwen2.5-coder:7b | 5 min | Good | $0 |
| Anthropic | claude-3-5-sonnet | 1 min | Excellent | $3 |
| OpenAI | gpt-4o | 1 min | Excellent | $2.50 |

*Times assume 25 extractions per device, 1000 tokens per extraction*

### Subsequent Devices (80% Cache Hit)

All providers: **~30s** (cache lookups dominate, LLM calls minimal)

**Conclusion:** After building correction cache with first few devices, all providers perform similarly. Choose based on setup constraints, not speed.

---

## Troubleshooting

### "Cannot connect to Ollama"

**Solution:** Use HuggingFace instead (no server needed)

```bash
python scripts/setup_huggingface.py
```

### "CUDA out of memory"

**Solution:** Use smaller model or quantization

```bash
echo "LLM_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct" >> .env
```

### "transformers not installed"

**Solution:** Install dependencies

```bash
pip install transformers torch
```

### "Slow inference on CPU"

**Solution:** Use smaller model or switch to cloud provider

```bash
# Option 1: Smaller model
echo "LLM_MODEL=Qwen/Qwen2.5-Coder-1.5B-Instruct" >> .env

# Option 2: Cloud provider
echo "LLM_PROVIDER=anthropic" >> .env
```

---

## Summary

**Choose HuggingFace if:**
- ✅ Can't install Ollama server
- ✅ Need offline/air-gapped operation
- ✅ Running in Docker/containers
- ✅ Want zero external dependencies

**Choose Ollama if:**
- ✅ Need fastest iteration speed
- ✅ Can install server locally
- ✅ Development/testing focused

**Choose Anthropic/OpenAI if:**
- ✅ Need best quality
- ✅ Willing to pay for convenience
- ✅ Production deployment
- ✅ Don't want to manage infrastructure
