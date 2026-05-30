import sys, os
sys.path.insert(0, '.')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from app.infrastructure.repositories.load_multi_city import load_multi_city_poi

pois = load_multi_city_poi('data/multi_city_attractions.xlsx', ['Gdańsk', 'Gdynia', 'Sopot'])
print(f'Loaded {len(pois)} Trojmiasto POIs')
if pois:
    print('\nFirst POI sample:')
    p = pois[0]
    for k, v in sorted(p.items()):
        print(f'  {k}: {repr(v)}')
    
    print('\nPOIs with score_total > 0 (top 5):')
    for poi in pois[:5]:
        print(f'  name={poi.get("name")} type={poi.get("type")} tags={poi.get("tags", [])[:5]}')
        print(f'    priority={poi.get("priority_level")} must_see={poi.get("must_see")} pop={poi.get("popularity_score")}')
