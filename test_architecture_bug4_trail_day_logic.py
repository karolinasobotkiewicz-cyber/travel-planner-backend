"""
Test for ARCHITECTURE BUG #4: Trail day logic (27.04.2026 - CLIENT FEEDBACK)

Problem: Trails treated like regular POI (trail + 5 POI + lunch + dinner)
Expected: Trail = main activity + max 1-2 light POI after (only if trail <4h)
Solution: HARD FILTER based on trail duration

Trail day rules:
1. Max 1 trail per day
2. Long trail (>=4h) -> NO additional POI (only lunch/dinner)
3. Short trail (<4h) -> max 2 light POI (<=60min each)

Test cases:
1. Long trail (Rysy 11h) -> expect ONLY trail in attractions
2. Short trail (Giewont 3.5h) -> expect trail + 1-2 light POI (<=60min)
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.domain.planner.engine import build_day


def test_trail_day_logic():
    """Test that trail days limit POI based on trail duration"""
    print("="*80)
    print("TEST: Trail Day Logic (Bug #4)")
    print("="*80)
    
    # Mock POIs: 1 long trail + 1 short trail + 3 regular POI (1 light, 2 long)
    pois = [
        {
            "id": "rysy",
            "type": "trail",
            "name": "Rysy",
            "difficulty_level": "difficult",
            "duration_min": 660,  # 11 hours - LONG TRAIL
            "duration_max": 780,
            "priorytet": 20,
            "tags": ["mountain", "hiking", "difficult"],
            "target_groups": ["friends", "adventure_seekers"],
            "lat": 49.1794,
            "lng": 20.0880
        },
        {
            "id": "giewont",
            "type": "trail",
            "name": "Giewont",
            "difficulty_level": "moderate",
            "duration_min": 210,  # 3.5 hours - SHORT TRAIL
            "duration_max": 250,
            "priorytet": 12,
            "tags": ["mountain", "hiking"],
            "target_groups": ["friends", "couples"],
            "lat": 49.1794,
            "lng": 20.0880
        },
        {
            "id": "morskie_oko",
            "type": "poi",
            "Name": "Morskie Oko",
            "priorytet": 15,
            "typ": "nature",
            "czas_zwiedzania_min": 120,  # 2 hours - LONG POI
            "tags": ["lake", "nature"],
            "target_groups": ["family_kids", "friends", "couples"],
            "lat": 49.2016,
            "lng": 20.0707
        },
        {
            "id": "gubalowka",
            "type": "poi",
            "Name": "Gubalowka",
            "priorytet": 10,
            "typ": "viewpoint",
            "czas_zwiedzania_min": 45,  # 45 min - LIGHT POI
            "tags": ["viewpoint", "scenic"],
            "target_groups": ["family_kids", "friends", "couples", "seniors"],
            "lat": 49.2864,
            "lng": 19.9486
        },
        {
            "id": "krupowki",
            "type": "poi",
            "Name": "Krupowki",
            "priorytet": 10,
            "typ": "shopping",
            "czas_zwiedzania_min": 90,  # 1.5 hours - LONG POI
            "tags": ["shopping", "culture"],
            "target_groups": ["family_kids", "friends", "couples", "seniors"],
            "lat": 49.2964,
            "lng": 19.9486
        },
        {
            "id": "chocholowskie",
            "type": "poi",
            "Name": "Termy Chocholowskie",
            "priorytet": 8,
            "typ": "spa",
            "czas_zwiedzania_min": 50,  # 50 min - LIGHT POI
            "tags": ["spa", "relaxation"],
            "target_groups": ["couples", "seniors"],
            "lat": 49.3964,
            "lng": 19.7486
        }
    ]
    
    # User with hiking preferences (trails allowed)
    user_hiking = {
        "target_group": "friends",
        "budget_level": 2,
        "preferences": ["mountain_trails", "nature", "outdoor"],
        "special_needs": []
    }
    
    context = {
        "city_name": "Zakopane",
        "destination_type": "city",
        "days_count": 1
    }
    
    # =========================================================================
    # Test Case 1: Long trail (Rysy 11h) -> NO additional POI
    # =========================================================================
    print("\n[Test Case 1] Long trail (Rysy 11h)")
    print("-"*80)
    print("Trail: Rysy (11h duration)")
    print("Expected: ONLY trail (NO additional POI, only lunch/dinner allowed)")
    
    # Use only Rysy + other POI (exclude short trail)
    pois_long_trail = [pois[0], pois[2], pois[3], pois[4], pois[5]]  # Rysy + 4 POI
    
    plan_long = build_day(pois_long_trail, user_hiking, context, day_start="08:00", day_end="20:00")
    
    # build_day returns list of items
    plan_items_long = plan_long if isinstance(plan_long, list) else plan_long.get("items", [])
    
    print(f"\n[DEBUG] Plan items for long trail:")
    attractions_long = []
    for item in plan_items_long:
        item_type = item.get("type")
        if item_type == "attraction":
            poi = item.get("poi", {})
            name_safe = str(poi.get('name', 'unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"  - {item_type}: id={poi.get('id')}, type={poi.get('type')}, name={name_safe}, "
                  f"duration={poi.get('duration_min', poi.get('czas_zwiedzania_min', 0))}min")
            attractions_long.append(poi.get("id"))
        elif item_type in ["lunch_break", "dinner"]:
            print(f"  - {item_type}: {item.get('start_time')}-{item.get('end_time')}")
    
    # Count attractions (excluding lunch/dinner)
    attraction_count_long = sum(
        1 for item in plan_items_long
        if item.get("type") == "attraction"
    )
    
    print(f"\nAttractions in plan: {attraction_count_long}")
    print(f"Expected: 1 (only trail)")
    
    if attraction_count_long == 1 and "rysy" in attractions_long:
        print("CORRECT: Only trail in plan (long trail blocks other POI)")
        test1_pass = True
    else:
        print(f"BUG: {attraction_count_long} attractions (should be 1 - only Rysy)")
        print(f"   Attractions: {attractions_long}")
        test1_pass = False
    
    # =========================================================================
    # Test Case 2: Short trail (Giewont 3.5h) -> trail + 1-2 light POI
    # =========================================================================
    print("\n[Test Case 2] Short trail (Giewont 3.5h)")
    print("-"*80)
    print("Trail: Giewont (3.5h duration)")
    print("Expected: Trail + max 2 light POI (<=60min each)")
    print("Available light POI: Gubalowka (45min), Termy Chocholowskie (50min)")
    print("Available long POI: Morskie Oko (120min), Krupowki (90min) - should be BLOCKED")
    
    # Use only Giewont + other POI (exclude long trail Rysy)
    pois_short_trail = [pois[1], pois[2], pois[3], pois[4], pois[5]]  # Giewont + 4 POI
    
    plan_short = build_day(pois_short_trail, user_hiking, context, day_start="08:00", day_end="19:00")
    
    # build_day returns list of items
    plan_items_short = plan_short if isinstance(plan_short, list) else plan_short.get("items", [])
    
    print(f"\n[DEBUG] Plan items for short trail:")
    attractions_short = []
    light_poi_count = 0
    long_poi_found = []
    for item in plan_items_short:
        item_type = item.get("type")
        if item_type == "attraction":
            poi = item.get("poi", {})
            poi_id = poi.get("id")
            poi_type = poi.get("type")
            duration = poi.get('duration_min', poi.get('czas_zwiedzania_min', 0))
            name_safe = str(poi.get('name', 'unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"  - {item_type}: id={poi_id}, type={poi_type}, name={name_safe}, duration={duration}min")
            
            attractions_short.append(poi_id)
            
            if poi_type != "trail":
                if duration <= 60:
                    light_poi_count += 1
                else:
                    long_poi_found.append(poi_id)
        elif item_type in ["lunch_break", "dinner"]:
            print(f"  - {item_type}: {item.get('start_time')}-{item.get('end_time')}")
    
    # Count attractions
    attraction_count_short = sum(
        1 for item in plan_items_short
        if item.get("type") == "attraction"
    )
    
    trail_count = 1 if "giewont" in attractions_short else 0
    
    print(f"\nAttractions in plan: {attraction_count_short} total")
    print(f"  - Trail: {trail_count}")
    print(f"  - Light POI (<=60min): {light_poi_count}")
    print(f"  - Long POI (>60min): {len(long_poi_found)}")
    
    # Validation
    test2_pass = True
    
    if trail_count != 1:
        print(f"BUG: Expected 1 trail, got {trail_count}")
        test2_pass = False
    
    if light_poi_count > 2:
        print(f"BUG: Too many light POI after trail: {light_poi_count}/2")
        test2_pass = False
    
    if long_poi_found:
        print(f"BUG: Long POI should be BLOCKED on trail day: {long_poi_found}")
        test2_pass = False
    
    if test2_pass:
        print(f"CORRECT: Trail + {light_poi_count} light POI (<=2), NO long POI")
    
    # =========================================================================
    # Final result
    # =========================================================================
    print("\n" + "="*80)
    print("TEST RESULT:")
    print("="*80)
    
    success = test1_pass and test2_pass
    
    if success:
        print("SUCCESS: Trail day logic working correctly")
        print("   - Long trail (11h) -> only trail in plan")
        print("   - Short trail (3.5h) -> trail + light POI only (max 2)")
        return True
    else:
        print("FAILURE: Trail day logic not working")
        if not test1_pass:
            print("   - Long trail should block all other POI")
        if not test2_pass:
            print("   - Short trail should allow max 2 light POI (<=60min)")
        return False


if __name__ == "__main__":
    success = test_trail_day_logic()
    sys.exit(0 if success else 1)
