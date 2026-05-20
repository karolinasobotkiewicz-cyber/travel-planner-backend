import sys, os, json
sys.path.insert(0, '.')
# Suppress all engine prints
import io
from contextlib import redirect_stdout

from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

poi_repo = POIRepository('data/zakopane.xlsx')
service = PlanService(poi_repo)

with open('../Testy_Klientki/test-06.json', 'r', encoding='utf-8') as f:
    r6 = json.load(f)
trip6 = TripInput(**r6)

f_buf = io.StringIO()
with redirect_stdout(f_buf):
    result6 = service.generate_plan(trip6)

# Inspect DayPlan structure dynamically
for idx, day in enumerate(result6.days):
    day_num = getattr(day, 'day_number', idx + 1)
    print(f"\n=== Day {day_num} ===")
    for item in day.items:
        itype = item.type.value if hasattr(item.type, 'value') else str(item.type)
        name = getattr(item, 'name', None) or getattr(item, 'attraction_name', None) or getattr(item, 'restaurant_name', None) or ''
        start = getattr(item, 'start_time', '?')
        end = getattr(item, 'end_time', '?')
        dur = getattr(item, 'duration_min', '?')
        from_loc = getattr(item, 'from_location', None) or getattr(item, 'from_name', None) or ''
        to_loc = getattr(item, 'to_location', None) or getattr(item, 'to_name', None) or ''
        extra = f" [{from_loc} -> {to_loc}]" if from_loc or to_loc else f" {name}"
        print(f"  {start}-{end} ({dur}m) [{itype}]{extra}")
