import sys, os, json
sys.path.insert(0, '.')
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

# Set logging level to ERROR to suppress debug info
import logging
logging.getLogger().setLevel(logging.ERROR)

poi_repo = POIRepository('data/zakopane.xlsx')
service = PlanService(poi_repo)

with open('../Testy_Klientki/test-06.json', 'r', encoding='utf-8') as f:
    r6 = json.load(f)
trip6 = TripInput(**r6)
result6 = service.generate_plan(trip6)

print("="*80)
print("TEST-06 RESULTS")
print("="*80)
for day in result6.days:
    print(f"\n--- Day {day.day_number} ({day.date}) ---")
    for item in day.items:
        itype = item.type.value if hasattr(item.type, 'value') else item.type
        name = getattr(item, 'name', getattr(item, 'attraction_name', getattr(item, 'restaurant_name', itype)))
        # For transit, show origin and destination if available
        if itype == 'transit':
            origin = getattr(item, 'origin', '?')
            destination = getattr(item, 'destination', '?')
            name = f"Dojazd: {origin} -> {destination}"
        
        start = getattr(item, 'start_time', '?')
        end = getattr(item, 'end_time', '?')
        print(f"  {start}-{end} [{itype}] {name}")
