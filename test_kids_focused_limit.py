"""
CLIENT REQUIREMENT TEST (04.02.2026): Kids-focused daily limit
Test that non-family groups (friends) get max 1 kids-focused POI per day

Expected Result:
- Should NOT include poi_9 (Park Harnasia - kids-only)
- Should NOT include other kids-focused POI if one is already selected
- Should prefer POI with broader target_groups
"""

import sys
import json
sys.path.insert(0, '.')  # Add current directory to path

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POI data
ZAKOPANE_POI = load_zakopane_poi("data/zakopane.xlsx")

def test_kids_focused_limit_friends():
    """Test that friends group gets max 1 kids-focused POI per day"""
    
    # Friends group - should exclude kids-focused POI
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
        "date": "2026-02-04"  # Tuesday
    }
    
    print("\n" + "="*80)
    print("CLIENT REQUIREMENT TEST: Kids-focused daily limit")
    print("="*80)
    print(f"User: {user['target_group']} | Intensity: {user['intensity_preference']}")
    print(f"Start: {ctx['start_time']} | End: {ctx['end_time']}")
    print("-"*80)
    
    plan = build_day(ZAKOPANE_POI, user, ctx)
    
    # Count kids-focused POI in plan
    kids_focused_poi = []
    all_poi_in_plan = []
    
    for item in plan:
        if item["type"] == "attraction":
            poi = item.get("poi", {})
            poi_id_val = poi.get("id")
            poi_name = item.get("name", "Unknown")
            all_poi_in_plan.append((poi_id_val, poi_name))
            
            # Check if kids-focused (only family_kids in target_groups)
            target_groups = poi.get("target_groups") or []
            tg = set([str(x).strip().lower() for x in target_groups])
            is_kids_focused = len(tg) == 1 and "family_kids" in tg
            
            if is_kids_focused:
                kids_focused_poi.append((poi_id_val, poi_name, item.get("start_time")))
    
    print("\n📍 ALL POI IN PLAN:")
    for poi_id, poi_name in all_poi_in_plan:
        print(f"   - {poi_id}: {poi_name}")
    
    print(f"\n🎯 KIDS-FOCUSED POI COUNT: {len(kids_focused_poi)}/1")
    if kids_focused_poi:
        print("   Kids-focused POI found:")
        for poi_id, poi_name, time in kids_focused_poi:
            print(f"   - {poi_id}: {poi_name} at {time}")
    else:
        print("   ✅ No kids-focused POI (as expected)")
    
    # Verify limit
    print("\n" + "="*80)
    if len(kids_focused_poi) <= 1:
        print("✅ PASS | Daily limit respected: max 1 kids-focused POI")
        if len(kids_focused_poi) == 0:
            print("         (0 kids-focused POI - even better!)")
    else:
        print(f"❌ FAIL | Too many kids-focused POI: {len(kids_focused_poi)}/1")
        print("         Expected: max 1 kids-focused POI per day")
    print("="*80 + "\n")
    
    return len(kids_focused_poi) <= 1

if __name__ == "__main__":
    success = test_kids_focused_limit_friends()
    sys.exit(0 if success else 1)
