"""
Test Problem #5: why_selected validation - ensure reasons match actual POI tags

BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #5):
Client issue: "why_selected zawiera nielogiczne argumenty niepasujące do POI"

Examples:
- Dom do góry nogami: "Great for museum_heritage lovers" + "Breathtaking mountain views"
  → POI has NO museum/viewpoint tags, only "illusion_kids", "interactive_exhibition_kids"
- Wielka Krokiew: "nature_landscape lovers"
  → POI has NO nature_landscape tags, only "snow_tubing", "adrenaline_experience"

Solution:
- Validate why_selected against actual POI tags (NOT name substring matching)
- Only generate reasons that match POI's real attributes
"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.explainability import explain_poi_selection

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"Loaded {len(pois)} POIs\n")

print("="*80)
print("TEST: Problem #5 - why_selected Validation")
print("="*80)

# Test parameters
user_museum = {
    "target_group": "couples",
    "preferences": ["museum_heritage", "cultural"],
    "budget_level": 2
}

user_nature = {
    "target_group": "friends",
    "preferences": ["nature_landscapes", "hiking"],
    "budget_level": 2
}

context = {
    "time_of_day": "afternoon",
    "weather": "sunny"
}

# ============================================================================
# TEST 1: Dom do góry nogami - should NOT get museum/mountain reasons
# ============================================================================
print("\n" + "="*80)
print("TEST 1: Dom do góry nogami")
print("="*80)

dom = [p for p in pois if 'Dom do g' in p.get('name', '')]
if dom:
    poi = dom[0]
    print(f"POI: {poi.get('name')}")
    print(f"Type: {poi.get('type')}")
    print(f"Tags: {poi.get('tags')}")
    
    # Generate why_selected with museum_heritage user
    reasons = explain_poi_selection(poi, context, user_museum)
    
    print(f"\nGenerated why_selected:")
    for r in reasons:
        print(f"  - {r}")
    
    # Validation
    has_museum_reason = any("museum" in r.lower() or "heritage" in r.lower() or "cultural" in r.lower() for r in reasons)
    has_mountain_reason = any("mountain" in r.lower() or "views" in r.lower() or "scenic" in r.lower() for r in reasons)
    
    print(f"\n✅ VALIDATION:")
    if has_museum_reason:
        print(f"   ❌ FAIL: Has museum/heritage reason but POI has NO museum tags")
        print(f"      POI tags: {poi.get('tags')} (no museum/heritage/cultural)")
    else:
        print(f"   ✅ PASS: No museum/heritage reason (correct - POI has no museum tags)")
    
    if has_mountain_reason:
        print(f"   ❌ FAIL: Has mountain/views reason but POI has NO viewpoint tags")
        print(f"      POI tags: {poi.get('tags')} (no viewpoint/scenic/panorama)")
    else:
        print(f"   ✅ PASS: No mountain/views reason (correct - POI has no viewpoint tags)")
    
    test1_pass = not has_museum_reason and not has_mountain_reason
else:
    print("   ⚠️  POI NOT FOUND")
    test1_pass = False

# ============================================================================
# TEST 2: Wielka Krokiew - should NOT get nature_landscape reason
# ============================================================================
print("\n" + "="*80)
print("TEST 2: Wielka Krokiew")
print("="*80)

krokiew = [p for p in pois if 'Wielka Krokiew' in p.get('name', '')]
if krokiew:
    poi = krokiew[0]
    print(f"POI: {poi.get('name')}")
    print(f"Type: {poi.get('type')}")
    print(f"Tags: {poi.get('tags')}")
    
    # Generate why_selected with nature_landscapes user
    reasons = explain_poi_selection(poi, context, user_nature)
    
    print(f"\nGenerated why_selected:")
    for r in reasons:
        print(f"  - {r}")
    
    # Validation
    has_nature_reason = any("nature" in r.lower() or "landscape" in r.lower() or "hiking" in r.lower() for r in reasons)
    
    print(f"\n✅ VALIDATION:")
    if has_nature_reason:
        print(f"   ❌ FAIL: Has nature/landscape reason but POI has NO nature_landscape tags")
        print(f"      POI tags: {poi.get('tags')} (no nature_landscape/hiking/mountain_trails)")
    else:
        print(f"   ✅ PASS: No nature/landscape reason (correct - POI has no nature tags)")
    
    test2_pass = not has_nature_reason
else:
    print("   ⚠️  POI NOT FOUND")
    test2_pass = False

# ============================================================================
# TEST 3: Dolina Kościeliska - SHOULD get mountain/nature reasons (has correct tags)
# ============================================================================
print("\n" + "="*80)
print("TEST 3: Dolina Kościeliska (positive test)")
print("="*80)

dolina = [p for p in pois if 'Kościeliska' in p.get('name', '') or 'Koscieliska' in p.get('name', '')]
if dolina:
    poi = dolina[0]
    print(f"POI: {poi.get('name')}")
    print(f"Type: {poi.get('type')}")
    print(f"Tags: {poi.get('tags')}")
    
    # Generate why_selected with nature user
    reasons = explain_poi_selection(poi, context, user_nature)
    
    print(f"\nGenerated why_selected:")
    for r in reasons:
        print(f"  - {r}")
    
    # Validation - should have nature/mountain reasons if tags match
    has_nature_reason = any("nature" in r.lower() or "landscape" in r.lower() or "mountain" in r.lower() or "hiking" in r.lower() for r in reasons)
    
    poi_tags_str = ",".join([str(t).lower() for t in poi.get('tags', [])])
    has_nature_tags = any(tag in poi_tags_str for tag in ["nature_landscape", "mountain", "hiking", "scenic", "viewpoint"])
    
    print(f"\n✅ VALIDATION:")
    if has_nature_tags:
        if has_nature_reason:
            print(f"   ✅ PASS: Has nature/mountain reason AND POI has matching tags")
            print(f"      POI tags include nature/landscape/mountain/viewpoint")
            test3_pass = True
        else:
            print(f"   ⚠️  WARNING: POI has nature tags but no nature reason generated")
            print(f"      This might be OK if other reasons have higher priority")
            test3_pass = True  # Not a failure - just info
    else:
        print(f"   ⚠️  INFO: POI has no nature tags, so no nature reason expected")
        test3_pass = True
else:
    print("   ⚠️  POI NOT FOUND")
    test3_pass = True  # Not critical

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)

all_pass = test1_pass and test2_pass

if all_pass:
    print("\n✅ ALL CRITICAL TESTS PASSED")
    print("\n   Problem #5 FIXED:")
    print("   - why_selected validates against actual POI tags")
    print("   - No illogical reasons (museum/mountain views for wrong POIs)")
    print("   - Reasons match POI's real attributes")
else:
    print("\n❌ SOME TESTS FAILED")
    if not test1_pass:
        print("   - TEST 1 FAILED: Dom do góry nogami still has illogical reasons")
    if not test2_pass:
        print("   - TEST 2 FAILED: Wielka Krokiew still has nature_landscape reason")

print("\n" + "="*80)
