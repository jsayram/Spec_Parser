"""
Example: Real-world correction workflow for POCT1-A extraction.

This demonstrates the complete cycle:
1. Run extraction with 7B model (may have errors)
2. Review LLM outputs
3. Correct bad outputs
4. Re-run extraction (uses corrections automatically)
"""

from pathlib import Path
import json
from spec_parser.llm import CorrectionCache
from loguru import logger


def review_and_correct_workflow():
    """Interactive workflow to review and correct LLM outputs."""
    
    cache_path = Path("config/llm_corrections.db")
    if not cache_path.exists():
        print(f"❌ No cache found at {cache_path}")
        print("Run 'device extract-blueprint' first to generate LLM outputs")
        return
    
    cache = CorrectionCache(cache_path)
    
    print("=" * 70)
    print("LLM CORRECTION REVIEW WORKFLOW")
    print("=" * 70)
    
    # Get cache stats
    stats = cache.stats()
    print(f"\n📊 Cache Stats:")
    print(f"   Total corrections: {stats['total_corrections']}")
    print(f"   Verified: {stats['verified_corrections']}")
    print(f"   Unverified: {stats['total_corrections'] - stats['verified_corrections']}")
    print(f"   Total cache hits: {stats['total_cache_hits']}")
    
    # Get unverified corrections
    import sqlite3
    with sqlite3.connect(cache_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT * FROM corrections 
            WHERE is_verified = 0 
            ORDER BY created_at DESC
        """)
        unverified = cursor.fetchall()
    
    if not unverified:
        print("\n✅ All corrections are verified!")
        return
    
    print(f"\n📋 {len(unverified)} unverified correction(s) pending review:")
    print()
    
    # Review each unverified correction
    for i, row in enumerate(unverified, 1):
        print("=" * 70)
        print(f"CORRECTION {i} of {len(unverified)}")
        print("=" * 70)
        
        print(f"\nDevice: {row['device_id']}")
        print(f"Message Type: {row['message_type']}")
        print(f"Model: {row['model']}")
        print(f"Created: {row['created_at']}")
        print(f"Prompt Hash: {row['prompt_hash'][:16]}...")
        
        print(f"\n📝 Prompt (first 300 chars):")
        print(row['prompt_text'][:300] + "...")
        
        print(f"\n🤖 LLM Response:")
        response = row['original_response']
        
        # Try to pretty-print if JSON
        try:
            parsed = json.loads(response)
            print(json.dumps(parsed, indent=2)[:500])
            if len(json.dumps(parsed)) > 500:
                print("... (truncated)")
        except:
            print(response[:500])
            if len(response) > 500:
                print("... (truncated)")
        
        print("\n" + "=" * 70)
        print("REVIEW OPTIONS:")
        print("  1. Approve (response is correct)")
        print("  2. Correct (provide corrected response)")
        print("  3. Skip (review later)")
        print("  4. Exit")
        print("=" * 70)
        
        choice = input("\nYour choice (1-4): ").strip()
        
        if choice == "1":
            # Approve - mark verified with no correction
            cache.mark_verified(row['prompt_hash'], corrected_response=None)
            print("✅ Approved")
            
        elif choice == "2":
            # Correct - allow editing
            print("\nEnter corrected JSON response (or paste from file):")
            print("(Type 'END' on a new line when done)")
            
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            
            corrected = "\n".join(lines)
            
            # Validate JSON
            try:
                json.loads(corrected)
                cache.mark_verified(row['prompt_hash'], corrected_response=corrected)
                print("✅ Correction saved")
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}")
                print("Correction NOT saved")
        
        elif choice == "3":
            print("⏭️  Skipped")
            continue
        
        elif choice == "4":
            print("👋 Exiting")
            break
        
        print()
    
    # Final stats
    final_stats = cache.stats()
    print("\n" + "=" * 70)
    print("REVIEW COMPLETE")
    print("=" * 70)
    print(f"Verified: {final_stats['verified_corrections']}/{final_stats['total_corrections']}")
    
    remaining = final_stats['total_corrections'] - final_stats['verified_corrections']
    if remaining == 0:
        print("\n✅ All corrections verified! Next extraction will use cached results.")
    else:
        print(f"\n⚠️  {remaining} correction(s) still pending review")


def show_cache_impact():
    """Show how corrections improve extraction quality."""
    
    cache_path = Path("config/llm_corrections.db")
    if not cache_path.exists():
        print(f"❌ No cache found at {cache_path}")
        return
    
    cache = CorrectionCache(cache_path)
    stats = cache.stats()
    
    print("=" * 70)
    print("CACHE IMPACT ANALYSIS")
    print("=" * 70)
    
    verified = cache.find_similar(verified_only=True, limit=100)
    
    print(f"\n✅ {len(verified)} verified corrections in cache")
    print(f"📊 Total cache hits: {stats['total_cache_hits']}")
    
    if verified:
        print(f"\n🔥 Most-used corrections (top 5):")
        top5 = sorted(verified, key=lambda x: x.hit_count, reverse=True)[:5]
        for i, record in enumerate(top5, 1):
            print(f"   {i}. {record.message_type or 'N/A'}: {record.hit_count} hits")
    
    # Calculate LLM calls saved
    llm_calls_saved = stats['total_cache_hits']
    print(f"\n💰 LLM calls saved: {llm_calls_saved}")
    print(f"   (without cache: would need {stats['total_corrections'] + llm_calls_saved} calls)")
    print(f"   (with cache: only needed {stats['total_corrections']} calls)")
    
    reduction_pct = (llm_calls_saved / (stats['total_corrections'] + llm_calls_saved)) * 100
    print(f"   📉 {reduction_pct:.1f}% reduction in LLM calls")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "impact":
        show_cache_impact()
    else:
        review_and_correct_workflow()
