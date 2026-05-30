"""Verify tag fix coverage and check key detection."""
import re, pandas as pd

with open('app/domain/scoring/tag_preferences.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all top-level preference keys (4-space indented)
keys = re.findall(r'^\s{4}"([a-z_]+)"\s*:\s*\{', content, re.MULTILINE)
print(f'Preference keys found ({len(keys)}): {keys}')

# For each key, check if FIX #124 is in its tags section
for key in ['kids_attractions', 'nature_landscape']:
    # Find key as dict key (4-space indent)
    m = re.search(r'^\s{4}"' + key + r'"\s*:\s*\{', content, re.MULTILINE)
    if m:
        idx = m.start()
        ts = content.find('"tags": [', idx)
        bracket_start = content.find('[', ts)
        depth = 0
        for i in range(bracket_start, len(content)):
            if content[i] == '[': depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    bracket_end = i
                    break
        tags_content = content[bracket_start:bracket_end+1]
        has_fix = 'FIX #124' in tags_content
        print(f'{key}: FIX #124 in tags = {has_fix}')
    else:
        print(f'{key}: KEY NOT FOUND as top-level dict key!')

# Check actual tag coverage
df = pd.read_excel('data/multi_city_attractions.xlsx', sheet_name='All Cities')
all_tags = set()
for tags_raw in df['Tags'].dropna():
    s = str(tags_raw).strip().strip('[]').replace("'","").replace('"','')
    for t in re.split(r'[,\s]+', s):
        t = t.strip()
        if t: all_tags.add(t)

unknown = sorted(t for t in all_tags if t not in content)
print(f'\nUnknown tags after fix: {len(unknown)} (was 924)')
if unknown:
    print('Remaining unknown:')
    for t in unknown:
        print(f'  {t}')
