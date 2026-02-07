import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

# Load POI
pois = load_zakopane_poi('data/zakopane.xlsx')

# Find Morskie Oko
morskie = [p for p in pois if 'Morskie' in p.get('name', '')]
if morskie:
    poi = morskie[0]
    print(f"\nMorskie Oko (poi_36):")
    print(f"  Tags type: {type(poi.get('tags'))}")
    print(f"  Tags value: {poi.get('tags')}")
    print(f"  Tags repr: {repr(poi.get('tags'))}")
    print(f"  'must_see' in tags: {'must_see' in poi.get('tags', [])}")
    print(f"  'nature_landscapes' in tags: {'nature_landscapes' in poi.get('tags', [])}")

# Find Dolina Kościeliska
dolina = [p for p in pois if 'Kościeliska' in p.get('name', '')]
if dolina:
    poi = dolina[0]
    print(f"\nDolina Kościeliska (poi_34):")
    print(f"  Tags type: {type(poi.get('tags'))}")
    print(f"  Tags value: {poi.get('tags')}")
    print(f"  Tags repr: {repr(poi.get('tags'))}")
    print(f"  'must_see' in tags: {'must_see' in poi.get('tags', [])}")
    print(f"  'nature_landscapes' in tags: {'nature_landscapes' in poi.get('tags', [])}")
