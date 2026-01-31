"""
Local test to reproduce and fix gap filling issue
"""
import sys
sys.path.insert(0, ".")

from app.domain.planner.engine import build_day
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from datetime import date

print("=" * 80)
print("LOADING POI...")
print("=" * 80)

pois = load_zakopane_poi("data/zakopane.xlsx")
print(f"✓ Loaded {len(pois)} POI\n")

# Same context as production
# ⚠️ Use EXACT settings from production test!
user = {
    "target_group": "family_kids",
    "travel_style": "relaxed",
    "interests": ["dinozaury", "zoo", "family", "dzieci"],  # Force DINO PARK + Zoo selection
    "budget_level": "medium",
    "has_car": True
}

context = {
    "date": date(2026, 2, 16),  # Monday - EXACT date from production test!
    "season": "winter",
    "weather": {"temp": 5, "condition": "cloudy"}
}

print("=" * 80)
print("BUILDING PLAN...")
print("=" * 80)

plan = build_day(
    pois=pois,
    user=user,
    context=context,
    day_start="10:00",
    day_end="18:00"
)

print(f"\n✓ Plan generated with {len(plan)} items\n")

print("=" * 80)
print("ANALYZING PLAN FOR GAPS:")
print("=" * 80)

from app.domain.planner.time_utils import time_to_minutes

last_end = None
gaps_found = []

for i, item in enumerate(plan):
    item_type = item['type']
    
    # Display item
    if item_type == 'attraction':
        print(f"{i}. {item_type}: {item['name']}")
        print(f"   {item['start_time']} - {item['end_time']}")
    elif item_type == 'transfer':
        print(f"{i}. {item_type}: {item.get('from', '?')} → {item.get('to', '?')} ({item.get('duration_min', '?')} min)")
    elif item_type == 'lunch_break':
        print(f"{i}. {item_type}: {item['start_time']} - {item['end_time']}")
    elif item_type == 'free_time':
        print(f"{i}. ✓ FREE_TIME: {item['start_time']} - {item['end_time']} (FILLED GAP!)")
    else:
        print(f"{i}. {item_type}")
    
    # Calculate end time
    current_end = None
    if item_type == 'attraction':
        current_end = time_to_minutes(item['end_time'])
    elif item_type == 'transfer':
        # Transfer has no times in raw plan - calculate from last_end + duration
        if last_end is not None:
            current_end = last_end + item['duration_min']
    elif item_type == 'lunch_break':
        current_end = time_to_minutes(item['end_time'])
    elif item_type == 'accommodation_start':
        current_end = time_to_minutes(item['time'])
    elif item_type == 'free_time':
        current_end = time_to_minutes(item['end_time'])
    
    # Check gap to next item
    if current_end is not None and i < len(plan) - 1:
        next_item = plan[i + 1]
        next_type = next_item['type']
        
        next_start = None
        if next_type == 'attraction':
            next_start = time_to_minutes(next_item['start_time'])
        elif next_type == 'lunch_break':
            next_start = time_to_minutes(next_item['start_time'])
        
        if next_start is not None:
            gap = next_start - current_end
            if gap > 20:
                print(f"   ❌ GAP: {gap} min until next {next_type}!")
                gaps_found.append({
                    'from': item_type,
                    'to': next_type,
                    'gap_min': gap,
                    'end': current_end,
                    'next_start': next_start
                })
    
    if current_end:
        last_end = current_end

print("\n" + "=" * 80)
print(f"GAPS > 20 MIN FOUND: {len(gaps_found)}")
print("=" * 80)

if gaps_found:
    for gap in gaps_found:
        print(f"❌ {gap['from']} → {gap['to']}: {gap['gap_min']} min gap")
        print(f"   Should be filled with soft POI or free_time!")
    print("\n⚠️ GAP FILLING NOT WORKING!")
else:
    print("✓ No gaps > 20 min found - gap filling working correctly!")

print("\n" + "=" * 80)
print("SOFT POI AVAILABLE:")
print("=" * 80)

soft_pois = [p for p in pois 
             if p.get("must_see", 10) <= 7 
             and 10 <= p.get("time_min", 60) <= 30]

print(f"Found {len(soft_pois)} soft POI (must_see ≤7, time 10-30 min):\n")
for p in soft_pois[:10]:
    print(f"  • {p['name']}: {p.get('time_min', '?')} min, must_see={p.get('must_see', '?')}")
