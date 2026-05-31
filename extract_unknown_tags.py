"""
Wyciąga wszystkie unikalne tagi z multi_city_attractions.xlsx
które NIE są rozpoznawane przez tag_preferences.py
"""
import ast
import pandas as pd
import sys
sys.path.insert(0, '.')

from app.domain.scoring.tag_preferences import USER_PREFERENCES_TO_TAGS as TAG_PREFERENCES

# Zbierz wszystkie znane tagi z tag_preferences
known_tags = set()
for pref_data in TAG_PREFERENCES.values():
    for tag in pref_data.get("tags", []):
        known_tags.add(tag.lower().strip())

# Wczytaj Excel
df = pd.read_excel('data/multi_city_attractions.xlsx', sheet_name='All Cities')

# Wyciągnij wszystkie tagi
all_tags = {}  # tag -> lista POI gdzie występuje

for _, row in df.iterrows():
    raw = str(row.get('Tags', '') or '')
    name = str(row.get('Name', '') or '')
    city = str(row.get('City', '') or '')

    # Parse tags
    tags = []
    raw = raw.strip()
    if raw.startswith('['):
        try:
            tags = ast.literal_eval(raw)
        except:
            tags = [t.strip().strip("'\"") for t in raw.strip("[]").split(',')]
    elif raw and raw != 'nan':
        tags = [t.strip() for t in raw.split(',')]

    for tag in tags:
        tag = tag.lower().strip().strip("'\"")
        if tag and tag not in known_tags:
            if tag not in all_tags:
                all_tags[tag] = []
            all_tags[tag].append(f"{name} ({city})")

# Sortuj po liczbie wystąpień
sorted_tags = sorted(all_tags.items(), key=lambda x: -len(x[1]))

print(f"Znane tagi w tag_preferences: {len(known_tags)}")
print(f"Nieznane tagi w multi_city: {len(sorted_tags)}\n")
print("=" * 60)
print(f"{'TAG':<40} {'WYSTĄPIEŃ':>10}  PRZYKŁAD")
print("=" * 60)
for tag, pois in sorted_tags:
    example = pois[0] if pois else ''
    print(f"{tag:<40} {len(pois):>10}  {example[:50]}")
