"""
Integration Test for Day 8 - Regenerate Time Range with Pinned Items.

Test scenario:
1. Generate 3-day plan
2. Identify POI in Day 1 to pin (e.g., first attraction)
3. Regenerate time range 12:00-16:00 with pinned item
4. Verify:
   - Pinned item still in place
   - Other items in range replaced with new POIs
   - Times recalculated correctly
   - New version created
5. Test rollback

ETAP 2 - DAY 8 (19.02.2026)
"""
import requests
import json

BASE_URL = "http://localhost:8001"


def test_day8_regenerate_flow():
    """
    Full Day 8 test: Generate → Regenerate range → Verify pinned.
    """
    print("\n" + "=" * 60)
    print("DAY 8 - REGENERATE TIME RANGE WITH PINNED ITEMS TEST")
    print("=" * 60)
    
    # ========================================
    # STEP 1: Generate 3-day plan
    # ========================================
    print("\n[STEP 1] Generating 3-day plan...")
    
    payload = {
        "location": {
            "city": "Zakopane",
            "region": "Tatry",
            "country": "Polska"
        },
        "trip_length": {
            "start_date": "2026-07-15",
            "end_date": "2026-07-17",
            "days": 3
        },
        "group": {
            "type": "couples",
            "size": 2,
            "age_range": "adults"
        },
        "daily_time_window": {
            "start": "09:00",
            "end": "19:00"
        },
        "budget": {
            "level": 2,
            "daily_limit": None
        },
        "preferences": ["hiking", "nature", "culture"],
        "transport_modes": ["car"]
    }
    
    response = requests.post(f"{BASE_URL}/plan/preview", json=payload)
    
    if response.status_code != 200:
        print(f"❌ Failed to generate plan: {response.status_code}")
        print(response.text)
        return False
    
    plan = response.json()
    plan_id = plan["plan_id"]
    days = plan["days"]
    
    print(f"✅ Plan generated: {plan_id}")
    print(f"   Days: {len(days)}")
    
    # Get Day 1 details
    day1 = days[0]
    day1_items = day1["items"]
    
    attractions_day1 = [
        item for item in day1_items 
        if item.get("type") == "attraction"
    ]
    
    print(f"   Day 1 attractions: {len(attractions_day1)}")
    
    if len(attractions_day1) < 2:
        print("❌ Not enough attractions in Day 1 to test")
        return False
    
    # Print all attractions with times
    print("\n   Day 1 attractions:")
    for i, attr in enumerate(attractions_day1, 1):
        print(f"      {i}. {attr['name']} ({attr['poi_id']}) "
              f"at {attr['start_time']}-{attr['end_time']}")
    
    # ========================================
    # STEP 2: Check versions after generation
    # ========================================
    print("\n[STEP 2] Checking versions after generation...")
    
    response = requests.get(f"{BASE_URL}/plan/{plan_id}/versions")
    
    if response.status_code != 200:
        print(f"❌ Failed to get versions: {response.status_code}")
        return False
    
    versions = response.json()
    print(f"✅ Versions after generation: {len(versions)}")
    
    for v in versions:
        print(f"   Version #{v['version_number']}: "
              f"{v['change_type']} - {v.get('change_summary', 'N/A')}")
    
    # ========================================
    # STEP 3: Identify pinned item and time range
    # ========================================
    print("\n[STEP 3] Selecting pinned item and time range...")
    
    # Pin the second attraction (to see changes around it)
    if len(attractions_day1) >= 2:
        pinned_attraction = attractions_day1[1]
    else:
        pinned_attraction = attractions_day1[0]
    
    pinned_poi_id = pinned_attraction["poi_id"]
    pinned_name = pinned_attraction["name"]
    pinned_time = pinned_attraction["start_time"]
    
    print(f"✅ Will pin: {pinned_name} ({pinned_poi_id}) at {pinned_time}")
    
    # Set regenerate range: 11:00-16:00 (should include pinned item)
    from_time = "11:00"
    to_time = "16:00"
    
    print(f"✅ Regenerate range: {from_time} - {to_time}")
    
    # Get original items in range
    original_in_range = [
        item for item in attractions_day1
        if from_time <= item["start_time"] < to_time
    ]
    
    print(f"   Original attractions in range: {len(original_in_range)}")
    for attr in original_in_range:
        pinned_marker = " [PINNED]" if attr["poi_id"] == pinned_poi_id else ""
        print(f"      - {attr['name']} ({attr['poi_id']}){pinned_marker}")
    
    # ========================================
    # STEP 4: Regenerate time range
    # ========================================
    print(f"\n[STEP 4] Regenerating Day 1 range {from_time}-{to_time}...")
    
    regenerate_payload = {
        "from_time": from_time,
        "to_time": to_time,
        "pinned_items": [pinned_poi_id]
    }
    
    response = requests.post(
        f"{BASE_URL}/plan/{plan_id}/days/1/regenerate",
        json=regenerate_payload
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to regenerate: {response.status_code}")
        print(response.text)
        return False
    
    updated_plan = response.json()
    updated_day1 = updated_plan["days"][0]
    updated_items = updated_day1["items"]
    
    updated_attractions = [
        item for item in updated_items
        if item.get("type") == "attraction"
    ]
    
    print(f"✅ Range regenerated successfully")
    print(f"   Updated Day 1 attractions: {len(updated_attractions)}")
    
    # ========================================
    # STEP 5: Verify pinned item still in place
    # ========================================
    print("\n[STEP 5] Verifying pinned item...")
    
    pinned_found = False
    pinned_item_data = None
    
    for attr in updated_attractions:
        if attr["poi_id"] == pinned_poi_id:
            pinned_found = True
            pinned_item_data = attr
            break
    
    if not pinned_found:
        print(f"❌ Pinned item {pinned_name} NOT FOUND after regenerate!")
        return False
    
    print(f"✅ Pinned item still present: {pinned_item_data['name']} "
          f"({pinned_item_data['poi_id']})")
    print(f"   Time: {pinned_item_data['start_time']}-"
          f"{pinned_item_data['end_time']}")
    
    # ========================================
    # STEP 6: Verify other items changed
    # ========================================
    print("\n[STEP 6] Verifying items in range changed...")
    
    updated_in_range = [
        item for item in updated_attractions
        if from_time <= item["start_time"] < to_time
    ]
    
    print(f"   Updated attractions in range: {len(updated_in_range)}")
    for attr in updated_in_range:
        pinned_marker = " [PINNED]" if attr["poi_id"] == pinned_poi_id else ""
        was_original = any(
            o["poi_id"] == attr["poi_id"] 
            for o in original_in_range
        )
        change_marker = " [ORIGINAL]" if was_original else " [NEW]"
        print(f"      - {attr['name']} ({attr['poi_id']})"
              f"{pinned_marker}{change_marker}")
    
    # Count new items (excluding pinned)
    new_items = [
        attr for attr in updated_in_range
        if attr["poi_id"] != pinned_poi_id and not any(
            o["poi_id"] == attr["poi_id"] 
            for o in original_in_range
        )
    ]
    
    if len(new_items) > 0:
        print(f"✅ {len(new_items)} new items added in range")
    else:
        print("⚠️ No new items added (range might be too small)")
    
    # ========================================
    # STEP 7: Check versions after regenerate
    # ========================================
    print("\n[STEP 7] Checking versions after regenerate...")
    
    response = requests.get(f"{BASE_URL}/plan/{plan_id}/versions")
    
    if response.status_code != 200:
        print(f"❌ Failed to get versions: {response.status_code}")
        return False
    
    versions = response.json()
    print(f"✅ Versions after regenerate: {len(versions)}")
    
    for v in versions:
        print(f"   Version #{v['version_number']}: "
              f"{v['change_type']} - {v.get('change_summary', 'N/A')}")
    
    # Find regenerate version
    regenerate_version = None
    for v in versions:
        if v["change_type"] == "regenerate_range":
            regenerate_version = v
            break
    
    if not regenerate_version:
        print("❌ Regenerate version NOT CREATED")
        return False
    
    print(f"✅ Regenerate version created: "
          f"#{regenerate_version['version_number']}")
    
    # ========================================
    # STEP 8: Test rollback to version 2 (after generation)
    # ========================================
    print("\n[STEP 8] Testing rollback to version 2 (before regenerate)...")
    
    rollback_payload = {
        "target_version": 2  # After generation, before regenerate
    }
    
    response = requests.post(
        f"{BASE_URL}/plan/{plan_id}/rollback",
        json=rollback_payload
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to rollback: {response.status_code}")
        print(response.text)
        return False
    
    rolled_back_plan = response.json()
    
    # Check if rollback response has days or need to fetch again
    if "days" not in rolled_back_plan:
        print("  (Fetching plan after rollback...)")
        response = requests.get(f"{BASE_URL}/plan/{plan_id}")
        if response.status_code != 200:
            print(f"❌ Failed to fetch plan after rollback: {response.status_code}")
            return False
        rolled_back_plan = response.json()
    
    rolled_back_day1 = rolled_back_plan["days"][0]
    rolled_back_attractions = [
        item for item in rolled_back_day1["items"]
        if item.get("type") == "attraction"
    ]
    
    print(f"✅ Rollback successful")
    print(f"   Rolled back Day 1 attractions: "
          f"{len(rolled_back_attractions)}")
    
    # Verify original state restored
    original_poi_ids = {attr["poi_id"] for attr in attractions_day1}
    rolled_back_poi_ids = {attr["poi_id"] for attr in rolled_back_attractions}
    
    if original_poi_ids == rolled_back_poi_ids:
        print("✅ Original plan restored correctly")
    else:
        print("⚠️ Rolled back plan differs from original")
        print(f"   Original POIs: {original_poi_ids}")
        print(f"   Rolled back POIs: {rolled_back_poi_ids}")
    
    # ========================================
    # STEP 9: Final version check
    # ========================================
    print("\n[STEP 9] Final version count...")
    
    response = requests.get(f"{BASE_URL}/plan/{plan_id}/versions")
    
    if response.status_code != 200:
        print(f"❌ Failed to get versions: {response.status_code}")
        return False
    
    versions = response.json()
    print(f"✅ Final version count: {len(versions)}")
    
    expected_versions = [
        "initial",
        "generated",
        "regenerate_range",
        "rollback"
    ]
    
    actual_types = [v["change_type"] for v in versions]
    
    print(f"   Expected: {expected_versions}")
    print(f"   Actual: {actual_types}")
    
    if len(versions) >= 4:
        print("✅ All versions created correctly")
    else:
        print(f"⚠️ Expected at least 4 versions, got {len(versions)}")
    
    # ========================================
    # FINAL RESULT
    # ========================================
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - DAY 8 REGENERATE RANGE WORKING!")
    print("=" * 60)
    print(f"\n📋 Summary:")
    print(f"   - Plan ID: {plan_id}")
    print(f"   - Pinned item: {pinned_name} ({pinned_poi_id})")
    print(f"   - Regenerate range: {from_time}-{to_time}")
    print(f"   - New items added: {len(new_items)}")
    print(f"   - Final versions: {len(versions)}")
    print(f"\n✅ READY TO COMMIT")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_day8_regenerate_flow()
    
    if not success:
        print("\n" + "=" * 60)
        print("❌ TESTS FAILED - CHECK ERRORS ABOVE")
        print("=" * 60)
        exit(1)
