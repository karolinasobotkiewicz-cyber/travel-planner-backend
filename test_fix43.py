import sys, os, json, io
from contextlib import redirect_stdout
sys.path.insert(0, '.')
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

poi_repo = POIRepository('data/zakopane.xlsx')
all_pois = poi_repo._pois # Accessing internal attribute
print(f"Total POIs in repo: {len(all_pois)}")

service = PlanService(poi_repo)

with open('../Testy_Klientki/test-08.json', 'r', encoding='utf-8') as f:
    r8 = json.load(f)
trip8 = TripInput(**r8)

# Check if preferences are correctly set
print(f"Preferences: {trip8.preferences}")

buf = io.StringIO()
with redirect_stdout(buf):
    result8 = service.generate_plan(trip8)

output = buf.getvalue()

for line in output.split('\n'):
    if any(keyword in line for keyword in ['Trail limit', 'Termy limit', 'BOOSTED', 'Final trail', 'Global trail count', 'Global termy count', 'Filtering', 'candidates']):
        print(line)

print("\n=== DISTRIBUTION ===")
assigned_names = set()
for i, day in enumerate(result8.days):
    items = [it for it in day.items if (it.type.value if hasattr(it.type,'value') else str(it.type)) == 'attraction']
    names = [getattr(it, 'name', None) or getattr(it, 'attraction_name', None) or '?' for it in items]
    for n in names: assigned_names.add(n)
    print(f"  Day {i+1}: {len(items)} | {[n[:25] for n in names]}")

print(f"\nTOTAL: {len(assigned_names)} unique attractions")

# Print what was NOT used
all_names = {poi.name for poi in all_pois if poi.category != 'Restauracja'}
print(f"Not used (subset): {list(all_names - assigned_names)[:20]}")
