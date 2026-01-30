"""Test live API with early start time - check if closed POI are scheduled"""
import requests
import json

API_URL = "https://travel-planner-backend-xbsp.onrender.com/plan/preview"

payload = {
    "location": {
        "city": "zakopane",
        "country": "Poland",
        "latitude": 49.299,
        "longitude": 19.95
    },
    "group": {
        "type": "solo",
        "size": 1,
        "crowd_tolerance": 1
    },
    "trip_length": {
        "start_date": "2026-02-15",  # Sunday
        "days": 1
    },
    "daily_time_window": {
        "start_time": "09:00",
        "end_time": "18:00"
    },
    "budget": {
        "total": 500,
        "currency": "PLN"
    },
    "preferences": [],
    "travel_style": "balanced"
}

print("Testing live API: POST /plan/preview")
print("Start time: 09:00")
print("Date: 2026-02-15 (Sunday)")
print()

try:
    response = requests.post(API_URL, json=payload, timeout=120)
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Response 200 OK")
        print()
        print("Attractions in plan:")
        
        for day in data.get("days", []):
            for item in day.get("items", []):
                if item["type"] == "attraction":
                    name = item["name"]
                    start = item["start_time"]
                    
                    marker = ""
                    if "Oscypka" in name:
                        marker = " ⚠️  (should NOT be scheduled - closed until 15:30!)"
                    elif "Myszog" in name and start < "10:00":
                        marker = " ⚠️  (should NOT be scheduled before 10:00!)"
                    
                    print(f"  {start}: {name}{marker}")
    else:
        print(f"❌ Response {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error: {e}")
