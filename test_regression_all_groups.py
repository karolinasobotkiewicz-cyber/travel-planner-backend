"""
REGRESSION TEST: Verify poi_9 filtering for all target groups

Expected behavior:
- solo: EXCLUDE poi_9 (family_kids only)
- couples: EXCLUDE poi_9 (family_kids only)
- friends: EXCLUDE poi_9 (family_kids only)
- family_kids: ALLOW poi_9 (target group match)

HOTFIX #10.8 verification.
"""

import sys
import io
from datetime import datetime

# Fix Windows console encoding for Polish characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import from app
from app.domain.planner.engine import build_day
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

print("=" * 80)
print("REGRESSION TEST: POI_9 Filtering - All Target Groups")
print("=" * 80)

# Load POI
all_pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"\n✅ Loaded {len(all_pois)} POI from data/zakopane.xlsx")

# Check poi_9 data
poi_9 = [p for p in all_pois if p.get('id') == 'poi_9'][0]
print(f"\n📋 POI_9 Data:")
print(f"   Name: {poi_9.get('name')}")
print(f"   Target groups: {poi_9.get('target_groups')}")
print(f"   kids_only: {poi_9.get('kids_only')}")

# Test all groups
test_groups = [
    ("solo", "❌ EXCLUDE"),
    ("couples", "❌ EXCLUDE"),
    ("friends", "❌ EXCLUDE"),
    ("family_kids", "✅ ALLOW")
]

context = {
    "season": "winter",
    "date": datetime(2026, 2, 5),
    "weather": {"condition": "sunny", "temp": 5},
    "has_car": True,
    "transport": "car",
    "group_size": 3
}

all_results = []

for target_group, expected_behavior in test_groups:
    print()
    print("=" * 80)
    print(f"🧪 TEST: {target_group.upper()} - Expected: {expected_behavior} poi_9")
    print("=" * 80)
    
    user = {
        "target_group": target_group,
        "intensity": "moderate",
        "budget": "standard",
        "travel_style": "balanced"
    }
    
    # Run engine
    result = build_day(
        pois=all_pois,
        user=user,
        context=context,
        day_start="09:00",
        day_end="19:00"
    )
    
    # Check if poi_9 in result
    poi_ids = [item['poi'].get('id') for item in result if item.get('type') == 'attraction']
    has_poi_9 = 'poi_9' in poi_ids
    
    all_results.append((target_group, expected_behavior, has_poi_9, poi_ids))
    
    print()
    print(f"📊 RESULT for {target_group}:")
    print(f"   POI in plan: {poi_ids}")
    print(f"   Contains poi_9: {has_poi_9}")

# Summary
print()
print("=" * 80)
print("📋 REGRESSION TEST SUMMARY")
print("=" * 80)

all_passed = True
for target_group, expected_behavior, has_poi_9, poi_ids in all_results:
    should_have_poi_9 = "ALLOW" in expected_behavior
    test_passed = has_poi_9 == should_have_poi_9
    
    status = "✅ PASS" if test_passed else "❌ FAIL"
    print(f"{status} | {target_group:12s} | Expected: {expected_behavior:12s} | Has poi_9: {has_poi_9}")
    
    if not test_passed:
        all_passed = False
        print(f"      ⚠️  poi_9 was {'FOUND' if has_poi_9 else 'NOT FOUND'} but should be {'ALLOWED' if should_have_poi_9 else 'EXCLUDED'}")

print()
if all_passed:
    print("🎉 ALL TESTS PASSED! poi_9 filtering works correctly for all groups.")
else:
    print("❌ SOME TESTS FAILED! Review the results above.")
