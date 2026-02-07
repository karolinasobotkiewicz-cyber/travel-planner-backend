"""
Integration test: Generate plan with tag preferences
"""

import sys
sys.path.append("app")

from infrastructure.repositories.load_zakopane import load_zakopane_poi
from infrastructure.repositories.normalizer import normalize_poi
from domain.planner.engine import build_day

def test_plan_with_water_preferences():
    """Test plan generation with water_attractions preference"""
    print("\n🧪 INTEGRATION TEST: Water Attractions Preference")
    print("=" * 80)
    
    # Load POIs
    raw_pois = load_zakopane_poi("data/zakopane.xlsx")
    pois = [normalize_poi(p, i) for i, p in enumerate(raw_pois, start=1)]
    
    print(f"✅ Loaded {len(pois)} POI")
    
    # User with water_attractions preference
    user = {
        "target_group": "family_kids",
        "budget": 2,
        "crowd_tolerance": 2,
        "preferences": ["water_attractions"],  # Should boost Termy
        "travel_style": ["relaxed"],
        "intensity_level": 2,
    }
    
    context = {
        "season": "winter",
        "date": "2026-02-05",
        "weather": {
            "condition": "clear",
            "temp": -5,
            "precip": False,
        }
    }
    
    # Generate plan
    print("\n🔄 Generating plan...")
    plan = build_day(pois, user, context)
    
    print(f"\n✅ Generated plan with {len(plan)} POI:")
    print("=" * 80)
    
    for i, p in enumerate(plan, 1):
        poi_name = p.get("name", "Unknown")
        poi_type = p.get("type", "")
        poi_tags = p.get("tags", [])
        print(f"{i}. {poi_name}")
        print(f"   Type: {poi_type}")
        print(f"   Tags: {', '.join(poi_tags[:5])}")
    
    # Check if water POI scored higher
    water_pois = [p for p in plan if "thermal" in p.get("tags", []) or "hot_springs" in p.get("tags", [])]
    
    print(f"\n📊 Water-related POI in plan: {len(water_pois)}")
    for p in water_pois:
        print(f"   - {p.get('name')}")
    
    if water_pois:
        print("\n✅ SUCCESS: Water attractions appear in plan (preference applied)")
    else:
        print("\n⚠️  WARNING: No water attractions in plan (check scoring)")


def test_plan_with_kids_preferences():
    """Test plan generation with attractions_for_kids preference"""
    print("\n\n🧪 INTEGRATION TEST: Kids Attractions Preference")
    print("=" * 80)
    
    # Load POIs
    raw_pois = load_zakopane_poi("data/zakopane.xlsx")
    pois = [normalize_poi(p, i) for i, p in enumerate(raw_pois, start=1)]
    
    print(f"✅ Loaded {len(pois)} POI")
    
    # User with attractions_for_kids preference
    user = {
        "target_group": "family_kids",
        "budget": 2,
        "crowd_tolerance": 2,
        "preferences": ["attractions_for_kids"],  # Should boost kids POI
        "travel_style": ["relaxed"],
        "intensity_level": 2,
    }
    
    context = {
        "season": "winter",
        "date": "2026-02-05",
        "weather": {
            "condition": "clear",
            "temp": -5,
            "precip": False,
        }
    }
    
    # Generate plan
    print("\n🔄 Generating plan...")
    plan = build_day(pois, user, context)
    
    print(f"\n✅ Generated plan with {len(plan)} POI:")
    print("=" * 80)
    
    for i, p in enumerate(plan, 1):
        poi_name = p.get("name", "Unknown")
        poi_type = p.get("type", "")
        poi_tags = p.get("tags", [])
        print(f"{i}. {poi_name}")
        print(f"   Type: {poi_type}")
        print(f"   Tags: {', '.join(poi_tags[:5])}")
    
    # Check if kids POI scored higher
    kids_pois = [p for p in plan if p.get("type") == "kids_attractions" or "interactive_exhibition_kids" in p.get("tags", [])]
    
    print(f"\n📊 Kids-related POI in plan: {len(kids_pois)}")
    for p in kids_pois:
        print(f"   - {p.get('name')}")
    
    if kids_pois:
        print("\n✅ SUCCESS: Kids attractions appear in plan (preference applied)")
    else:
        print("\n⚠️  WARNING: No kids attractions in plan (check scoring)")


def test_plan_without_preferences():
    """Test plan generation without preferences (backward compat)"""
    print("\n\n🧪 INTEGRATION TEST: No Preferences (Backward Compat)")
    print("=" * 80)
    
    # Load POIs
    raw_pois = load_zakopane_poi("data/zakopane.xlsx")
    pois = [normalize_poi(p, i) for i, p in enumerate(raw_pois, start=1)]
    
    print(f"✅ Loaded {len(pois)} POI")
    
    # User without preferences
    user = {
        "target_group": "family_kids",
        "budget": 2,
        "crowd_tolerance": 2,
        "preferences": [],  # No preferences
        "travel_style": ["relaxed"],
        "intensity_level": 2,
    }
    
    context = {
        "season": "winter",
        "date": "2026-02-05",
        "weather": {
            "condition": "clear",
            "temp": -5,
            "precip": False,
        }
    }
    
    # Generate plan
    print("\n🔄 Generating plan...")
    plan = build_day(pois, user, context)
    
    print(f"\n✅ Generated plan with {len(plan)} POI:")
    print("=" * 80)
    
    for i, p in enumerate(plan, 1):
        poi_name = p.get("name", "Unknown")
        print(f"{i}. {poi_name}")
    
    if len(plan) > 0:
        print("\n✅ SUCCESS: Plan generated without preferences (backward compatible)")
    else:
        print("\n❌ ERROR: No plan generated")


if __name__ == "__main__":
    print("=" * 80)
    print("TAG PREFERENCE SCORING - INTEGRATION TESTS")
    print("=" * 80)
    
    try:
        test_plan_with_water_preferences()
        test_plan_with_kids_preferences()
        test_plan_without_preferences()
        
        print("\n" + "=" * 80)
        print("✅ ALL INTEGRATION TESTS COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
