import sys; sys.path.insert(0, '.')
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
pois = load_zakopane_poi('data/zakopane.xlsx')

# Show tags from POIs whose name or type suggests trail/active
import re
trail_keywords = ['szlak', 'trail', 'trasa', 'szczyt', 'tatry', 'turnia', 'giewont', 'kasprowy', 'krupowki']
print('=== POIs with trail-like names ===')
for p in pois:
    name = p.get('name', '').lower()
    ptype = str(p.get('type', '')).lower()
    if any(kw in name for kw in trail_keywords) or 'trail' in ptype or 'hiking' in ptype:
        print(f"  {p.get('name','?')[:40]:40s}  type={p.get('type','?'):20s}  tags={p.get('tags',[])[:5]}")

print()
print('=== All unique tags ===')
all_tags = set()
for p in pois:
    all_tags.update(p.get('tags', []))
for t in sorted(all_tags):
    print(f'  {t}')

