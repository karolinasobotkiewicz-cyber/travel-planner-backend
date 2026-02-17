import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')

missing_gps = [p for p in pois if not p.get('lat') or not p.get('lng')]

print(f"POI missing GPS coordinates: {len(missing_gps)}/{len(pois)}")
print()

if missing_gps:
    print("POIs without GPS:")
    for p in missing_gps[:15]:
        print(f"  {p.get('id')}: {p.get('name', 'N/A')}")
else:
    print("✓ All POIs have GPS coordinates")
