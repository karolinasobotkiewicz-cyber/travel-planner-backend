"""
Test budget daily_limit enforcement
Verifies that engine respects budget.daily_limit parameter
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POI directly
pois = load_zakopane_poi("data/zakopane.xlsx")
print(f"Loaded {len(pois)} POI from zakopane.xlsx\n")

# Test context
context = {
    "season": "winter",
    "region_type": "mountains",
    "transport": "car",
    "date": "2026-02-15",
    "has_car": True,
}

print("=" * 80)
print("TEST 1: No budget limit (backward compatibility)")
print("=" * 80)

user_no_limit = {
    "target_group": "family_kids",
    "children_age": [5, 8],
    "crowd_tolerance": "medium",
    "budget": 2,
    "daily_limit": None,  # No limit
    "preferences": ["family_friendly", "nature_landscapes"],
    "travel_style": "balanced",
}

plan1 = build_day(
    pois=pois,
    user=user_no_limit,
    context=context,
    day_start="09:00",
    day_end="18:00",
)

# Calculate total cost
total_cost_1 = 0
poi_count_1 = 0
for item in plan1:
    if item["type"] == "attraction":
        cost = item.get("poi", {}).get("ticket_price", 0)
        total_cost_1 += cost
        poi_count_1 += 1
        print(f"  POI: {item['name']} - {cost} PLN")

print(f"\n✓ Test 1 Results:")
print(f"  Total POI: {poi_count_1}")
print(f"  Total cost: {total_cost_1} PLN")
print(f"  Expected: No limit, should work as before")
print(f"  Status: {'PASS' if poi_count_1 >= 3 else 'FAIL'} (should have 3+ POI)\n")

print("=" * 80)
print("TEST 2: Strict budget limit (500 PLN)")
print("=" * 80)

user_with_limit = {
    "target_group": "family_kids",
    "children_age": [5, 8],
    "crowd_tolerance": "medium",
    "budget": 2,
    "daily_limit": 500,  # STRICT LIMIT
    "preferences": ["family_friendly", "nature_landscapes"],
    "travel_style": "balanced",
}

plan2 = build_day(
    pois=pois,
    user=user_with_limit,
    context=context,
    day_start="09:00",
    day_end="18:00",
)

# Calculate total cost
total_cost_2 = 0
poi_count_2 = 0
for item in plan2:
    if item["type"] == "attraction":
        cost = item.get("poi", {}).get("ticket_price", 0)
        total_cost_2 += cost
        poi_count_2 += 1
        print(f"  POI: {item['name']} - {cost} PLN (running total: {total_cost_2} PLN)")

print(f"\n✓ Test 2 Results:")
print(f"  Total POI: {poi_count_2}")
print(f"  Total cost: {total_cost_2} PLN")
print(f"  Budget limit: 500 PLN")
print(f"  Status: {'PASS ✓' if total_cost_2 <= 500 else 'FAIL ✗'} (should be ≤500 PLN)\n")

print("=" * 80)
print("TEST 3: Very low limit (200 PLN)")
print("=" * 80)

user_low_limit = {
    "target_group": "family_kids",
    "children_age": [5, 8],
    "crowd_tolerance": "medium",
    "budget": 2,
    "daily_limit": 200,  # VERY LOW
    "preferences": ["family_friendly", "nature_landscapes"],
    "travel_style": "balanced",
}

plan3 = build_day(
    pois=pois,
    user=user_low_limit,
    context=context,
    day_start="09:00",
    day_end="18:00",
)

# Calculate total cost
total_cost_3 = 0
poi_count_3 = 0
for item in plan3:
    if item["type"] == "attraction":
        cost = item.get("poi", {}).get("ticket_price", 0)
        total_cost_3 += cost
        poi_count_3 += 1
        print(f"  POI: {item['name']} - {cost} PLN (running total: {total_cost_3} PLN)")

print(f"\n✓ Test 3 Results:")
print(f"  Total POI: {poi_count_3}")
print(f"  Total cost: {total_cost_3} PLN")
print(f"  Budget limit: 200 PLN")
print(f"  Status: {'PASS ✓' if total_cost_3 <= 200 else 'FAIL ✗'} (should be ≤200 PLN)\n")

print("=" * 80)
print("SUMMARY")
print("=" * 80)

all_pass = True

print(f"Test 1 (No limit): {poi_count_1} POI, {total_cost_1} PLN - {'PASS ✓' if poi_count_1 >= 3 else 'FAIL ✗'}")
if poi_count_1 < 3:
    all_pass = False

print(f"Test 2 (500 PLN limit): {poi_count_2} POI, {total_cost_2} PLN - {'PASS ✓' if total_cost_2 <= 500 else 'FAIL ✗'}")
if total_cost_2 > 500:
    all_pass = False

print(f"Test 3 (200 PLN limit): {poi_count_3} POI, {total_cost_3} PLN - {'PASS ✓' if total_cost_3 <= 200 else 'FAIL ✗'}")
if total_cost_3 > 200:
    all_pass = False

print("\n" + "=" * 80)
if all_pass:
    print("🎉 ALL TESTS PASSED - Budget enforcement working correctly!")
else:
    print("❌ SOME TESTS FAILED - Check implementation")
print("=" * 80)
