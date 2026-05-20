import sys, os
sys.path.insert(0, '.')
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
pois = load_zakopane_poi('data/zakopane.xlsx', city_filter='Zakopane')
print(f'Total POIs loaded: {len(pois)}')
ids = [p['id'] for p in pois]
print('Missing:', [f'poi_{i}' for i in range(1,32) if f'poi_{i}' not in ids])
for p in pois:
    city = p.get('City','')
    if city not in ['Zakopane', '']:
        print(f"  {p['id']}: {p['name']} -> city={city}")
pois_krakow = load_zakopane_poi('data/zakopane.xlsx', city_filter='Krakow')
print(f'Krakow POIs from zakopane.xlsx: {len(pois_krakow)} (should be 0)')
