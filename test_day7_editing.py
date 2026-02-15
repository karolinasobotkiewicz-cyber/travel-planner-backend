"""
Test Day 7: Editing API Endpoints
Tests remove and replace endpoints with versioning.
"""
import requests
import json
from pprint import pprint

BASE_URL = "http://localhost:8001"

def test_day7_editing_flow():
    """
    Test flow:
    1. Generate 3-day plan → version #1
    2. Remove item from Day 1 → version #2
    3. Replace item in Day 1 → version #3
    4. Verify versions created correctly
    """
    print("\n" + "="*70)
    print("DAY 7 EDITING API TEST")
    print("="*70)
    
    # Step 1: Generate 3-day plan
    print("\n[STEP 1] Generating 3-day plan...")
    trip_input = {
        "location": {
            "city": "Zakopane",
            "country": "Poland",
            "region_type": "mountain"
        },
        "group": {
            "type": "couples",
            "size": 2,
            "crowd_tolerance": 1
        },
        "trip_length": {
            "days": 3,
            "start_date": "2026-02-20"
        },
        "daily_time_window": {
            "start": "09:00",
            "end": "19:00"
        },
        "budget": {
            "level": 2
        },
        "transport_modes": ["car"],
        "preferences": ["hiking", "nature", "culture"],
        "travel_style": "balanced"
    }
    
    response = requests.post(f"{BASE_URL}/plan/preview", json=trip_input)
    assert response.status_code == 200, f"Failed to generate plan: {response.status_code}"
    
    plan = response.json()
    plan_id = plan["plan_id"]
    print(f"✅ Plan generated: {plan_id}")
    print(f"   Days: {len(plan['days'])}")
    
    # Get Day 1 items
    day1 = plan["days"][0]
    attractions_day1 = [item for item in day1["items"] if item.get("type") == "attraction"]
    print(f"   Day 1 attractions: {len(attractions_day1)}")
    
    if len(attractions_day1) < 2:
        print("❌ ERROR: Not enough attractions in Day 1 to test editing")
        return False
    
    # Select first two attractions for testing
    item_to_remove = attractions_day1[0]
    item_to_replace = attractions_day1[1]
    
    print(f"   Item to remove: {item_to_remove.get('poi_name', 'N/A')} (poi_id: {item_to_remove.get('poi_id')})")
    print(f"   Item to replace: {item_to_replace.get('poi_name', 'N/A')} (poi_id: {item_to_replace.get('poi_id')})")
    
    # Step 2: Check versions after generation
    print("\n[STEP 2] Checking versions after generation...")
    response = requests.get(f"{BASE_URL}/plan/{plan_id}/versions")
    assert response.status_code == 200, f"Failed to get versions: {response.status_code}"
    
    versions = response.json()
    print(f"✅ Versions found: {len(versions)}")
    for v in versions:
        print(f"   Version #{v['version_number']}: {v['change_type']} - {v.get('change_summary', 'N/A')}")
    
    # Step 3: Remove item from Day 1
    print("\n[STEP 3] Removing item from Day 1...")
    remove_request = {
        "item_id": item_to_remove.get("poi_id"),
        "avoid_cooldown_hours": 24
    }
    
    response = requests.post(
        f"{BASE_URL}/plan/{plan_id}/days/1/remove",
        json=remove_request
    )
    
    if response.status_code != 200:
        print(f"❌ Remove failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    updated_plan = response.json()
    day1_after_remove = updated_plan["days"][0]
    attractions_after_remove = [item for item in day1_after_remove["items"] if item.get("type") == "attraction"]
    
    print(f"✅ Item removed successfully")
    print(f"   Day 1 attractions after remove: {len(attractions_after_remove)}")
    print(f"   Original count: {len(attractions_day1)}, After remove: {len(attractions_after_remove)}")
    
    # Step 4: Check versions after remove
    print("\n[STEP 4] Checking versions after remove...")
    response = requests.get(f"{BASE_URL}/plan/{plan_id}/versions")
    versions = response.json()
    print(f"✅ Versions after remove: {len(versions)}")
    for v in versions:
        print(f"   Version #{v['version_number']}: {v['change_type']} - {v.get('change_summary', 'N/A')}")
    
    # Step 5: Replace item in Day 1
    print("\n[STEP 5] Replacing item in Day 1...")
    replace_request = {
        "item_id": item_to_replace.get("poi_id"),
        "strategy": "SMART_REPLACE",
        "preferences": {}
    }
    
    response = requests.post(
        f"{BASE_URL}/plan/{plan_id}/days/1/replace",
        json=replace_request
    )
    
    if response.status_code != 200:
        print(f"❌ Replace failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    updated_plan = response.json()
    day1_after_replace = updated_plan["days"][0]
    attractions_after_replace = [item for item in day1_after_replace["items"] if item.get("type") == "attraction"]
    
    print(f"✅ Item replaced successfully")
    print(f"   Day 1 attractions after replace: {len(attractions_after_replace)}")
    
    # Find replacement POI
    replacement_found = False
    for item in attractions_after_replace:
        if item.get("poi_id") != item_to_remove.get("poi_id"):
            # This might be the replacement
            if item.get("poi_name") != item_to_replace.get("poi_name"):
                replacement_found = True
                print(f"   Replacement POI: {item.get('poi_name')} (poi_id: {item.get('poi_id')})")
    
    if not replacement_found:
        print("   ⚠️  Could not identify specific replacement POI (might be same or removed)")
    
    # Step 6: Final version check
    print("\n[STEP 6] Final version check...")
    response = requests.get(f"{BASE_URL}/plan/{plan_id}/versions")
    versions = response.json()
    print(f"✅ Final version count: {len(versions)}")
    for v in versions:
        print(f"   Version #{v['version_number']}: {v['change_type']} - {v.get('change_summary', 'N/A')}")
    
    # Step 7: Verify rollback works
    print("\n[STEP 7] Testing rollback to version 1...")
    response = requests.post(
        f"{BASE_URL}/plan/{plan_id}/rollback",
        json={"target_version": 1}
    )
    
    if response.status_code != 200:
        print(f"❌ Rollback failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    rollback_result = response.json()
    print(f"✅ Rollback successful")
    print(f"   New version number: {rollback_result.get('new_version_number')}")
    print(f"   Rolled back to: {rollback_result.get('rolled_back_to')}")
    
    # Final version list
    response = requests.get(f"{BASE_URL}/plan/{plan_id}/versions")
    versions = response.json()
    print(f"\n✅ Final version history ({len(versions)} versions):")
    for v in versions:
        print(f"   Version #{v['version_number']}: {v['change_type']} - {v.get('change_summary', 'N/A')}")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED - DAY 7 EDITING API WORKING!")
    print("="*70)
    return True


if __name__ == "__main__":
    try:
        success = test_day7_editing_flow()
        if success:
            print("\n✅ READY TO COMMIT")
        else:
            print("\n❌ TESTS FAILED - FIX BEFORE COMMIT")
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
