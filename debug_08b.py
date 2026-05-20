import sys, os, json, io
from contextlib import redirect_stdout
sys.path.insert(0, '.')
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

poi_repo = POIRepository('data/zakopane.xlsx')
service = PlanService(poi_repo)

with open('../Testy_Klientki/test-08.json', 'r', encoding='utf-8') as f:
    r8 = json.load(f)
trip8 = TripInput(**r8)

# Capture output
buf = io.StringIO()
with redirect_stdout(buf):
    result8 = service.generate_plan(trip8)

output = buf.getvalue()

# Filter only relevant lines
lines = output.split('\n')
relevant = []
for line in lines:
    # Show lines about days 4-7 scope
    if any(marker in line for marker in ['Building Day 4', 'Building Day 5', 'Building Day 6', 'Building Day 7',
                                          'Day 4:', 'Day 5:', 'Day 6:', 'Day 7:',
                                          'global_used', 'already used', 'global trail',
                                          '[LIMITS]', '[BUILD_DAY]', 'skip', 'Skip']):
        relevant.append(line)

print('\n'.join(relevant[:200]))

# Also show what POIs were used in days 1-3
print("\n=== ATTRACTIONS PER DAY ===")
for i, day in enumerate(result8.days):
    items = [it for it in day.items if (it.type.value if hasattr(it.type,'value') else str(it.type)) == 'attraction']
    for it in items:
        n = getattr(it, 'name', None) or getattr(it, 'attraction_name', None) or '?'
        poi_id_val = getattr(it, 'poi_id', None) or getattr(it, 'id', None) or '?'
        print(f"  Day {i+1}: '{n}' (id={poi_id_val})")
