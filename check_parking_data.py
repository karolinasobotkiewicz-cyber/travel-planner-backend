"""
Sprawdź parking data dla pierwszego POI (DINO PARK)
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')

dino = next((p for p in pois if 'DINO' in p['name'].upper()), None)

if not dino:
    print("❌ DINO PARK not found!")
    exit(1)

print(f"DINO PARK parking data:")
print(f"  parking_name: '{dino.get('parking_name')}'")
print(f"  parking_address: '{dino.get('parking_address')}'")
print(f"  parking_lat: {dino.get('parking_lat')}")
print(f"  parking_lng: {dino.get('parking_lng')}")
print(f"  parking_type: '{dino.get('parking_type')}'")
print(f"  parking_walk_time_min: {dino.get('parking_walk_time_min')}")
print()
print(f"POI own location:")
print(f"  address: '{dino.get('address')}'")
print(f"  lat: {dino.get('lat')}")
print(f"  lng: {dino.get('lng')}")
