"""Test script for FIX #77-#80 verification"""
import requests
import json

BASE_URL = "http://127.0.0.1:8001"
HEADERS = {"X-Guest-ID": "test-fix77-80", "Content-Type": "application/json"}

def test_plan(label, payload):
    print(f"\n{'='*70}")
    print(f"TEST: {label}")
    print('='*70)
    r = requests.post(f"{BASE_URL}/plan/preview", json=payload, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        print(f"ERROR {r.status_code}: {r.text[:300]}")
        return
    plan = r.json()
    for day in plan["days"]:
        print(f"\n--- Day {day.get('day', day.get('day_number', '?'))} ---")
        for item in day["items"]:
            t = item.get("type")
            st = item.get("start_time","?")
            et = item.get("end_time","?")
            dur = item.get("duration_min","?")
            if t == "transit":
                mode = item.get("mode","?")
                frm = item.get("from_location","?")
                to = item.get("to_location","?")
                print(f"  TRANSIT {st}-{et} {dur}min [{mode}]: {frm} -> {to}")
            elif t == "free_time":
                label_txt = item.get("label","?")
                sugg = item.get("suggestions", [])
                print(f"  FREE_TIME {st}-{et} {dur}min | '{label_txt}'")
                print(f"    suggestions: {sugg}")
            elif t == "dinner_break":
                print(f"  DINNER {st}-{et} {dur}min  ← CHECK: min 40 min?")
            elif t == "attraction":
                print(f"  ATTRACTION {st}-{et} {dur}min: {item.get('name','?')}")
            elif t in ("day_start", "day_end", "lunch_break", "parking"):
                print(f"  {t.upper()} {st}-{et}")

# TEST 1: Zakopane couples - check FIX #77 (close POIs walk transit) + FIX #78 (varied labels)
test_plan("Zakopane couples, evening window - FIX #77+#78", {
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
    "trip_length": {"days": 1, "start_date": "2026-06-20"},
    "daily_time_window": {"start": "09:00", "end": "21:00"},
    "budget": {"level": 2},
    "transport_modes": ["car"],
    "preferences": ["local_food_experience", "cultural"],
    "travel_style": "relax"
})

# TEST 2: Zakopane seniors - check FIX #76 regression (free_time <= 60 min) + FIX #78 labels
test_plan("Zakopane seniors - FIX #76 regression + FIX #78", {
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "group": {"type": "seniors", "size": 2, "crowd_tolerance": 1},
    "trip_length": {"days": 2, "start_date": "2026-06-20"},
    "daily_time_window": {"start": "09:00", "end": "18:00"},
    "budget": {"level": 1},
    "transport_modes": ["car"],
    "travel_style": "relax"
})

# TEST 3: Zakopane family_kids - FIX #79 crowd label check
test_plan("Zakopane family_kids - FIX #79 crowd label", {
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "group": {"type": "family_kids", "size": 4, "children_age": 8, "crowd_tolerance": 1},
    "trip_length": {"days": 1, "start_date": "2026-07-15"},
    "daily_time_window": {"start": "09:00", "end": "19:00"},
    "budget": {"level": 2},
    "transport_modes": ["car"],
    "travel_style": "balanced"
})

print("\n\nDONE!")
