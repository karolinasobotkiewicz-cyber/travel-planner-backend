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

buf = io.StringIO()
with redirect_stdout(buf):
    result8 = service.generate_plan(trip8)

# Print Day 1 full item list
for i, day in enumerate(result8.days):
    print(f"\n=== Day {i+1} ===")
    for item in day.items:
        itype = item.type.value if hasattr(item.type, 'value') else str(item.type)
        if itype in ['day_start', 'day_end']:
            continue
        name = (getattr(item, 'name', None) or getattr(item, 'attraction_name', None) or 
                getattr(item, 'restaurant_name', None) or '')
        start = getattr(item, 'start_time', '?')
        end = getattr(item, 'end_time', '?')
        dur = getattr(item, 'duration_min', '?')
        from_loc = getattr(item, 'from_location', None) or getattr(item, 'from_name', None) or ''
        to_loc = getattr(item, 'to_location', None) or getattr(item, 'to_name', None) or ''
        if from_loc or to_loc:
            desc = f"[{from_loc} → {to_loc}]"
        else:
            desc = name
        print(f"  {start}-{end} ({dur}m) [{itype}] {desc}")
