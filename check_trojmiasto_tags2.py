import sys, os
sys.path.insert(0, '.')
os.environ['PYTHONIOENCODING'] = 'utf-8'

import pandas as pd

# Load excel directly - don't trigger validator
df = pd.read_excel('data/multi_city_attractions.xlsx')

# Filter to Trojmiasto cities
cities = ['Gdańsk', 'Gdynia', 'Sopot']
trojmiasto_df = df[df['City'].isin(cities)]
print(f'Trójmiasto POIs: {len(trojmiasto_df)}')
print(f'Cities: {trojmiasto_df["City"].value_counts().to_dict()}')

# Get all tags
from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS

all_known = set()
for pref_data in USER_PREFERENCES_TO_TAGS.values():
    all_known.update(pref_data.get('tags', []))
    all_known.update(pref_data.get('type_match', []))

all_tags = set()
for _, row in trojmiasto_df.iterrows():
    raw = row.get('Tags', '')
    if pd.notna(raw) and str(raw).strip():
        for tag in str(raw).split(','):
            t = tag.strip()
            if t:
                all_tags.add(t)

unknown = sorted(all_tags - all_known)
known = sorted(all_tags & all_known)
print(f'\nTotal unique tags: {len(all_tags)}')
print(f'Known: {len(known)}')
print(f'UNKNOWN ({len(unknown)}):')
for t in unknown:
    print(f'  {t}')
