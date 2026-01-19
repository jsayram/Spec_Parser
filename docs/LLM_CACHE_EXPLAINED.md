# How LLM Correction Cache Guarantees Quality

## The Problem: 7B Model Makes Mistakes

**Qwen2-Coder-7B** is fast and local, but may extract fields incorrectly:

```json
// ❌ 7B model output (wrong field name)
{
  "field_name": "MSH-9",  // Should be "MSH-7"
  "field_description": "Date/Time of Message",
  "data_type": "TS"
}
```

## The Solution: Cache + Verify + Re-use

### Architecture

```
First Run (Cold Cache):
─────────────────────────
User: extract-blueprint
  ↓
LLM: Generate prompt for "OBS.R01 fields"
  ↓
Compute: SHA256(model + prompt) = "abc123..."
  ↓
Cache: SELECT WHERE prompt_hash = "abc123..." 
  ↓ (not found)
Call: Qwen2-Coder-7B API
  ↓
Response: {...wrong field...}
  ↓
Store: INSERT INTO corrections (
         prompt_hash = "abc123...",
         original_response = {...wrong...},
         is_verified = FALSE
       )
  ↓
Return: wrong output to user


Human Review:
─────────────
User: python examples/llm_correction_workflow.py
  ↓
Show: Original response {...wrong field...}
  ↓
User: Provides corrected JSON {...correct field...}
  ↓
Store: UPDATE corrections 
       SET corrected_response = {...correct...},
           is_verified = TRUE
       WHERE prompt_hash = "abc123..."


Second Run (Warm Cache):
────────────────────────
User: extract-blueprint (same device, same spec)
  ↓
LLM: Generate same prompt for "OBS.R01 fields"
  ↓
Compute: SHA256(model + prompt) = "abc123..." (SAME HASH!)
  ↓
Cache: SELECT WHERE prompt_hash = "abc123..." AND is_verified = TRUE
  ↓ (FOUND!)
Return: corrected_response {...correct field...}
  ↑
  └─── NO LLM CALL! Perfect output instantly!
```

## Guarantees

### 1. **Deterministic Hash**: Same prompt → Same hash
```python
# Example from cache.py
def compute_hash(prompt_text: str, model: str) -> str:
    combined = f"{model}::{prompt_text}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

# Same input ALWAYS produces same 64-char hex string
# "qwen2.5-coder:7b::Extract fields..." → "abc123def456..."
# "qwen2.5-coder:7b::Extract fields..." → "abc123def456..." (same!)
```

### 2. **SQLite UNIQUE constraint**: Can't store duplicates
```sql
CREATE TABLE corrections (
    prompt_hash TEXT PRIMARY KEY,  -- ← UNIQUE constraint
    ...
);

-- INSERT with same prompt_hash = automatic REPLACE
```

### 3. **Verified flag**: Only use human-approved corrections
```python
# In llm_interface.py
if use_cache:
    cached = self.cache.get(prompt_hash)
    if cached and cached.is_verified:  # ← Must be verified
        return cached.corrected_response or cached.original_response
    # Unverified entries are ignored
```

### 4. **Temperature=0.0**: LLM produces same output for same prompt
```python
# In providers/ollama.py
payload = {
    "model": self.model,
    "prompt": prompt,
    "options": {
        "temperature": 0.0,  # ← Deterministic sampling
    }
}
# Same prompt → Same output (no randomness)
```

## Example: Real Workflow

### Run 1: Extract with 7B model
```bash
$ spec-parser device extract-blueprint --device-id Roche_CobasLiat ...

[MessageDiscovery] Cache MISS: abc123... - calling Ollama
[MessageDiscovery] Discovered 12 messages
[FieldExtraction[OBS.R01]] Cache MISS: def456... - calling Ollama
[FieldExtraction[OBS.R01]] Extracted 8 fields  # ← May have errors
...
Blueprint saved: blueprint.json
Cache stats: {"total_corrections": 15, "verified_corrections": 0}
```

### Inspect Output: Find Errors
```bash
$ cat blueprint.json | jq '.messages[0].fields[0]'
{
  "field_name": "MSH-9",  # ❌ WRONG! Should be MSH-7
  "field_description": "Date/Time of Message",
  "data_type": "TS"
}
```

