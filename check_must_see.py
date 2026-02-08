import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi("data/zakopane.xlsx")

# Sort by must_see_score
pois_sorted = sorted(pois, key=lambda p: float(p.get('must_see_score', 0)), reverse=True)

print("\nTop 10 POI by must_see_score:\n")
for i, p in enumerate(pois_sorted[:10], 1):
    name = p.get('name', p.get('Name', 'Unknown'))  # Try both fields
    must_see = p.get('must_see_score', 0)
    priority = p.get('priority_level', None)
    print(f"{i}. {name}")
    print(f"   must_see={must_see}, priority_level={priority}")
