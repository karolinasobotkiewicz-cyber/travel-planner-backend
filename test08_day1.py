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

f_buf = io.StringIO()
with redirect_stdout(f_buf):
    result8 = service.generate_plan(trip8)

# Show Day 1 in full detail
day = result8.days[0]
print(f"=== TEST-08 Day 1 ===")
for item in day.items:
    itype = item.type.value if hasattr(item.type, 'value') else str(item.type)
    name = getattr(item, 'name', None) or getattr(item, 'attraction_name', None) or ''
    start = getattr(item, 'start_time', '?')
    end = getattr(item, 'end_time', '?')
    dur = getattr(item, 'duration_min', '?')
    is_tech = getattr(item, 'is_technical_buffer', None)
    from_loc = getattr(item, 'from_location', None) or getattr(item, 'from_name', None) or ''
    to_loc = getattr(item, 'to_location', None) or getattr(item, 'to_name', None) or ''
    extra = f"[{from_loc} → {to_loc}]" if from_loc or to_loc else name
    tech_str = f" (tech={is_tech})" if is_tech is not None else ""
    print(f"  {start}-{end} ({dur}m) [{itype}] {extra}{tech_str}")

# Also show last item of each day to check if trail ends at day_end
print()
print("=== Last items per day ===")
for i, day in enumerate(result8.days):
    real_items = [item for item in day.items if (item.type.value if hasattr(item.type,'value') else str(item.type)) not in ['day_start','day_end']]
    if real_items:
        last = real_items[-1]
        itype = last.type.value if hasattr(last.type, 'value') else str(last.type)
        end = getattr(last, 'end_time', '?')
        name = getattr(last, 'name', None) or getattr(last, 'attraction_name', None) or ''
        print(f"  Day {i+1}: last={itype} '{name}' ends {end}")
