"""Check POI tags for Problem #5: why_selected illogical reasons"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"Loaded {len(pois)} POIs\n")
print("="*80)
print("PROBLEM #5: why_selected Illogical Reasons")
print("="*80)

# Test Case 1: Dom do góry nogami
print("\n🔍 TEST CASE 1: Dom do góry nogami")
print("-" * 80)
dom = [p for p in pois if 'Dom do g' in p.get('name', '')]
if dom:
    p = dom[0]
    print(f"Name: {p.get('name')}")
    print(f"ID: {p.get('id')}")
    print(f"Type: {p.get('type')}")
    print(f"Tags: {p.get('tags')}")
    print(f"Target groups: {p.get('target_groups')}")
    print(f"Priority: {p.get('priority_level')}")
    
    # Check if tags contain museum/heritage/mountain_views
    tags_list = p.get('tags', [])
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(',')]
    
    print(f"\n❌ ERROR in client feedback:")
    print(f"   - why_selected: 'Great for museum_heritage lovers'")
    print(f"   - why_selected: 'Breathtaking mountain views'")
    
    print(f"\n✅ ACTUAL POI ATTRIBUTES:")
    has_museum = any(tag in str(tags_list).lower() for tag in ['museum', 'heritage', 'cultural'])
    has_views = any(tag in str(tags_list).lower() for tag in ['viewpoint', 'scenic', 'panorama', 'mountain_view', 'nature_landscape'])
    print(f"   - Has museum/heritage tags: {has_museum}")
    print(f"   - Has viewpoint/scenic tags: {has_views}")
    print(f"   - Likely category: Instagram/novelty/short attraction")
else:
    print("   ⚠️  NOT FOUND in dataset")

# Test Case 2: Wielka Krokiew
print("\n\n🔍 TEST CASE 2: Wielka Krokiew")
print("-" * 80)
krokiew = [p for p in pois if 'Wielka Krokiew' in p.get('name', '')]
if krokiew:
    p = krokiew[0]
    print(f"Name: {p.get('name')}")
    print(f"ID: {p.get('id')}")
    print(f"Type: {p.get('type')}")
    print(f"Tags: {p.get('tags')}")
    print(f"Target groups: {p.get('target_groups')}")
    print(f"Priority: {p.get('priority_level')}")
    
    tags_list = p.get('tags', [])
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(',')]
    
    print(f"\n❌ ERROR in client feedback:")
    print(f"   - why_selected: 'nature_landscape lovers' - naciągane")
    
    print(f"\n✅ ACTUAL POI ATTRIBUTES:")
    has_nature = any(tag in str(tags_list).lower() for tag in ['nature_landscape', 'mountain_trails', 'hiking'])
    has_viewpoint = any(tag in str(tags_list).lower() for tag in ['viewpoint', 'scenic', 'panorama'])
    has_sport = any(tag in str(tags_list).lower() for tag in ['sport', 'active', 'landmark'])
    print(f"   - Has nature_landscape/hiking tags: {has_nature}")
    print(f"   - Has viewpoint/scenic tags: {has_viewpoint}")
    print(f"   - Has sport/landmark tags: {has_sport}")
    print(f"   - Likely category: active_sport / landmark / viewpoint")
else:
    print("   ⚠️  NOT FOUND in dataset")

# Summary
print("\n\n" + "="*80)
print("ROOT CAUSE ANALYSIS")
print("="*80)
print("""
Current explainability.py logic (Lines 64-74):

    matched_prefs = []
    for pref in preferences:
        pref_lower = pref.lower()
        if pref_lower in poi_tags or pref_lower in poi_type:
            matched_prefs.append(pref)
    
    if matched_prefs:
        prefs_text = " and ".join(matched_prefs[:2])
        reasons.append(f"Great for {prefs_text} lovers")

PROBLEM: This checks if user preference is in poi_tags, but if user has
         "museum_heritage" preference and POI doesn't have that tag,
         the code should NOT add this reason.

ADDITIONAL ISSUE (Lines 107-115):
    elif "góry" in poi_name or "morskie oko" in poi_name or "kościeliska" in poi_name:
        reasons.append("Breathtaking mountain views")

PROBLEM: This generates "mountain views" based ONLY on name substring matching,
         not on actual POI tags like "viewpoint", "scenic", "panorama".

SOLUTION:
1. Validate preferences match MORE strictly (check POI tags, not just substring)
2. Replace name-based logic with tag-based validation
3. Only generate reasons that match POI's actual attributes (tags + type)
""")
