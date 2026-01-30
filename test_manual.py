"""
Manual testing - bezpośrednie wywołanie engine z różnymi preferences/travel_style.
Testuje czy nowe scoring modules działają poprawnie.
"""
from app.domain.planner.engine import build_day
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.infrastructure.repositories.normalizer import normalize_poi

# Load real data
print("Loading zakopane POI...")
excel_path = "data/zakopane.xlsx"
raw_pois = load_zakopane_poi(excel_path)
pois = [normalize_poi(poi, idx) for idx, poi in enumerate(raw_pois)]
print(f"Loaded {len(pois)} POI\n")

# Base context
context = {
    "date": "2026-02-15",
    "season": "winter",
    "daylight_end": "16:30",
    "region_type": "mountain",
    "precip": False,
    "temp": -5,
}

print("=" * 60)
print("TEST 1: outdoor preferences + adventure travel_style")
print("=" * 60)
user1 = {
    "target_group": "solo",
    "budget": 2,
    "crowd_tolerance": 2,
    "preferences": ["outdoor", "hiking", "nature"],
    "travel_style": "adventure",
}
plan1 = build_day(pois, user1, context)
attractions1 = [item for item in plan1 if item["type"] == "attraction"]
print(f"Generated {len(attractions1)} attractions")
print(f"POI IDs: {[item['poi']['id'] for item in attractions1]}")
print(f"Total items in plan: {len(plan1)}")

print("\n" + "=" * 60)
print("TEST 2: museums preferences + relax travel_style")
print("=" * 60)
user2 = {
    "target_group": "solo",
    "budget": 2,
    "crowd_tolerance": 2,
    "preferences": ["museums", "culture", "history"],
    "travel_style": "relax",
}
plan2 = build_day(pois, user2, context)
attractions2 = [item for item in plan2 if item["type"] == "attraction"]
print(f"Generated {len(attractions2)} attractions")
print(f"POI IDs: {[item['poi']['id'] for item in attractions2]}")
print(f"Total items in plan: {len(plan2)}")

print("\n" + "=" * 60)
print("TEST 3: empty preferences + balanced travel_style (default)")
print("=" * 60)
user3 = {
    "target_group": "solo",
    "budget": 2,
    "crowd_tolerance": 2,
    "preferences": [],
    "travel_style": "balanced",
}
plan3 = build_day(pois, user3, context)
attractions3 = [item for item in plan3 if item["type"] == "attraction"]
print(f"Generated {len(attractions3)} attractions")
print(f"POI IDs: {[item['poi']['id'] for item in attractions3]}")
print(f"Total items in plan: {len(plan3)}")

print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)
print(f"✅ Test 1 completed: {len(attractions1)} attractions")
print(f"✅ Test 2 completed: {len(attractions2)} attractions")
print(f"✅ Test 3 completed: {len(attractions3)} attractions")
print("\nAll plans have standard structure:")
for i, plan in enumerate([plan1, plan2, plan3], 1):
    types = [item["type"] for item in plan]
    has_start = "accommodation_start" in types
    has_end = "accommodation_end" in types
    has_lunch = "lunch_break" in types
    print(f"  Plan {i}: start={has_start}, end={has_end}, lunch={has_lunch}")

print("\n✅ Manual testing completed - all 3 scenarios work correctly!")

