import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi("data/zakopane.xlsx")

priority_values = {}
for p in pois:
    val = p.get('priority_level', None)
    if val not in priority_values:
        priority_values[val] = []
    priority_values[val].append(p.get('Name'))

print("\nPriority_level values in data:\n")
for key, poi_list in priority_values.items():
    print(f"'{key}': {len(poi_list)} POI")
    for name in poi_list[:3]:  # Show first 3
        print(f"  - {name}")
    if len(poi_list) > 3:
        print(f"  ... and {len(poi_list)-3} more")
