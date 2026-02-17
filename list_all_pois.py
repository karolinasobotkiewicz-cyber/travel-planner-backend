import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')

print(f"Total POIs: {len(pois)}\n")
print("All POI names:")
print("="*80)

for p in pois:
    poi_id = p.get('id', 'N/A')
    name = p.get('name', 'N/A')
    print(f"{poi_id:10s} - {name}")
