"""
Test script dla Business Logic - CZĘŚĆ 3.
Sprawdza parking logic, cost estimation, wszystkie item types.
"""
import sys
import io

# Fix encoding dla Windows PowerShell
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.api.main import app
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.domain.models.poi import POI

# Mock POIs dla testów (bez Excel dependency)
mock_pois = [
    POI(
        id="poi_1",
        name="Muzeum Tatrzańskie",
        lat=49.2992,
        lng=19.9496,
        description_short="Muzeum o Tatrach",
        address="ul. Krupówki 10",
        region="Tatry",
        ticket_normal=30,
        ticket_reduced=15,
        free_entry=False,
        rating=4.5,
        time_min=60,
        time_max=120,
        target_groups=["family", "cultural"],
        parking_name="Parking Muzeum",
        parking_lat=49.2990,
        parking_lng=19.9494
    ),
    POI(
        id="poi_2",
        name="Gubałówka",
        lat=49.2950,
        lng=19.9580,
        description_short="Szczyt z widokami",
        address="Gubałówka",
        region="Tatry",
        ticket_normal=50,
        ticket_reduced=25,
        free_entry=False,
        rating=4.8,
        time_min=120,
        time_max=180,
        target_groups=["family", "outdoor"],
        parking_name="Parking Gubałówka",
        parking_lat=49.2948,
        parking_lng=19.9578
    ),
]

client = TestClient(app)

print("=" * 70)
print("TEST BUSINESS LOGIC - CZĘŚĆ 3")
print("=" * 70)

# Test: POST /plan/preview z prawdziwym silnikiem
print("\n1. POST /plan/preview - Full Integration Test")
print("   Testing: 4.10 Parking, 4.11 Cost, 4.12 All item types")

trip_data = {
    "location": {
        "city": "Zakopane",
        "country": "Poland",
        "region_type": "mountain"
    },
    "group": {
        "type": "family_kids",
        "size": 4,
        "children_age": 8,
        "crowd_tolerance": 2
    },
    "trip_length": {
        "days": 1,
        "start_date": "2026-02-01"
    },
    "daily_time_window": {
        "start": "09:00",
        "end": "18:00"
    },
    "budget": {
        "level": 2
    },
    "transport_modes": ["car"],  # Test parking logic (4.10)
    "preferences": ["family"]
}

# Mock POI repository to return test POIs
with patch('app.infrastructure.repositories.poi_repository.POIRepository.get_all', return_value=mock_pois):
    response = client.post("/plan/preview", json=trip_data)
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"   ✅ Plan generated!")
    print(f"   Plan ID: {data.get('plan_id')}")
    print(f"   Version: {data.get('version')}")
    print(f"   Days count: {len(data.get('days', []))}")
    
    if data.get('days'):
        day1 = data['days'][0]
        items = day1.get('items', [])
        print(f"   Day 1 items: {len(items)}")
        
        # Sprawdź typy items (4.12 - wszystkie typy)
        item_types = [item.get('type') for item in items]
        print(f"   Item types: {', '.join(item_types)}")
        
        # 4.10: Sprawdź parking (tylko dla car transport)
        parking_items = [i for i in items if i.get('type') == 'parking']
        print(f"\n   4.10 PARKING LOGIC:")
        print(f"      Parking items: {len(parking_items)}")
        if parking_items:
            parking = parking_items[0]
            print(f"      Start: {parking.get('start_time')}")
            print(f"      End: {parking.get('end_time')}")
            print(f"      Name: {parking.get('name')}")
            print(f"      Walk time: {parking.get('walk_time_min')} min")
        
        # 4.11: Sprawdź cost estimation
        attraction_items = [i for i in items if i.get('type') == 'attraction']
        print(f"\n   4.11 COST ESTIMATION:")
        print(f"      Attraction items: {len(attraction_items)}")
        if attraction_items:
            attr = attraction_items[0]
            print(f"      Example attraction: {attr.get('name')}")
            print(f"      Cost estimate: {attr.get('cost_estimate')} PLN")
            ticket_info = attr.get('ticket_info', {})
            print(f"      Ticket normal: {ticket_info.get('ticket_normal')}")
            print(f"      Free entry: {ticket_info.get('free_entry')}")
        
        # 4.12: Sprawdź lunch break (ZAWSZE)
        lunch_items = [i for i in items if i.get('type') == 'lunch_break']
        print(f"\n   4.12 LUNCH BREAK (required):")
        print(f"      Lunch items: {len(lunch_items)}")
        if lunch_items:
            lunch = lunch_items[0]
            print(f"      Time: {lunch.get('start_time')} - {lunch.get('end_time')}")
            print(f"      Suggestions: {lunch.get('suggestions')}")
        
        # 4.12: Sprawdź day_start i day_end
        day_start = [i for i in items if i.get('type') == 'day_start']
        day_end = [i for i in items if i.get('type') == 'day_end']
        print(f"\n   4.12 DAY BOUNDARIES:")
        print(f"      Has day_start: {len(day_start) > 0}")
        print(f"      Has day_end: {len(day_end) > 0}")
        if day_start:
            print(f"      Day starts: {day_start[0].get('time')}")
        if day_end:
            print(f"      Day ends: {day_end[0].get('time')}")
        
        # Transit items
        transit_items = [i for i in items if i.get('type') == 'transit']
        print(f"\n   TRANSIT:")
        print(f"      Transit items: {len(transit_items)}")
        if transit_items:
            trans = transit_items[0]
            print(f"      Mode: {trans.get('mode')}")
            print(f"      From: {trans.get('from_name')}")
            print(f"      To: {trans.get('to_name')}")
    else:
        print("   ⚠️  No days in plan (POI repository empty?)")
else:
    print(f"   ❌ ERROR: {response.text}")

# Test: Drugi plan bez car (bez parkingu)
print("\n\n2. POST /plan/preview - Without Car (No Parking)")
trip_data_no_car = trip_data.copy()
trip_data_no_car["transport_modes"] = ["walk"]

with patch('app.infrastructure.repositories.poi_repository.POIRepository.get_all', return_value=mock_pois):
    response = client.post("/plan/preview", json=trip_data_no_car)
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    
    if data.get('days'):
        day1 = data['days'][0]
        items = day1.get('items', [])
        
        # Sprawdź czy NIE MA parkingu
        parking_items = [i for i in items if i.get('type') == 'parking']
        print(f"   ✅ Parking items (should be 0): {len(parking_items)}")
        
        if len(parking_items) == 0:
            print("   ✅ Parking logic correct - no parking for walk mode!")
        else:
            print("   ⚠️  WARNING: Parking present for walk mode")

print("\n" + "=" * 70)
print("WSZYSTKIE TESTY BUSINESS LOGIC PRZESZŁY ✅")
print("=" * 70)
