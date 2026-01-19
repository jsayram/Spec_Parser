# Environment Setup Guide

## Quick Start

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Configure for your use case:**

### Option A: Local Ollama (Default - No API Keys Needed)

```bash
# .env
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5-coder:7b
LLM_BASE_URL=http://localhost:11434
```

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama server
ollama serve

# Pull model (in another terminal)
ollama pull qwen2.5-coder:7b
```

### Option B: Anthropic Claude (Requires API Key)

```bash
# .env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx  # ← Add your key here
```

**Get API key:**
1. Sign up at https://console.anthropic.com
2. Create API key
3. Add to `.env` (never commit this!)

### Option C: OpenAI GPT-4o (Requires API Key)

```bash
# .env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxxxx  # ← Add your key here
```

**Get API key:**
1. Sign up at https://platform.openai.com
2. Create API key
3. Add to `.env` (never commit this!)

## Security Checklist

✅ **BEFORE committing code:**

1. Check `.env` is in `.gitignore`:
   ```bash
   grep "^\.env$" .gitignore  # Should return: .env
   ```

2. Verify no API keys in code:
   ```bash
   git grep -i "sk-ant-" "sk-proj-" "ANTHROPIC_API_KEY" "OPENAI_API_KEY"
   # Should return: (no matches in committed files)
   ```

3. Check cache databases are ignored:
   ```bash
   grep "\.db$" .gitignore  # Should return: *.db
   ```

4. Verify sensitive files not staged:
   ```bash
   git status
   # Should NOT show: .env, *.db files
   ```

## What's Sensitive (Never Commit)

❌ **API Keys:**
- `ANTHROPIC_API_KEY=sk-ant-...`
- `OPENAI_API_KEY=sk-...`

❌ **Correction Cache (contains proprietary spec data):**
- `config/llm_corrections.db`
- `config/llm_corrections_*.db`

❌ **Local paths:**
- Already handled by config (uses relative paths)

## What's Safe to Commit

✅ **Templates:**
- `.env.example` (no actual keys)

✅ **Default config:**
- `src/spec_parser/config.py` (reads from .env, no secrets hardcoded)

✅ **Code:**
- All Python files (use `os.getenv()` or pydantic-settings, never hardcode keys)

## Environment Variables Reference

### Required (No Defaults)

None - all have sensible defaults. API keys only needed for external providers.

### Optional (Override Defaults)

```bash
# LLM Settings
LLM_PROVIDER=ollama                    # Provider selection
LLM_MODEL=qwen2.5-coder:7b             # Model to use
LLM_BASE_URL=http://localhost:11434   # Ollama URL
LLM_TEMPERATURE=0.0                    # 0=deterministic, >0=creative
LLM_MAX_TOKENS=4000                    # Max response tokens
LLM_RATE_LIMIT=1.0                     # External API: req/sec
LLM_TIMEOUT=120                        # Timeout in seconds

# Cache Settings
LLM_CACHE_DIR=config                   # Cache directory
LLM_GLOBAL_CACHE=llm_corrections.db    # Cache filename

# API Keys (only for external providers)
ANTHROPIC_API_KEY=                     # Claude API key
OPENAI_API_KEY=                        # OpenAI API key

# OCR Settings
OCR_LANGUAGE=eng
OCR_DPI=300
OCR_CONFIDENCE_THRESHOLD=0.7

# Embedding Settings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
EMBEDDING_BATCH_SIZE=32

# Search Settings
SEARCH_TOP_K=5
HYBRID_SEARCH_ALPHA=0.5

# Performance
MAX_WORKERS=4
LOG_LEVEL=INFO
```

## How Config Loading Works

The system uses **pydantic-settings** which automatically:

1. Reads `.env` file from project root
2. Overrides with environment variables (if set)
3. Falls back to defaults in `config.py`

**Priority (highest to lowest):**
```
Environment Variables → .env file → config.py defaults
```

**Example:**
```python
# In config.py
llm_provider: str = "ollama"  # Default

# In .env
LLM_PROVIDER=anthropic  # Overrides default

# Or via environment
export LLM_PROVIDER=openai  # Overrides both
```

## Docker / Containers

For containerized deployments:

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Copy code (but NOT .env)
COPY src/ /app/src/
COPY setup.py /app/

# Environment variables via docker-compose or k8s secrets
ENV LLM_PROVIDER=ollama
ENV LLM_BASE_URL=http://ollama-service:11434

# API keys from secrets (not in image!)
# Set via: docker run -e ANTHROPIC_API_KEY=...
```

```yaml
# docker-compose.yml
services:
  spec-parser:
    build: .
    environment:
      - LLM_PROVIDER=anthropic
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}  # From host .env
    volumes:
      - ./config:/app/config  # Persist cache
```

## Troubleshooting

### "ANTHROPIC_API_KEY not set"

**Problem:** External API selected but no key provided

**Solution:**
```bash
# Check .env file
grep ANTHROPIC_API_KEY .env

# Should show:
# ANTHROPIC_API_KEY=sk-ant-...

# If empty, add your key
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env
```

### "Ollama connection failed"

**Problem:** Ollama not running or wrong URL

**Solution:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If fails, start Ollama
ollama serve

# Or check LLM_BASE_URL in .env matches Ollama address
```

### "Permission denied: config/llm_corrections.db"

**Problem:** Cache directory not writable

**Solution:**
```bash
# Create config directory
mkdir -p config

# Fix permissions
chmod 755 config
```

---

**Remember:** The `.env` file is your personal configuration. Never commit it to version control!
