"""
COMPREHENSIVE TEST - ETAP 1 Complete System Verification
Tests all major features implemented in Stage 1
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day

# Load POI
pois = load_zakopane_poi("data/zakopane.xlsx")
print(f"✓ Loaded {len(pois)} POI from zakopane.xlsx\n")

def print_test_header(test_num, description):
    print("\n" + "=" * 80)
    print(f"TEST {test_num}: {description}")
    print("=" * 80)

def analyze_plan(plan, test_name):
    """Analyze and print plan details"""
    poi_list = []
    total_cost = 0
    
    for item in plan:
        if item["type"] == "attraction":
            poi = item.get("poi", {})
            name = item["name"]
            cost = poi.get("ticket_price", 0)
            total_cost += cost
            poi_list.append({
                "name": name,
                "cost": cost,
                "target_groups": poi.get("target_groups", []),
                "kids_only": poi.get("kids_only", False),
                "intensity": poi.get("intensity", "unknown")
            })
    
    print(f"\n{test_name} Results:")
    print(f"  POI count: {len(poi_list)}")
    print(f"  Total cost (per person): {total_cost} PLN")
    
    if poi_list:
        print(f"  POI list:")
        for poi in poi_list:
            print(f"    - {poi['name']} ({poi['cost']} PLN, intensity={poi['intensity']})")
    
    return poi_list, total_cost

# ============================================================================
# TEST 1: Multi-season opening hours (Winter vs Summer)
# ============================================================================
print_test_header(1, "Multi-season opening hours (Winter)")

context_winter = {
    "season": "winter",
    "region_type": "mountains",
    "transport": "car",
    "date": "2026-02-15",  # Winter
    "has_car": True,
}

user_base = {
    "target_group": "couples",
    "children_age": None,
    "crowd_tolerance": 1,
    "budget": 2,
    "daily_limit": None,
    "group_size": 2,
    "preferences": ["nature_landscapes"],
    "travel_style": "balanced",
}

plan_winter = build_day(
    pois=pois,
    user=user_base,
    context=context_winter,
    day_start="09:00",
    day_end="18:00",
)

poi_winter, cost_winter = analyze_plan(plan_winter, "Winter (Feb)")

# Check if Morskie Oko is in plan (should have winter hours 08:00-16:00)
has_morskie = any("Morskie Oko" in item.get("name", "") for item in plan_winter if item["type"] == "attraction")
print(f"  ✓ Morskie Oko in winter plan: {has_morskie}")
print(f"  Status: {'PASS ✓' if has_morskie else 'FAIL ✗'}")

# ============================================================================
# TEST 2: Target group filtering - family_kids
# ============================================================================
print_test_header(2, "Target group filtering - family_kids")

user_family = {
    "target_group": "family_kids",
    "children_age": 6,
    "crowd_tolerance": 1,
    "budget": 2,
    "daily_limit": None,
    "group_size": 4,
    "preferences": ["family_friendly"],
    "travel_style": "balanced",
}

plan_family = build_day(
    pois=pois,
    user=user_family,
    context=context_winter,
    day_start="09:00",
    day_end="18:00",
)

poi_family, cost_family = analyze_plan(plan_family, "Family (kids age 6)")

# Check if family-friendly POI are included
family_poi_names = [item["name"].lower() for item in plan_family if item["type"] == "attraction"]
has_family_friendly = any("park" in name or "dom do góry" in name for name in family_poi_names)
print(f"  ✓ Contains family-friendly POI: {has_family_friendly}")
print(f"  Status: {'PASS ✓' if len(poi_family) >= 2 else 'FAIL ✗'} (should have 2+ POI)")

# ============================================================================
# TEST 3: Target group filtering - seniors (no kids_only)
# ============================================================================
print_test_header(3, "Target group filtering - seniors (exclude kids_only)")

user_seniors = {
    "target_group": "seniors",
    "children_age": None,
    "crowd_tolerance": 0,  # Low crowd tolerance
    "budget": 2,
    "daily_limit": None,
    "group_size": 2,
    "preferences": ["culture_heritage"],
    "travel_style": "relaxed",
}

plan_seniors = build_day(
    pois=pois,
    user=user_seniors,
    context=context_winter,
    day_start="10:00",  # Later start
    day_end="17:00",  # Earlier end
)

poi_seniors, cost_seniors = analyze_plan(plan_seniors, "Seniors")

# Check no kids_only POI
has_kids_only = any(poi["kids_only"] for poi in poi_seniors)
print(f"  ✓ No kids_only POI: {not has_kids_only}")
print(f"  Status: {'PASS ✓' if not has_kids_only else 'FAIL ✗'}")

# ============================================================================
# TEST 4: Budget enforcement (strict limit 300 PLN per group)
# ============================================================================
print_test_header(4, "Budget enforcement (300 PLN limit for group of 4)")

user_budget = {
    "target_group": "family_kids",
    "children_age": 7,
    "crowd_tolerance": 1,
    "budget": 2,
    "daily_limit": 300,  # STRICT LIMIT
    "group_size": 4,
    "preferences": ["family_friendly"],
    "travel_style": "balanced",
}

plan_budget = build_day(
    pois=pois,
    user=user_budget,
    context=context_winter,
    day_start="09:00",
    day_end="18:00",
)

poi_budget, cost_per_person_budget = analyze_plan(plan_budget, "Budget limit 300 PLN")

# Calculate total group cost
total_group_cost = cost_per_person_budget * 4
print(f"  Total group cost: {cost_per_person_budget} × 4 = {total_group_cost} PLN")
print(f"  Limit: 300 PLN")
budget_ok = total_group_cost <= 300
print(f"  Status: {'PASS ✓' if budget_ok else 'FAIL ✗'} (total {total_group_cost} ≤ 300)")

# ============================================================================
# TEST 5: Intensity filtering - seniors avoid 'high' intensity
# ============================================================================
print_test_header(5, "Intensity filtering - seniors (avoid high intensity)")

# Check if any POI have high intensity (should not for seniors)
high_intensity_count = sum(1 for poi in poi_seniors if poi.get("intensity", "").lower() == "high")
print(f"  High intensity POI count: {high_intensity_count}")
print(f"  Status: {'PASS ✓' if high_intensity_count == 0 else 'FAIL ✗'} (should be 0)")

# ============================================================================
# TEST 6: Tag preferences scoring - must_see_only
# ============================================================================
print_test_header(6, "Tag preferences scoring - must_see_only")

user_must_see = {
    "target_group": "couples",
    "children_age": None,
    "crowd_tolerance": 1,
    "budget": 2,
    "daily_limit": None,
    "group_size": 2,
    "preferences": ["must_see_only", "nature_landscapes"],
    "travel_style": "balanced",
}

plan_must_see = build_day(
    pois=pois,
    user=user_must_see,
    context=context_winter,
    day_start="09:00",
    day_end="18:00",
)

poi_must_see, cost_must_see = analyze_plan(plan_must_see, "Must-see preferences")

# Check if high-scoring POI like Morskie Oko appear
has_high_score = any("Morskie Oko" in item.get("name", "") or "Dolina" in item.get("name", "") 
                     for item in plan_must_see if item["type"] == "attraction")
print(f"  ✓ Contains high must_see_score POI: {has_high_score}")
print(f"  Status: {'PASS ✓' if has_high_score else 'FAIL ✗'}")

# ============================================================================
# TEST 7: Kids-focused POI limit (max 1 per day for non-family)
# ============================================================================
print_test_header(7, "Kids-focused POI limit (friends group)")

user_friends = {
    "target_group": "friends",
    "children_age": None,
    "crowd_tolerance": 2,
    "budget": 2,
    "daily_limit": None,
    "group_size": 3,
    "preferences": ["adventure", "nature_landscapes"],
    "travel_style": "active",
}

plan_friends = build_day(
    pois=pois,
    user=user_friends,
    context=context_winter,
    day_start="09:00",
    day_end="18:00",
)

poi_friends, cost_friends = analyze_plan(plan_friends, "Friends (no kids)")

# Count kids-focused POI (should be ≤1)
kids_focused_count = sum(1 for poi in poi_friends if poi.get("kids_only", False))
print(f"  Kids-focused POI count: {kids_focused_count}")
print(f"  Status: {'PASS ✓' if kids_focused_count <= 1 else 'FAIL ✗'} (should be ≤1)")

# ============================================================================
# TEST 8: No budget limit (backward compatibility)
# ============================================================================
print_test_header(8, "No budget limit (backward compatibility)")

user_no_limit = {
    "target_group": "family_kids",
    "children_age": 8,
    "crowd_tolerance": 1,
    "budget": 2,
    "daily_limit": None,  # NO LIMIT
    "group_size": 4,
    "preferences": ["family_friendly"],
    "travel_style": "balanced",
}

plan_no_limit = build_day(
    pois=pois,
    user=user_no_limit,
    context=context_winter,
    day_start="09:00",
    day_end="18:00",
)

poi_no_limit, cost_no_limit = analyze_plan(plan_no_limit, "No budget limit")

print(f"  Status: {'PASS ✓' if len(poi_no_limit) >= 3 else 'FAIL ✗'} (should work without limit)")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("ETAP 1 SYSTEM VERIFICATION SUMMARY")
print("=" * 80)

tests = [
    ("Multi-season (Winter)", has_morskie, "Morskie Oko in winter plan"),
    ("Target: family_kids", len(poi_family) >= 2, f"{len(poi_family)} POI for family"),
    ("Target: seniors (no kids)", not has_kids_only, "No kids_only POI"),
    ("Budget: 300 PLN limit", budget_ok, f"Total {total_group_cost} ≤ 300 PLN"),
    ("Intensity: seniors", high_intensity_count == 0, "No high intensity"),
    ("Tag scoring: must_see", has_high_score, "High-score POI present"),
    ("Kids limit: friends", kids_focused_count <= 1, f"{kids_focused_count} kids POI"),
    ("No budget limit", len(poi_no_limit) >= 3, f"{len(poi_no_limit)} POI without limit"),
]

passed = sum(1 for _, result, _ in tests if result)
total = len(tests)

print(f"\nResults: {passed}/{total} tests passed\n")

for i, (name, result, detail) in enumerate(tests, 1):
    status = "✓ PASS" if result else "✗ FAIL"
    print(f"  {i}. {name}: {status} ({detail})")

print("\n" + "=" * 80)
if passed == total:
    print("🎉 ALL TESTS PASSED - Etap 1 system working correctly!")
else:
    print(f"⚠️  {total - passed} TEST(S) FAILED - Review implementation")
print("=" * 80)
