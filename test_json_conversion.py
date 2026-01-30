"""
Test opening hours JSON conversion
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi("data/zakopane.xlsx")

print(f"Załadowano {len(pois)} POIs\n")

# Check first 3 POIs
for i, poi in enumerate(pois[:3]):
    print(f"POI {i+1}: {poi.get('name')}")
    print(f"  opening_hours: {poi.get('opening_hours')}")
    print(f"  opening_hours_seasonal: {poi.get('opening_hours_seasonal')}")
    print(f"  Type opening_hours: {type(poi.get('opening_hours'))}")
    print()

# Find Muzeum Oscypka (should have Saturday only hours)
for poi in pois:
    if "Oscypka" in poi.get('name', ''):
        print(f"\nMuzeum Oscypka:")
        print(f"  opening_hours: {poi.get('opening_hours')}")
        print(f"  Type: {type(poi.get('opening_hours'))}")
        break

# Find seasonal POI
for poi in pois:
    seasonal = poi.get('opening_hours_seasonal')
    if seasonal:
        print(f"\nPOI with seasonal hours: {poi.get('name')}")
        print(f"  opening_hours_seasonal: {seasonal}")
        print(f"  Type: {type(seasonal)}")
        break
