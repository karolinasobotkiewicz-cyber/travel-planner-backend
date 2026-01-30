"""Quick test opening hours bug - Muzeum Oscypka + Myszogród"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POIs
pois = load_zakopane_poi('data/zakopane.xlsx')

# Find problem POIs
muzeum = [p for p in pois if 'Oscypka' in p['name']][0]
mysz = [p for p in pois if 'Myszog' in p['name']][0]

print("=" * 80)
print("MUZEUM OSCYPKA:")
print(f"Opening hours: {muzeum['opening_hours']}")
print()

print("MYSZOGRÓD:")
print(f"Opening hours: {mysz['opening_hours']}")
print("=" * 80)
print()

# Test with early start time (09:00) - should NOT schedule closed POI
user = {
    "target_group": "solo",
    "budget": 2,
    "crowd_tolerance": 1,
    "preferences": [],
    "travel_style": "balanced"
}

context = {
    "season": "winter",
    "date": (2026, 2, 15, 6),  # 2026-02-15 (Sunday, dow=6)
    "weather": {
        "condition": "sunny",
        "precip": False,
        "temp": 5
    },
    "region_type": "mountain",
    "daylight_end": None
}

print("Running build_day with start_time 09:00...")
print()

plan = build_day(pois, user, context, "09:00", "18:00")

print("=" * 80)
print("PLAN ITEMS:")
for item in plan:
    if item['type'] == 'attraction':
        name = item['name']
        start = item['start_time']
        end = item['end_time']
        
        # Check if it's problematic POI
        marker = ""
        if 'Oscypka' in name:
            marker = " ❌ CLOSED UNTIL 15:30!"
        elif 'Myszog' in name:
            if start < "10:00":
                marker = " ❌ CLOSED UNTIL 10:00!"
        
        print(f"  {start}-{end}: {name}{marker}")

print("=" * 80)
