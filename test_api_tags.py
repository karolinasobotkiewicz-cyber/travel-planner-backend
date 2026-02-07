"""
Manual API test: Generate plan with tag preferences
Test endpoint: POST /plan/preview
"""

import requests
import json

API_URL = "http://localhost:8000"

def test_water_preferences():
    """Test plan generation with water_attractions preference"""
    print("=" * 80)
    print("🧪 TEST API: Water Attractions Preference")
    print("=" * 80)
    
    payload = {
        "user": {
            "target_group": "family_kids",
            "budget_level": 2,
            "crowd_tolerance": 2,
            "preferences": ["water_attractions"],  # NEW: Tag preference
            "travel_style": ["relaxed"],
            "intensity_level": 2,
        },
        "trip": {
            "destination": "zakopane",
            "start_date": "2026-02-05",
            "end_date": "2026-02-05",
            "start_time": "09:00",
            "end_time": "18:00"
        }
    }
    
    print(f"\n📤 POST {API_URL}/plan/preview")
    print(f"Preferences: {payload['user']['preferences']}")
    
    response = requests.post(f"{API_URL}/plan/preview", json=payload)
    
    print(f"\n📥 Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        plan = data.get("plan", [])
        
        print(f"\n✅ Plan generated with {len(plan)} POI:")
        print("=" * 80)
        
        # Check for water-related POI (Termy)
        water_poi = [p for p in plan if "Termy" in p.get("name", "") or "thermal" in str(p.get("tags", [])).lower()]
        
        for i, poi in enumerate(plan, 1):
            poi_name = poi.get("name", "Unknown")
            poi_tags = poi.get("tags", [])
            poi_time = poi.get("time", "")
            
            is_water = "Termy" in poi_name or any("thermal" in str(t).lower() for t in poi_tags)
            prefix = "🌊" if is_water else "  "
            
            print(f"{prefix} {i}. {poi_time} - {poi_name}")
            if poi_tags and len(poi_tags) > 0:
                print(f"      Tags: {', '.join(poi_tags[:5])}")
        
        print(f"\n📊 Water-related POI in plan: {len(water_poi)}")
        for p in water_poi:
            print(f"   🌊 {p.get('name')}")
        
        if water_poi:
            print("\n✅ SUCCESS: Water attractions boosted by tag preferences!")
        else:
            print("\n⚠️  WARNING: No water attractions in plan (check scoring)")
    else:
        print(f"❌ ERROR: {response.status_code}")
        print(response.text)


def test_kids_preferences():
    """Test plan generation with attractions_for_kids preference"""
    print("\n\n" + "=" * 80)
    print("🧪 TEST API: Kids Attractions Preference")
    print("=" * 80)
    
    payload = {
        "user": {
            "target_group": "family_kids",
            "budget_level": 2,
            "crowd_tolerance": 2,
            "preferences": ["attractions_for_kids"],  # NEW: Tag preference
            "travel_style": ["relaxed"],
            "intensity_level": 2,
        },
        "trip": {
            "destination": "zakopane",
            "start_date": "2026-02-05",
            "end_date": "2026-02-05",
            "start_time": "09:00",
            "end_time": "18:00"
        }
    }
    
    print(f"\n📤 POST {API_URL}/plan/preview")
    print(f"Preferences: {payload['user']['preferences']}")
    
    response = requests.post(f"{API_URL}/plan/preview", json=payload)
    
    print(f"\n📥 Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        plan = data.get("plan", [])
        
        print(f"\n✅ Plan generated with {len(plan)} POI:")
        print("=" * 80)
        
        # Check for kids-related POI
        kids_poi = [p for p in plan if p.get("type") == "kids_attractions" or 
                    any("kids" in str(t).lower() for t in p.get("tags", []))]
        
        for i, poi in enumerate(plan, 1):
            poi_name = poi.get("name", "Unknown")
            poi_type = poi.get("type", "")
            poi_tags = poi.get("tags", [])
            poi_time = poi.get("time", "")
            
            is_kids = poi_type == "kids_attractions" or any("kids" in str(t).lower() for t in poi_tags)
            prefix = "🎈" if is_kids else "  "
            
            print(f"{prefix} {i}. {poi_time} - {poi_name}")
            if poi_type:
                print(f"      Type: {poi_type}")
        
        print(f"\n📊 Kids-related POI in plan: {len(kids_poi)}")
        for p in kids_poi:
            print(f"   🎈 {p.get('name')}")
        
        if kids_poi:
            print("\n✅ SUCCESS: Kids attractions boosted by tag preferences!")
        else:
            print("\n⚠️  WARNING: No kids attractions in plan")
    else:
        print(f"❌ ERROR: {response.status_code}")
        print(response.text)


def test_no_preferences():
    """Test plan generation without preferences (backward compat)"""
    print("\n\n" + "=" * 80)
    print("🧪 TEST API: No Preferences (Backward Compat)")
    print("=" * 80)
    
    payload = {
        "user": {
            "target_group": "family_kids",
            "budget_level": 2,
            "crowd_tolerance": 2,
            "preferences": [],  # Empty preferences
            "travel_style": ["relaxed"],
            "intensity_level": 2,
        },
        "trip": {
            "destination": "zakopane",
            "start_date": "2026-02-05",
            "end_date": "2026-02-05",
            "start_time": "09:00",
            "end_time": "18:00"
        }
    }
    
    print(f"\n📤 POST {API_URL}/plan/preview")
    print(f"Preferences: {payload['user']['preferences']}")
    
    response = requests.post(f"{API_URL}/plan/preview", json=payload)
    
    print(f"\n📥 Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        plan = data.get("plan", [])
        
        print(f"\n✅ Plan generated with {len(plan)} POI")
        print("=" * 80)
        
        for i, poi in enumerate(plan, 1):
            poi_name = poi.get("name", "Unknown")
            poi_time = poi.get("time", "")
            print(f"   {i}. {poi_time} - {poi_name}")
        
        if len(plan) > 0:
            print("\n✅ SUCCESS: Backward compatible (no preferences works)")
        else:
            print("\n❌ ERROR: Empty plan generated")
    else:
        print(f"❌ ERROR: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    print("=" * 80)
    print("TAG PREFERENCE SCORING - API MANUAL TESTS")
    print("=" * 80)
    
    try:
        test_water_preferences()
        test_kids_preferences()
        test_no_preferences()
        
        print("\n" + "=" * 80)
        print("✅ ALL API TESTS COMPLETE")
        print("=" * 80)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API")
        print("Make sure backend is running on http://localhost:8000")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
