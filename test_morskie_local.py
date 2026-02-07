import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')
print(f'Loaded {len(pois)} POIs')

# Find Morskie Oko
morskie = [p for p in pois if 'Morskie' in p.get('name', '')]
if morskie:
    poi = morskie[0]
    print(f"\nMorskie Oko (poi_36):")
    print(f"  ID: {poi.get('id')}")
    print(f"  Must see score: {poi.get('must_see_score')}")
    print(f"  Tags: {poi.get('tags')}")
    print(f"  Visit duration: {poi.get('time_min')}-{poi.get('time_max')} min")
    print(f"  Opening hours seasonal: {len(str(poi.get('opening_hours_seasonal', '')))} chars")
else:
    print('Morskie Oko NOT FOUND!')

# Find Dolina Kościeliska for comparison
dolina = [p for p in pois if 'Kościeliska' in p.get('name', '')]
if dolina:
    poi = dolina[0]
    print(f"\nDolina Kościeliska (poi_34):")
    print(f"  ID: {poi.get('id')}")
    print(f"  Must see score: {poi.get('must_see_score')}")
    print(f"  Tags: {poi.get('tags')}")
    print(f"  Visit duration: {poi.get('time_min')}-{poi.get('time_max')} min")
