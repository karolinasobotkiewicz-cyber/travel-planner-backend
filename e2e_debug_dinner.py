import requests, json, uuid
GUEST_ID = str(uuid.uuid4())
HEADERS = {"X-Guest-ID": GUEST_ID, "Content-Type": "application/json"}

# Test FIX #65 with evening window (includes dinner)
payload = {
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
    "trip_length": {"days": 1, "start_date": "2026-06-20"},
    "daily_time_window": {"start": "09:00", "end": "21:30"},
    "budget": {"level": 3},
    "transport_modes": ["car"],
    "preferences": ["local_food_experience", "cultural"],
    "travel_style": "relax"
}
r = requests.post("http://127.0.0.1:8001/plan/preview", json=payload, headers=HEADERS, timeout=60)
print("STATUS:", r.status_code)
if r.status_code == 200:
    plan = r.json()
    days = plan.get("days", [])
    print("\n=== ALL ITEMS ===")
    for day in days:
        items = day.get("items", [])
        for item in items:
            name = item.get("name","")[:60]
            t = item.get("type","")
            meal = item.get("meal_type","")
            start = item.get("start_time","")
            end = item.get("end_time","")
            print(f"  [{start}-{end}] type={t} name={name} meal_type={meal}")
else:
    print(r.text[:500])

# Check POI endpoint response structure
print("\n=== POI poi_75 RESPONSE ===")
r2 = requests.get("http://127.0.0.1:8001/poi/poi_75", timeout=10, headers=HEADERS)
print("STATUS:", r2.status_code)
if r2.status_code == 200:
    poi = r2.json()
    print("KEYS:", list(poi.keys()))
    print("name:", poi.get("name","N/A"))
    print("id:", poi.get("id","N/A"))
    print("tags:", poi.get("tags","N/A"))
