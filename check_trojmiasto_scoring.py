import sys, os
sys.path.insert(0, '.')
os.environ['PYTHONIOENCODING'] = 'utf-8'

import pandas as pd
from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS

df = pd.read_excel('data/multi_city_attractions.xlsx')
cities = ['Gdańsk', 'Gdynia', 'Sopot']
trojmiasto_df = df[df['City'].isin(cities)]

all_known = set()
for pref_data in USER_PREFERENCES_TO_TAGS.values():
    all_known.update(pref_data.get('tags', []))
    all_known.update(pref_data.get('type_match', []))

# POIs where ALL tags are unknown
zero_poi = []
for _, row in trojmiasto_df.iterrows():
    raw = row.get('Tags', '')
    tags = []
    if pd.notna(raw) and str(raw).strip():
        tags = [t.strip() for t in str(raw).split(',') if t.strip()]
    if tags and all(t not in all_known for t in tags):
        zero_poi.append({'name': row.get('Name', '?'), 'tags': tags})

print(f'POIs where ALL tags are unknown: {len(zero_poi)}')
for p in zero_poi:
    print(f'  {p["name"]}: {p["tags"]}')

# Also check POIs with NO tags at all
no_tags = trojmiasto_df[trojmiasto_df['Tags'].isna() | (trojmiasto_df['Tags'].astype(str).str.strip() == '')]
print(f'\nPOIs with NO tags: {len(no_tags)}')
print('Total Trójmiasto POIs:', len(trojmiasto_df))

# Check how calculate_tag_preference_score would score
# with preferences ['museums_heritage', 'nature_landscapes']
prefs = ['museums_heritage', 'nature_landscapes']
print('\nPOI scoring summary (museums_heritage + nature_landscapes):')
scored_pois = []
for _, row in trojmiasto_df.iterrows():
    raw = row.get('Tags', '')
    tags = set()
    if pd.notna(raw) and str(raw).strip():
        tags = {t.strip() for t in str(raw).split(',') if t.strip()}
    
    score = 0
    for pref in prefs:
        pref_data = USER_PREFERENCES_TO_TAGS.get(pref, {})
        for tag in tags:
            if tag in pref_data.get('tags', []):
                score += 15
        if row.get('Type of attraction', '') in pref_data.get('type_match', []):
            score += pref_data.get('type_bonus', 20)
    
    scored_pois.append((score, row.get('Name', '?'), tags))

scored_pois.sort(reverse=True)
print('Top 10 by pref score:')
for s, n, t in scored_pois[:10]:
    print(f'  score={s} | {n}')
print('\nZero score POIs:')
zero_scored = [(s, n, t) for s, n, t in scored_pois if s == 0]
print(f'  {len(zero_scored)} POIs have score=0 for these preferences')
