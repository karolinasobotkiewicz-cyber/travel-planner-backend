"""Debug gap filling - check if function is called and what it does"""
import sys
sys.path.insert(0, ".")

from app.domain.planner.engine import build_day
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from datetime import date

# Same request as production
request = {
    "destination": "Zakopane",
    "start_date": "2026-02-15",
    "end_date": "2026-02-15",
    "preferences": {
        "travel_style": "relaxed",
        "interests": ["nature", "family"],
        "budget_level": "medium"
    }
}

# Load POI
pois = load_zakopane_poi("data/zakopane.xlsx")
print(f"✓ Loaded {len(pois)} POI")

# Build plan
start_date = date.fromisoformat(request["start_date"])
plan = build_day(
    pois=pois,
    user={
        **request["preferences"],
        "target_group": "family_kids",
        "has_car": True
    },
    context={
        "date": start_date,
        "season": "winter",
        "weather": {"temp": 5, "condition": "cloudy"}
    },
    day_start="10:00",
    day_end="18:00"
)

print(f"\n✓ Generated plan with {len(plan)} items\n")

# Check for gaps
print("=" * 80)
print("TIMELINE CHECK:")
print("=" * 80)

from app.domain.planner.time_utils import time_to_minutes

last_end = None
for i, item in enumerate(plan):
    type_name = item['type']
    
    # Get times
    start_time = None
    end_time = None
    
    if type_name == "accommodation_start":
        start_time = item['time']
        end_time = item['time']
    elif type_name == "attraction":
        start_time = item['start_time']
        end_time = item['end_time']
        name = item['name']
    elif type_name == "transfer":
        # No times in raw transfer!
        duration = item['duration_min']
        print(f"{i}. TRANSFER: {item['from']} → {item['to']} ({duration} min)")
        print(f"   Raw transfer: {item}")
        if last_end:
            calc_end = last_end + duration
            print(f"   Calculated end: {calc_end} min from day start")
            last_end = calc_end
        continue
    elif type_name == "lunch_break":
        start_time = item['start_time']
        end_time = item['end_time']
    elif type_name == "free_time":
        start_time = item['start_time']
        end_time = item['end_time']
        print(f"{i}. FREE_TIME: {start_time} - {end_time} ✓ GAP FILLED!")
        last_end = time_to_minutes(end_time)
        continue
    elif type_name == "accommodation_end":
        start_time = item['time']
        print(f"{i}. DAY_END: {start_time}")
        break
    
    if start_time and end_time:
        start_min = time_to_minutes(start_time)
        end_min = time_to_minutes(end_time)
        
        # Check gap from last item
        if last_end is not None:
            gap = start_min - last_end
            if gap > 0:
                status = "❌ GAP!" if gap > 20 else "✓"
                print(f"{i}. {type_name.upper()}: {start_time} - {end_time}")
                if type_name == "attraction":
                    print(f"   {name}")
                print(f"   Gap from previous: {gap} min {status}")
            else:
                print(f"{i}. {type_name.upper()}: {start_time} - {end_time}")
                if type_name == "attraction":
                    print(f"   {name}")
        else:
            print(f"{i}. {type_name.upper()}: {start_time} - {end_time}")
            if type_name == "attraction":
                print(f"   {name}")
        
        last_end = end_min

print("\n" + "=" * 80)
print("SOFT POI AVAILABLE:")
print("=" * 80)

soft_pois = [p for p in pois if p.get("must_see_score", 3) <= 2 and 10 <= p.get("time_min", 60) <= 30]
print(f"Found {len(soft_pois)} soft POI candidates:\n")
for p in soft_pois[:10]:
    print(f"  • {p['name']}: {p.get('time_min', 60)} min, must_see={p.get('must_see_score', 3)}")
