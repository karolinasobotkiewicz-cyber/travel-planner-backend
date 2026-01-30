"""
Debug gap filling logic locally
"""
from app.domain.planner.engine import build_day
from app.infrastructure.repositories.poi_repository import POIRepository
from datetime import date

# Setup
repo = POIRepository('data/zakopane.xlsx')
all_pois = repo.get_all()
pois_dict = [p.model_dump(by_alias=False) for p in all_pois]

user = {
    "target_group": "friends",
    "group_size": 3,
    "children_age": None,
    "crowd_tolerance": 2,
    "budget_level": 2,
    "preferences": ["outdoor", "adventure"],
    "travel_style": "adventure"
}

context = {
    "has_car": True,
    "season": "winter",
    "region_type": "mountain",
    "weather": {"temp": 15, "precip": False, "wind": 0},
    "transport": "car",
    "date": date(2026, 2, 15),
    "daylight_end": None
}

print("=== GENERATING PLAN ===")
print(f"POI count: {len(pois_dict)}")
print(f"Date: {context['date']}")
print(f"Preferences: {user['preferences']}")

plan = build_day(
    pois=pois_dict,
    user=user,
    context=context,
    day_start="10:00",
    day_end="18:00"
)

print(f"\n=== PLAN ITEMS: {len(plan)} ===\n")

last_end_time = "10:00"
for i, item in enumerate(plan):
    item_type = item.get("type")
    
    if item_type == "accommodation_start":
        print(f"{i}. DAY START: {item.get('time')}")
        last_end_time = item.get('time')
    
    elif item_type == "attraction":
        start = item.get("start_time")
        end = item.get("end_time")
        name = item.get("name")
        
        # Calculate gap from last item
        from app.domain.planner.time_utils import time_to_minutes
        gap_min = time_to_minutes(start) - time_to_minutes(last_end_time)
        
        gap_str = f" (gap: {gap_min} min)" if gap_min > 0 else ""
        print(f"{i}. ATTRACTION: {name} | {start}-{end}{gap_str}")
        last_end_time = end
    
    elif item_type == "transfer":
        duration = item.get("duration_min")
        from_poi = item.get("from")
        to_poi = item.get("to")
        print(f"{i}. TRANSIT: {from_poi} → {to_poi} | {duration} min")
        from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
        last_end_time = minutes_to_time(time_to_minutes(last_end_time) + duration)
    
    elif item_type == "lunch_break":
        start = item.get("start_time")
        end = item.get("end_time")
        print(f"{i}. LUNCH: {start}-{end}")
        last_end_time = end
    
    elif item_type == "free_time":
        start = item.get("start_time")
        end = item.get("end_time")
        duration = item.get("duration_min")
        print(f"{i}. FREE TIME: {start}-{end} ({duration} min)")
        last_end_time = end

print("\n=== GAP ANALYSIS ===")
print("Check for gaps >20 min between POI")
