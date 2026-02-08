"""
TEST: Premium Experience Scoring
Verify KULIGI has premium_experience flag and scoring penalty works correctly.
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.scoring import calculate_premium_penalty

# Load POI
pois = load_zakopane_poi("data/zakopane.xlsx")
print(f"OK - Loaded {len(pois)} POI\n")

# Find KULIGI
kuligi = None
for poi in pois:
    if "KULIGI" in poi.get("name", "").upper():
        kuligi = poi
        break

if not kuligi:
    print("✗ FAIL: KULIGI not found in POI list")
    sys.exit(1)

print("=" * 80)
print("TEST 1: KULIGI has premium_experience flag")
print("=" * 80)

is_premium = kuligi.get("premium_experience", False)
print(f"  KULIGI premium_experience: {is_premium}")
print(f"  KULIGI ticket_price: {kuligi.get('ticket_price')} PLN/osoba")

if is_premium:
    print(f"  Status: ✓ PASS (KULIGI marked as premium)")
else:
    print(f"  Status: ✗ FAIL (KULIGI should be premium)")
    sys.exit(1)

print("\n" + "=" * 80)
print("TEST 2: Premium penalty at budget level 1 (budget)")
print("=" * 80)

user_budget = {"budget": 1}  # Budget level
penalty = calculate_premium_penalty(kuligi, user_budget)
expected_penalty = -40

print(f"  User budget level: 1 (budget)")
print(f"  Expected penalty: {expected_penalty}")
print(f"  Actual penalty: {penalty}")

if penalty == expected_penalty:
    print(f"  Status: ✓ PASS (Correct penalty for budget level)")
else:
    print(f"  Status: ✗ FAIL (Expected {expected_penalty}, got {penalty})")
    sys.exit(1)

print("\n" + "=" * 80)
print("TEST 3: Premium penalty at budget level 2 (standard)")
print("=" * 80)

user_standard = {"budget": 2}  # Standard level
penalty = calculate_premium_penalty(kuligi, user_standard)
expected_penalty = -20

print(f"  User budget level: 2 (standard)")
print(f"  Expected penalty: {expected_penalty}")
print(f"  Actual penalty: {penalty}")

if penalty == expected_penalty:
    print(f"  Status: ✓ PASS (Correct penalty for standard level)")
else:
    print(f"  Status: ✗ FAIL (Expected {expected_penalty}, got {penalty})")
    sys.exit(1)

print("\n" + "=" * 80)
print("TEST 4: No penalty at budget level 3 (high)")
print("=" * 80)

user_high = {"budget": 3}  # High level
penalty = calculate_premium_penalty(kuligi, user_high)
expected_penalty = 0

print(f"  User budget level: 3 (high)")
print(f"  Expected penalty: {expected_penalty}")
print(f"  Actual penalty: {penalty}")

if penalty == expected_penalty:
    print(f"  Status: ✓ PASS (No penalty for high budget)")
else:
    print(f"  Status: ✗ FAIL (Expected {expected_penalty}, got {penalty})")
    sys.exit(1)

print("\n" + "=" * 80)
print("TEST 5: Non-premium POI has no penalty")
print("=" * 80)

# Find non-premium POI (e.g., Morskie Oko)
morskie_oko = None
for poi in pois:
    if "Morskie Oko" in poi.get("name", ""):
        morskie_oko = poi
        break

if morskie_oko:
    is_premium = morskie_oko.get("premium_experience", False)
    penalty = calculate_premium_penalty(morskie_oko, user_budget)
    
    print(f"  POI: {morskie_oko.get('name')}")
    print(f"  premium_experience: {is_premium}")
    print(f"  Penalty: {penalty}")
    
    if not is_premium and penalty == 0:
        print(f"  Status: ✓ PASS (Non-premium POI has no penalty)")
    else:
        print(f"  Status: ✗ FAIL (Non-premium should have 0 penalty)")
        sys.exit(1)
else:
    print("  ⚠️ SKIP: Morskie Oko not found")

print("\n" + "=" * 80)
print("✓ ALL TESTS PASSED")
print("=" * 80)
print("\nSummary:")
print(f"  ✓ KULIGI marked as premium_experience = True")
print(f"  ✓ Budget level 1 → penalty -40 (heavy)")
print(f"  ✓ Budget level 2 → penalty -20 (moderate)")
print(f"  ✓ Budget level 3 → penalty 0 (none)")
print(f"  ✓ Non-premium POI → penalty 0")
print("\n🎉 Premium experience scoring working correctly!")
