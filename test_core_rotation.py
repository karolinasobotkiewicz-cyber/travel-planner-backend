"""
Test core POI rotation (CLIENT REQUIREMENT 08.02.2026)
Run same plan multiple times and verify different core POI are selected.
This prevents always getting Morskie Oko in every plan.
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

def test_core_rotation():
    """Test that core POI rotate across multiple plan generations."""
    
    # Load POI
    pois = load_zakopane_poi("data/zakopane.xlsx")
    print(f"[OK] Loaded {len(pois)} POI")
    
    # Fixed parameters for reproducibility
    user = {
        "target_group": "couples",
        "budget": 2,  # Standard level
        "intensity": "moderate",
        "group_size": 2,
        "preferences": ["hiking"],
        "travel_style": "balanced"
    }
    
    context = {
        "season": "summer",
        "has_car": True,
        "date": "2025-07-15",  # Summer date
        "region_type": "mountains",
        "transport": "car"
    }
    
    print("\n=== CORE POI ROTATION TEST ===")
    print("Running 10 iterations with same parameters...")
    print(f"Parameters: {user['target_group']}, {context['season']}, budget={user['budget']}\n")
    
    core_poi_by_run = []
    
    # Run 10 times with same parameters
    for run in range(10):
        try:
            plan = build_day(pois, user, context, day_start="09:00", day_end="19:00")
            
            # Extract core POI from plan
            day_core = []
            
            for item in plan:
                if item.get("type") == "attraction":
                    poi = item.get("poi", {})
                    # Core POI have priority_level = 12 (not "core" string)
                    priority = poi.get('priority_level', 0)
                    try:
                        if int(priority) == 12:  # Core POI
                            day_core.append(poi.get('name'))
                    except (ValueError, TypeError):
                        pass
            
            core_poi_by_run.append(day_core)
            print(f"Run {run+1}: Core POI = {day_core if day_core else 'None'}")
            
        except Exception as e:
            print(f"Run {run+1}: ERROR - {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Analyze results
    print("\n=== ANALYSIS ===")
    
    # Flatten list of all core POI seen
    all_core_poi = []
    for day_core in core_poi_by_run:
        all_core_poi.extend(day_core)
    
    unique_core = set(all_core_poi)
    
    print(f"Total runs: {len(core_poi_by_run)}")
    print(f"Unique core POI seen: {len(unique_core)}")
    print(f"Core POI names: {unique_core}")
    
    # Count frequency
    from collections import Counter
    freq = Counter(all_core_poi)
    print("\nFrequency:")
    for poi, count in freq.most_common():
        print(f"  {poi}: {count} times ({count/len(core_poi_by_run)*100:.1f}%)")
    
    # Success criteria: At least 2 different core POI should appear
    print("\n=== RESULT ===")
    if len(unique_core) >= 2:
        print("[PASS] TEST PASSED: Core POI rotation working!")
        print(f"  Found {len(unique_core)} different core POI across {len(core_poi_by_run)} runs.")
        print("  This confirms variety and prevents always selecting same core POI.")
        return True
    else:
        print("[FAIL] TEST FAILED: No rotation detected")
        if len(unique_core) == 1:
            print(f"  Same core POI every time: {list(unique_core)[0]}")
        else:
            print("  No core POI found in any run")
        return False

if __name__ == "__main__":
    success = test_core_rotation()
    exit(0 if success else 1)
