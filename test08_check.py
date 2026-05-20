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

result8 = service.generate_plan(trip8)

attraction_counts = []
# DayPlan is a Pydantic model, check field names
for i, day in enumerate(result8.days):
    attractions = [item for item in day.items if hasattr(item, 'type') and (item.type.value if hasattr(item.type, 'value') else str(item.type)) == 'attraction']
    attraction_counts.append(len(attractions))
    print(f"\n=== Day {i+1} ({len(attractions)} attractions) ===")
    for item in day.items:
        itype = item.type.value if hasattr(item.type, 'value') else str(item.type)
        name = getattr(item, 'name', None) or getattr(item, 'attraction_name', None) or ''
        start = getattr(item, 'start_time', '?')
        end = getattr(item, 'end_time', '?')
        dur = getattr(item, 'duration_min', '?')
        from_loc = getattr(item, 'from_location', None) or getattr(item, 'from_name', None) or ''
        to_loc = getattr(item, 'to_location', None) or getattr(item, 'to_name', None) or ''
        extra = f" [{from_loc} -> {to_loc}]" if from_loc or to_loc else f" {name}"
        print(f"  {start}-{end} ({dur}m) [{itype}]{extra}")

print(f"\nAttraction counts per day: {attraction_counts}")
print(f"Total attractions: {sum(attraction_counts)}")
