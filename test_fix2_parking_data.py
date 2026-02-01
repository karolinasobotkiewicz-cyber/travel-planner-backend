"""
Test parking data mapping (FIX #2)
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.application.services.plan_service import PlanService
from app.infrastructure.repositories import POIRepository

# Load POIs
all_pois = load_zakopane_poi('data/zakopane.xlsx')
dino = next((p for p in all_pois if 'DINO' in p['name'].upper()), None)

if not dino:
    print("❌ DINO PARK not found!")
    exit(1)

print(f"DINO PARK POI data:")
print(f"  parking_address: '{dino.get('parking_address')}'")
print(f"  parking_lat: {dino.get('parking_lat')}")
print(f"  parking_lng: {dino.get('parking_lng')}")
print()

# Create engine attraction item (simulating engine.build_day output)
engine_attraction = {
    "type": "attraction",
    "poi": dino,  # Full POI dict
    "name": dino.get("name"),
    "start_time": "09:17"  # After parking (09:00-09:15) + walk (2 min)
}

# Test _generate_parking_item with POI dict (not engine attraction item)
plan_service = PlanService(None)
parking_item = plan_service._generate_parking_item(
    dino,  # Pass POI dict directly
    "09:00",
    "09:17"
)

print(f"Generated parking item:")
print(f"  name: {parking_item.name}")
print(f"  address: '{parking_item.address}'")
print(f"  lat: {parking_item.lat}")
print(f"  lng: {parking_item.lng}")
print(f"  walk_time_min: {parking_item.walk_time_min}")
print()

# Verify fix
if parking_item.address and parking_item.lat != 0.0 and parking_item.lng != 0.0:
    print("✅ FIX #2 SUCCESS - Parking has complete location data!")
else:
    print(f"❌ FIX #2 FAILED - Parking missing data")
    print(f"  address empty: {not parking_item.address}")
    print(f"  lat zero: {parking_item.lat == 0.0}")
    print(f"  lng zero: {parking_item.lng == 0.0}")
