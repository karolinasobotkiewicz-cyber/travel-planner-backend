import pandas as pd
from app.infrastructure.repositories.normalizer import normalize_poi

# Load raw Excel
df = pd.read_excel('data/zakopane.xlsx')

# Get poi_9
row_9 = df.iloc[9]
print("=== RAW EXCEL poi_9 ===")
print(f"Name: {row_9['Name']}")
print(f"Target group: {row_9['Target group']}")
print(f"Type: {type(row_9['Target group'])}")
print(f"Repr: {repr(row_9['Target group'])}")

# Normalize
print("\n=== NORMALIZED poi_9 ===")
normalized = normalize_poi(row_9, 9)
print(f"id: {normalized.get('id')}")
print(f"name: {normalized.get('name')}")
print(f"target_groups: {normalized.get('target_groups')}")
print(f"Type: {type(normalized.get('target_groups'))}")
print(f"kids_only: {normalized.get('kids_only')}")

# Test filter logic
print("\n=== FILTER LOGIC TEST ===")
user = {"target_group": "friends"}
poi = normalized

user_group = str(user.get("target_group", "")).strip().lower()
print(f"user_group: '{user_group}'")

target_groups = poi.get("target_groups")
print(f"target_groups raw: {target_groups}")
print(f"target_groups is None: {target_groups is None}")
print(f"target_groups is empty: {not target_groups}")

if target_groups:
    tg = set([str(x).strip().lower() if x is not None else "" for x in target_groups])
    print(f"tg set: {tg}")
    print(f"user_group in tg: {user_group in tg}")
    print(f"SHOULD EXCLUDE: {user_group not in tg}")
else:
    print("target_groups is empty/None → ALLOW (no filtering)")
