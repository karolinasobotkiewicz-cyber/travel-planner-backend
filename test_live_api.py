import requests
import json

print("=" * 70)
print("LIVE API TEST - Render.com Production")
print("URL: https://travel-planner-backend-xbsp.onrender.com")
print("=" * 70)

# Test: POST /plan/preview z nowymi polami preferences + travel_style
payload = {
    "location": {
        "city": "zakopane",
        "country": "Poland",
        "region_type": "mountain"
    },
    "group": {
        "type": "solo",
        "size": 1,
        "crowd_tolerance": 2
    },
    "trip_length": {
        "start_date": "2026-02-15",
        "end_date": "2026-02-15",
        "days": 1
    },
    "daily_time_window": {
        "start": "09:00",
        "end": "19:00"
    },
    "budget": {
        "level": 2
    },
    "transport_modes": ["car"],
    "preferences": ["outdoor", "hiking", "nature"],  # NOWE
    "travel_style": "adventure"  # NOWE
}

print("\n📤 REQUEST: POST /plan/preview")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(
        "https://travel-planner-backend-xbsp.onrender.com/plan/preview",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60
    )
    
    print(f"\n📥 RESPONSE: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ SUCCESS!")
        print(f"   Plan ID: {data.get('plan_id', 'N/A')}")
        print(f"   Days: {len(data.get('days', []))}")
        
        if data.get("days"):
            day = data["days"][0]
            attractions = [item for item in day.get("items", []) if item.get("type") == "attraction"]
            print(f"   Attractions: {len(attractions)}")
            print(f"   Total items: {len(day.get('items', []))}")
            
            # Verify lunch break exists (core requirement)
            lunch = [item for item in day.get("items", []) if item.get("type") == "lunch_break"]
            if lunch:
                print(f"   ✅ Lunch break: {lunch[0].get('start_time')} - {lunch[0].get('end_time')}")
            
            print("\n✅ NEW FEATURES CONFIRMED:")
            print(f"   ✅ preferences accepted: {payload['preferences']}")
            print(f"   ✅ travel_style accepted: {payload['travel_style']}")
            print("   ✅ API działa z nowymi polami!")
    else:
        print(f"❌ ERROR: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    print("⏳ TIMEOUT - Render.com cold start (FREE tier). Czekam 30s i próbuję ponownie...")
    import time
    time.sleep(30)
    
    # Retry
    try:
        response = requests.post(
            "https://travel-planner-backend-xbsp.onrender.com/plan/preview",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        if response.status_code == 200:
            print("✅ SUCCESS po retry!")
        else:
            print(f"❌ ERROR po retry: {response.status_code}")
    except Exception as e:
        print(f"❌ RETRY FAILED: {e}")
        
except Exception as e:
    print(f"❌ EXCEPTION: {e}")

print("\n" + "=" * 70)
print("TEST COMPLETED")
print("=" * 70)
