import sys, os
sys.path.insert(0, '.')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS

pois = load_multi_city_poi('data/multi_city_attractions.xlsx', ['Gdańsk', 'Gdynia', 'Sopot'])
print(f'Loaded {len(pois)} POIs for Trojmiasto')

all_tags = set()
for poi in pois:
    for tag in poi.get('tags', []):
        all_tags.add(tag)

all_known = set()
for pref_data in USER_PREFERENCES_TO_TAGS.values():
    all_known.update(pref_data.get('tags', []))
    all_known.update(pref_data.get('type_match', []))
unknown = sorted(all_tags - all_known)
known = sorted(all_tags & all_known)
print(f'Total unique tags: {len(all_tags)}')
print(f'Known tags: {len(known)}')
print(f'UNKNOWN tags ({len(unknown)}):')
for t in unknown:
    print(f'  {t}')
