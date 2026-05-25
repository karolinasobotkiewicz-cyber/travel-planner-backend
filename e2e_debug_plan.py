import requests, json, uuid
GUEST_ID = str(uuid.uuid4())
HEADERS = {"X-Guest-ID": GUEST_ID, "Content-Type": "application/json"}
payload = {
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
    "trip_length": {"days": 1, "start_date": "2026-06-20"},
    "daily_time_window": {"start": "09:00", "end": "19:00"},
    "budget": {"level": 2},
    "transport_modes": ["car"],
    "preferences": ["nature_landscape", "hiking"],
    "travel_style": "adventure"
}
r = requests.post("http://127.0.0.1:8001/plan/preview", json=payload, headers=HEADERS, timeout=60)
print("STATUS:", r.status_code)
if r.status_code == 200:
    plan = r.json()
    days = plan.get("days", [])
    for day in days:
        items = day.get("items", [])
        for item in items:
            name = item.get("name","")[:50]
            t = item.get("type","")
            tags = str(item.get("tags",[]))[:60]
            print(f"  type={t} name={name} tags={tags}")
else:
    print(r.text[:500])
