import sys, os, json
sys.path.insert(0, '.')
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

poi_repo = POIRepository('data/zakopane.xlsx')
service = PlanService(poi_repo)

with open('../Testy_Klientki/test-08.json', 'r', encoding='utf-8') as f:
    r8 = json.load(f)
trip8 = TripInput(**r8)

# Run WITHOUT redirect so we see all debug output
result8 = service.generate_plan(trip8)

print("\n\n=== FINAL DISTRIBUTION ===")
for i, day in enumerate(result8.days):
    items = [it for it in day.items if (it.type.value if hasattr(it.type,'value') else str(it.type)) == 'attraction']
    names = []
    for it in items:
        n = getattr(it, 'name', None) or getattr(it, 'attraction_name', None) or '?'
        names.append(n[:30])
    print(f"  Day {i+1}: {len(items)} attractions | {names}")
