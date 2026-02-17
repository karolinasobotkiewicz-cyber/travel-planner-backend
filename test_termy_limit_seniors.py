"""
Test Problem #9: Max 1 Termy/Spa Per Day for Seniors

BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9):
Client issue: "Termy Zakopiańskie + Chochołowskie Termy tego samego dnia dla seniorów - nie ma sensu"

Requirements:
- Hard limit: max 1 termy/spa per day for target_group="seniors"
- Multiple termy visits exhaust seniors, should be avoided

Solution:
- Added is_termy_spa() function to identify termy/spa/thermal POIs
- Track termy_count per day for seniors
- Skip additional termy POIs if termy_count >= 1
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day, is_termy_spa

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"Loaded {len(pois)} POIs\n")

print("="*80)
print("TEST: Problem #9 - Max 1 Termy/Spa Per Day for Seniors")
print("="*80)

# Test 1: Identify termy/spa POIs
print("\nTEST 1: Identify Termy/Spa POIs")
print("="*80)

termy_pois = []
for poi in pois:
    if is_termy_spa(poi):
        poi_name = str(poi.get("name", "Unknown"))
        # ASCII-safe encoding
        poi_name_safe = poi_name.encode('ascii', errors='ignore').decode('ascii')
        termy_pois.append(poi_name_safe)
        print(f"   - {poi_name_safe}")

print(f"\nFound {len(termy_pois)} termy/spa POIs in dataset")

# Test 2: Generate plan for seniors
print("\n" + "="*80)
print("TEST 2: Generate Plan for Seniors")
print("="*80)

user = {
    "target_group": "seniors",
    "preferences": ["relax", "nature_landscapes"],
    "budget_level": 3
}

context = {
    "season": "winter",
    "has_car": True,
    "accommodation_location": {"lat": 49.295, "lon": 19.949},
    "start_time": "09:00",
    "end_time": "19:00",
    "date": "2026-02-17"  # Tuesday
}

print("\nGenerating plan for seniors...")
plan = build_day(
    pois=pois,
    user=user,
    context=context,
    day_start="09:00",
    day_end="19:00"
)

print(f"\nGenerated plan with {len(plan)} items")

# Count termy/spa items in plan
termy_items = []
for item in plan:
    if item.get("type") == "attraction":
        poi_name = item.get("name", "")
        # Check if it's a termy/spa
        # Find POI in dataset
        poi_dict = None
        for p in pois:
            if p.get("name") == poi_name:
                poi_dict = p
                break
        
        if poi_dict and is_termy_spa(poi_dict):
            # ASCII-safe encoding
            poi_name_safe = str(poi_name).encode('ascii', errors='ignore').decode('ascii')
            termy_items.append({
                "name": poi_name_safe,
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time")
            })

# Validation
print("\n" + "="*80)
print("VALIDATION")
print("="*80)

print(f"\nTermy/spa items in plan: {len(termy_items)}")

if len(termy_items) == 0:
    print("\n   No termy/spa items in plan (acceptable)")
    print("   Seniors may have different preferences or constraints")
elif len(termy_items) == 1:
    print("\nPASS: Exactly 1 termy/spa in plan (within limit)")
    termy = termy_items[0]
    print(f"   Termy: {termy['name']}")
    print(f"   Time: {termy['start_time']} - {termy['end_time']}")
    print("\n   Problem #9 FIXED:")
    print("   - Max 1 termy/spa per day for seniors enforced")
    print("   - Prevents exhaustion from multiple thermal visits")
    print("   - Allows time for other activities")
elif len(termy_items) > 1:
    print(f"\nFAIL: Found {len(termy_items)} termy/spa items (exceeds limit of 1)")
    for i, termy in enumerate(termy_items, 1):
        print(f"   {i}. {termy['name']} ({termy['start_time']}-{termy['end_time']})")
    print("\n   This violates the max 1 termy/day constraint for seniors")
else:
    print(f"\n   Negative count? {len(termy_items)} - something is wrong")

# Show timeline if termy items found
if termy_items:
    print("\n" + "="*80)
    print("TIMELINE (termy/spa items)")
    print("="*80)
    
    for termy in termy_items:
        print(f"\n{termy['name']}")
        print(f"   Time: {termy['start_time']} - {termy['end_time']}")

print("\n" + "="*80)