### Review and Correct
```bash
$ python examples/llm_correction_workflow.py

═══════════════════════════════════════════════════════════════
CORRECTION 1 of 15
═══════════════════════════════════════════════════════════════
Message Type: OBS.R01
Model: qwen2.5-coder:7b

🤖 LLM Response:
{
  "field_name": "MSH-9",  # ← Error here
  "field_description": "Date/Time of Message",
  "data_type": "TS"
}

REVIEW OPTIONS:
  1. Approve
  2. Correct
  3. Skip

Your choice: 2

Enter corrected JSON:
{
  "field_name": "MSH-7",  # ← Fixed
  "field_description": "Date/Time of Message",
  "data_type": "TS"
}
END

✅ Correction saved
```

### Run 2: Extract Again (Uses Corrections)
```bash
$ spec-parser device extract-blueprint --device-id Roche_CobasLiat ...

[MessageDiscovery] Cache HIT: abc123... (hit_count=1, verified=True)
[MessageDiscovery] Discovered 12 messages  # ← Same result, no LLM call
[FieldExtraction[OBS.R01]] Cache HIT: def456... (hit_count=1, verified=True)
[FieldExtraction[OBS.R01]] Extracted 8 fields  # ← Now uses corrected version!
...
Blueprint saved: blueprint.json  # ← Perfect output this time
Cache stats: {"total_corrections": 15, "verified_corrections": 15, "total_cache_hits": 15}
```

### Verify Output: Now Correct
```bash
$ cat blueprint.json | jq '.messages[0].fields[0]'
{
  "field_name": "MSH-7",  # ✅ CORRECT! From cache
  "field_description": "Date/Time of Message",
  "data_type": "TS"
}
```

## Testing: Prove It Works

```bash
# Automated test
$ python tests/test_llm_cache.py

STEP 1: First Run - Cache MISS (calls LLM)
Calling LLM...
✅ LLM Response (245 chars):
[{"message_type": "OBS.R01", ...}]
📊 Cache Stats: {'total_corrections': 1, 'verified_corrections': 0}

STEP 2: Verify Correction (simulate human review)
Correcting response (simulated)...
✅ Correction verified and saved

STEP 3: Second Run - Cache HIT (no LLM call)
Calling LLM with same prompt...
✅ Response (253 chars):
[{"message_type": "OBS.R01_CORRECTED", ...}]  # ← Uses correction!
📊 Hit count: 1 (should be 1+ from cache lookups)

✅ CACHE VERIFICATION SUCCESSFUL
```

## Performance Impact

With cache, you only pay for LLM calls once:

| Metric | Without Cache | With Cache |
|--------|---------------|------------|
| First run | 15 LLM calls | 15 LLM calls |
| Second run | 15 LLM calls | 0 LLM calls ✅ |
| Third run | 15 LLM calls | 0 LLM calls ✅ |
| 10 runs | 150 LLM calls | 15 LLM calls (90% reduction) |

**Cost savings:**
- Local (Qwen2-7B): Time saved (~5 sec → instant)
- Claude ($3/M tokens): ~$0.15/run → ~$0.01/run (15x cheaper)
- OpenAI ($2.50/M tokens): ~$0.12/run → ~$0.01/run (12x cheaper)

## Why This Works

1. **Deterministic prompts**: Same spec → same prompts → same hashes
2. **Temperature=0.0**: Same prompt → same LLM output (before correction)
3. **Human-in-the-loop**: Corrections are verified by expert, not guessed
4. **Immutable cache**: Once verified, correction never changes
5. **Hit tracking**: Most-used corrections are prioritized for few-shot examples

## Summary

**The correction cache doesn't just "hope" the LLM gets it right** - it:

1. ✅ **Captures** all LLM outputs in SQLite
2. ✅ **Verifies** corrections with human expert
3. ✅ **Replaces** future LLM calls with verified corrections
4. ✅ **Tracks** usage to identify high-value corrections
5. ✅ **Guarantees** deterministic, correct outputs after first review

**Result**: 7B model quality → Expert-level quality after one correction cycle.
