import sys
sys.path.append('.')
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

# Test _safe_str function
def _safe_str(x):
    return str(x).strip().lower() if x is not None else ""

pois = load_zakopane_poi('data/zakopane.xlsx')
poi9 = [p for p in pois if p.get('id') == 'poi_9'][0]

print(f"POI 9: {poi9.get('name')}")
print(f"target_groups TYPE: {type(poi9.get('target_groups'))}")
print(f"target_groups VALUE: {repr(poi9.get('target_groups'))}")

# Simulate filter logic
user_group = "friends"
target_groups = poi9.get("target_groups")

print(f"\n=== FILTER SIMULATION ===")
print(f"user_group: {user_group}")
print(f"target_groups: {target_groups}")

if not target_groups:
    print("→ ALLOW (no target_groups)")
else:
    print(f"→ Has target_groups, normalizing...")
    tg = set([_safe_str(x) for x in target_groups])
    print(f"   Normalized tg: {tg}")
    
    if user_group not in tg:
        print(f"   → EXCLUDE (user_group={user_group} NOT IN target_groups={tg})")
    else:
        print(f"   → ALLOW (user_group={user_group} IN target_groups={tg})")
