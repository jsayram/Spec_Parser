#!/usr/bin/env python3
"""
Test script to verify LLM correction cache is working correctly.

This script demonstrates:
1. First run: Cache MISS → calls LLM
2. Verify correction manually
3. Second run: Cache HIT → returns cached result without LLM call

Usage:
    python test_llm_cache.py
"""

from pathlib import Path
from spec_parser.llm import LLMInterface, CorrectionCache
from spec_parser.llm.llm_interface import create_llm_provider
from loguru import logger

logger.remove()  # Remove default handler
logger.add(lambda msg: print(msg, end=""), format="{message}")


def test_cache_workflow():
    """Test complete cache workflow: miss → verify → hit."""
    
    print("=" * 70)
    print("LLM CACHE VERIFICATION TEST")
    print("=" * 70)
    
    # Initialize cache
    cache_path = Path("config/llm_corrections_test.db")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        cache_path.unlink()  # Start fresh
    
    cache = CorrectionCache(cache_path)
    
    # Test prompt
    test_prompt = """Extract POCT1-A message types from this text:

The device supports OBS.R01 for observation results and QCN.J01 for quality control.

Return JSON array: [{"message_type": "...", "direction": "..."}]"""
    
    print("\n" + "=" * 70)
    print("STEP 1: First Run - Cache MISS (calls LLM)")
    print("=" * 70)
    
    # Initialize LLM
    try:
        llm = LLMInterface(cache_path=cache_path)
    except Exception as e:
        print(f"\n❌ Failed to initialize LLM: {e}")
        print("\nFor Ollama: Run 'ollama serve' and 'ollama pull qwen2.5-coder:7b'")
        print("For external API: Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        return False
    
    # First call - should hit LLM
    print(f"\nPrompt: {test_prompt[:100]}...")
    print("\nCalling LLM...")
    
    try:
        response1 = llm.generate(
            prompt=test_prompt,
            device_id="TEST_DEVICE",
            message_type="test_discovery"
        )
    except Exception as e:
        print(f"\n❌ LLM call failed: {e}")
        return False
    
    print(f"\n✅ LLM Response ({len(response1)} chars):")
    print(response1[:300] + "..." if len(response1) > 300 else response1)
    
    # Check cache was populated
    stats = cache.stats()
    print(f"\n📊 Cache Stats: {stats}")
    assert stats["total_corrections"] == 1, "Cache should have 1 entry"
    assert stats["verified_corrections"] == 0, "Entry should be unverified"
    
    print("\n" + "=" * 70)
    print("STEP 2: Verify Correction (simulate human review)")
    print("=" * 70)
    
    # Get the unverified record
    prompt_hash = CorrectionCache.compute_hash(test_prompt, llm.provider.model)
    record = cache.get(prompt_hash, increment_hit=False)
    
    print(f"\nOriginal response: {record.original_response[:200]}...")
    
    # Simulate human correction
    corrected_response = record.original_response.replace("OBS.R01", "OBS.R01_CORRECTED")
    
    print(f"\nCorrecting response (simulated)...")
    print(f"Corrected: {corrected_response[:200]}...")
    
    cache.mark_verified(prompt_hash, corrected_response=corrected_response)
    
    # Verify correction was saved
    verified_record = cache.get(prompt_hash, increment_hit=False)
    assert verified_record.is_verified, "Should be verified"
    assert verified_record.corrected_response == corrected_response, "Should have correction"
    
    print(f"\n✅ Correction verified and saved")
    
    print("\n" + "=" * 70)
    print("STEP 3: Second Run - Cache HIT (no LLM call)")
    print("=" * 70)
    
    # Second call with same prompt - should hit cache
    print(f"\nCalling LLM with same prompt...")
    print("(Watch for 'Cache HIT' message - no actual LLM call should happen)")
    
    response2 = llm.generate(
        prompt=test_prompt,
        device_id="TEST_DEVICE",
        message_type="test_discovery"
    )
    
    print(f"\n✅ Response ({len(response2)} chars):")
    print(response2[:300] + "..." if len(response2) > 300 else response2)
    
    # Verify it used the corrected response
    assert response2 == corrected_response, "Should return corrected response"
    assert "Cache HIT" in str(response2) or response2 == corrected_response, "Should be from cache"
    
    # Check hit count increased
    final_record = cache.get(prompt_hash, increment_hit=False)
    print(f"\n📊 Hit count: {final_record.hit_count} (should be 1+ from cache lookups)")
    
    # Final stats
    final_stats = cache.stats()
    print(f"\n📊 Final Cache Stats: {final_stats}")
    
    print("\n" + "=" * 70)
    print("✅ CACHE VERIFICATION SUCCESSFUL")
    print("=" * 70)
    print("\nKey observations:")
    print("1. ✅ First call: Cache MISS → LLM was called")
    print("2. ✅ Correction: Human verification saved to cache")
    print("3. ✅ Second call: Cache HIT → Corrected response returned without LLM")
    print(f"4. ✅ Hit tracking: {final_record.hit_count} cache hits recorded")
    
    # Cleanup
    cache_path.unlink()
    print(f"\n🧹 Cleaned up test cache: {cache_path}")
    
    return True


def inspect_cache(cache_path: Path):
    """Inspect cache contents."""
    if not cache_path.exists():
        print(f"❌ Cache not found: {cache_path}")
        return
    
    cache = CorrectionCache(cache_path)
    stats = cache.stats()
    
    print("\n" + "=" * 70)
    print("CACHE INSPECTION")
    print("=" * 70)
    print(f"\nCache file: {cache_path}")
    print(f"Stats: {stats}")
    
    # Get all corrections
    import sqlite3
    with sqlite3.connect(cache_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM corrections ORDER BY created_at DESC")
        rows = cursor.fetchall()
    
    print(f"\n{len(rows)} correction(s) in cache:\n")
    
    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['prompt_hash'][:8]}... (hit_count={row['hit_count']})")
        print(f"   Model: {row['model']}")
        print(f"   Device: {row['device_id']}")
        print(f"   Message: {row['message_type']}")
        print(f"   Verified: {bool(row['is_verified'])}")
        print(f"   Created: {row['created_at']}")
        print(f"   Prompt: {row['prompt_text'][:100]}...")
        print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "inspect":
        # Inspect production cache
        cache_path = Path("config/llm_corrections.db")
        inspect_cache(cache_path)
    else:
        # Run test
        success = test_cache_workflow()
        sys.exit(0 if success else 1)
