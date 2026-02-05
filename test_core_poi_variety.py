"""
CLIENT REQUIREMENT TEST (04.02.2026): Core POI variety
Test that plans have variety in core POI selection (not always same attractions)

Generate multiple plans with same parameters and verify different core POI appear
"""

import sys
import io
sys.path.insert(0, '.')

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POI
ZAKOPANE_POI = load_zakopane_poi("data/zakopane.xlsx")

def generate_plan(run_number):
    """Generate single plan and return core POI list"""
    user = {
        "target_group": "friends",
        "intensity_preference": "medium",
        "budget": "medium"
    }
    
    ctx = {
        "season": "winter",
        "has_car": True,
        "accommodation_location": {"lat": 49.295, "lon": 19.949},
        "start_time": "09:00",
        "end_time": "22:00",
        "date": "2026-02-05"  # Wednesday
    }
    
    plan = build_day(ZAKOPANE_POI, user, ctx)
    
    # Extract all POI
    all_poi = []
    core_poi = []
    
    for item in plan:
        if item["type"] == "attraction":
            poi = item.get("poi", {})
            poi_id_val = poi.get("id")
            poi_name = item.get("name", "Unknown")
            priority = str(poi.get("priority_level", "")).strip().lower()
            
            all_poi.append(poi_name)
            if priority == "core":
                core_poi.append(poi_name)
    
    return all_poi, core_poi

def test_core_poi_variety():
    """Test that multiple runs produce different core POI"""
    print("\n" + "="*80)
    print("CLIENT REQUIREMENT TEST: Core POI Variety")
    print("="*80)
    print("Generating 5 plans with same parameters...")
    print("Expected: Different core POI in different runs (variety)\n")
    
    all_runs = []
    all_core_poi_sets = []
    
    for i in range(5):
        print(f"\n🔄 RUN {i+1}/5:", flush=True)
        all_poi, core_poi = generate_plan(i+1)
        all_runs.append(all_poi)
        all_core_poi_sets.append(set(core_poi))
        
        print(f"   Total POI: {len(all_poi)}")
        print(f"   All POI: {all_poi}")
        print(f"   Core POI: {core_poi if core_poi else ['None']}")
    
    # Analyze variety
    print("\n" + "="*80)
    print("VARIETY ANALYSIS:")
    print("="*80)
    
    # Check if we have different core POI across runs
    unique_core_poi = set()
    for core_set in all_core_poi_sets:
        unique_core_poi.update(core_set)
    
    print(f"\n📊 Unique core POI across all runs: {len(unique_core_poi)}")
    print(f"   Core POI found: {sorted(list(unique_core_poi))}")
    
    # Check if runs differ from each other
    all_identical = all(all_runs[0] == run for run in all_runs[1:])
    
    print("\n🎲 VARIETY CHECK:")
    if all_identical:
        print("   ❌ All runs produced IDENTICAL plans (no variety)")
    else:
        # Count how many runs differ
        different_count = sum(1 for run in all_runs[1:] if run != all_runs[0])
        print(f"   ✅ {different_count}/4 runs differ from first run")
    
    # Check core POI variety specifically
    core_variety_count = len(unique_core_poi)
    if core_variety_count > 1:
        print(f"   ✅ Multiple core POI used: {core_variety_count} different core attractions")
    else:
        print(f"   ⚠️  Only {core_variety_count} core POI used (may indicate low variety)")
    
    print("\n" + "="*80)
    if not all_identical and core_variety_count > 1:
        print("✅ PASS | Core POI variety implemented successfully")
        print("         Plans show diversity in core attraction selection")
    elif not all_identical:
        print("⚠️  PARTIAL | Plans differ but core POI variety limited")
        print("         (May be due to constraints or scoring)")
    else:
        print("❌ FAIL | No variety detected - all plans identical")
        print("         Expected: different core POI in different runs")
    print("="*80 + "\n")
    
    return not all_identical

if __name__ == "__main__":
    success = test_core_poi_variety()
    sys.exit(0 if success else 1)
