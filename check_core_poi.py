import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi("data/zakopane.xlsx")

core = [p for p in pois if str(p.get('priority_level','')).strip().lower()=='core']

print(f"\nCore POI count: {len(core)}\n")
for p in core:    print(f"  {p.get('Name')} - priority_level='{p.get('priority_level')}'")
