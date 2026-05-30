import requests, json, uuid, sys

headers = {'X-Guest-ID': str(uuid.uuid4()), 'Content-Type': 'application/json'}

tests = [
    ("family_kids", {
        'location': {'city': 'Zakopane', 'country': 'Poland', 'region_type': 'mountain'},
        'group': {'type': 'family_kids', 'size': 4, 'crowd_tolerance': 2},
        'trip_length': {'days': 2, 'start_date': '2026-06-07'},
        'daily_time_window': {'start': '09:00', 'end': '19:00'},
        'budget': {'level': 2},
        'transport_modes': ['car'],
        'preferences': ['attractions_for_kids', 'nature_landscape'],
        'travel_style': 'relaxed'
    }),
    ("relax_wellness", {
        'location': {'city': 'Zakopane', 'country': 'Poland', 'region_type': 'mountain'},
        'group': {'type': 'couples', 'size': 2, 'crowd_tolerance': 2},
        'trip_length': {'days': 3, 'start_date': '2026-06-07'},
        'daily_time_window': {'start': '09:00', 'end': '19:00'},
        'budget': {'level': 3},
        'transport_modes': ['car'],
        'preferences': ['relax_wellness', 'relaxation'],
        'travel_style': 'relaxed'
    }),
    ("local_food", {
        'location': {'city': 'Zakopane', 'country': 'Poland', 'region_type': 'mountain'},
        'group': {'type': 'couples', 'size': 2, 'crowd_tolerance': 2},
        'trip_length': {'days': 2, 'start_date': '2026-06-07'},
        'daily_time_window': {'start': '09:00', 'end': '19:00'},
        'budget': {'level': 2},
        'transport_modes': ['car'],
        'preferences': ['local_food_experience', 'nature_landscape'],
        'travel_style': 'relaxed'
    }),
    ("seniors", {
        'location': {'city': 'Zakopane', 'country': 'Poland', 'region_type': 'mountain'},
        'group': {'type': 'seniors', 'size': 2, 'crowd_tolerance': 2},
        'trip_length': {'days': 2, 'start_date': '2026-06-07'},
        'daily_time_window': {'start': '09:00', 'end': '19:00'},
        'budget': {'level': 2},
        'transport_modes': ['car'],
        'preferences': ['nature_landscape', 'relaxation', 'museums_heritage'],
        'travel_style': 'relaxed'
    }),
]

for name, body in tests:
    print(f"\n=== Testing: {name} ===")
    try:
        r = requests.post('http://127.0.0.1:8001/plan/preview', json=body, headers=headers, timeout=120)
        print(f"HTTP {r.status_code}")
        if r.status_code == 200:
            plan = r.json()
            days = plan.get('days', [])
            print(f"Days: {len(days)}")
            for d in days:
                attrs = [i for i in d.get('items', []) if i.get('type') == 'attraction']
                print(f"  Day {d.get('day')}: {len(d.get('items',[]))} items, {len(attrs)} attractions")
                for a in attrs:
                    print(f"    - {a.get('name')}")
        else:
            print(r.text[:600])
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {e}")

print("\nDone.")
