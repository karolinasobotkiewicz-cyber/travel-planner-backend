"""
Test Problem #6: Quality Badges Consistency

BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #6):
Client issue: "Ten sam POI raz ma must_see/core_attraction, innym razem nic"

Requirements:
- Badges should be deterministic for the same POI + user profile
- Same POI should get same badges regardless of time_of_day
- No time-dependent badges that cause inconsistency

Solution:
- Removed "perfect_timing" badge (was time-dependent)
- All badges now deterministic based on POI properties + user profile
"""
import sys
sys.path.insert(0, '.')

from app.domain.planner.quality_checker import check_poi_quality

print("="*80)
print("TEST: Problem #6 - Quality Badges Consistency")
print("="*80)

# Test POI with priority = 12 (core attraction)
test_poi = {
    "id": "poi_1",
    "name": "Wielka Krokiew",
    "priority_level": 12,
    "najlepszy_czas_dnia": "morning",  # Optimal time is morning
    "zależność_od_pogody": "outdoor",
    "target_groups": ["solo", "couples", "friends", "family_kids"],
    "cena_bilet_normalny": 15
}

# Test user profile
user = {
    "target_group": "family_kids",
    "budget_level": 2
}

# Test 1: Call with morning context (optimal time)
print("\nTEST 1: POI visited at optimal time (morning)")
context_morning = {
    "time_of_day": "morning",
    "weather": "sunny"
}
badges_morning = check_poi_quality(test_poi, context_morning, user)
print(f"Context: time_of_day = morning")
print(f"Badges: {badges_morning}")

# Test 2: Call with afternoon context (non-optimal time)
print("\nTEST 2: Same POI visited at non-optimal time (afternoon)")
context_afternoon = {
    "time_of_day": "afternoon",
    "weather": "sunny"
}
badges_afternoon = check_poi_quality(test_poi, context_afternoon, user)
print(f"Context: time_of_day = afternoon")
print(f"Badges: {badges_afternoon}")

# Test 3: Call with evening context (non-optimal time)
print("\nTEST 3: Same POI visited at non-optimal time (evening)")
context_evening = {
    "time_of_day": "evening",
    "weather": "sunny"
}
badges_evening = check_poi_quality(test_poi, context_evening, user)
print(f"Context: time_of_day = evening")
print(f"Badges: {badges_evening}")

# Validation
print("\n" + "="*80)
print("VALIDATION")
print("="*80)

if badges_morning == badges_afternoon == badges_evening:
    print("\nPASS: Badges are consistent regardless of time_of_day")
    print(f"   All contexts return: {badges_morning}")
    print("\n   Problem #6 FIXED:")
    print("   - Removed time-dependent 'perfect_timing' badge")
    print("   - Badges now deterministic for same POI + user profile")
    print("   - Same POI always gets same badges")
else:
    print("\nFAIL: Badges differ across contexts")
    print(f"   Morning: {badges_morning}")
    print(f"   Afternoon: {badges_afternoon}")
    print(f"   Evening: {badges_evening}")

# Test 4: Verify expected badges
print("\n" + "="*80)
print("EXPECTED BADGES CHECK")
print("="*80)

expected_badges = ["must_see", "core_attraction", "family_favorite"]
print(f"\nExpected badges: {expected_badges}")
print(f"Actual badges: {badges_morning}")

if set(badges_morning) == set(expected_badges):
    print("\nPASS: All expected badges present")
    print("   - must_see (priority >= 11)")
    print("   - core_attraction (priority == 12)")
    print("   - family_favorite (family_kids in target_groups)")
else:
    missing = set(expected_badges) - set(badges_morning)
    extra = set(badges_morning) - set(expected_badges)
    if missing:
        print(f"\n   Missing badges: {missing}")
    if extra:
        print(f"   Extra badges: {extra}")

print("\n" + "="*80)
