import sys, os, json
sys.path.insert(0, '.')
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

poi_repo = POIRepository('data/zakopane.xlsx')
service = PlanService(poi_repo)

print("="*80)
print("TEST-06")
print("="*80)
with open('../Testy_Klientki/test-06.json', 'r', encoding='utf-8') as f:
    r6 = json.load(f)
trip6 = TripInput(**r6)
result6 = service.generate_plan(trip6)
for day in result6.days:
    print(f"\n--- Day {day.day_number} ---")
    for item in day.items:
        itype = item.type.value if hasattr(item.type, 'value') else item.type
        name = getattr(item, 'name', getattr(item, 'attraction_name', getattr(item, 'restaurant_name', itype)))
        start = getattr(item, 'start_time', '?')
        end = getattr(item, 'end_time', '?')
        print(f"  {start}-{end} [{itype}] {name}")
