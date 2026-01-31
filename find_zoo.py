from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')
zoo_pois = [p for p in pois if 'zoo' in p.get('name', '').lower() or 'dino' in p.get('name', '').lower()]

print(f'\nFound {len(zoo_pois)} zoo/dino POI:\n')
for p in zoo_pois:
    print(f"  - {p['name']}")
    print(f"    Tags: {p.get('tags', [])}")
    print(f"    Opening hours: {p.get('opening_hours')}")
    print(f"    Must see: {p.get('must_see')}")
    print(f"    Time: {p.get('time_min')}-{p.get('time_max')} min\n")
