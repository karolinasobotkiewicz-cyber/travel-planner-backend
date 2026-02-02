"""
Manual test ETAP 1 fixes:
FIX #1: parking_walk_time_min = 1 (not 5)
FIX #2: No free_time before open attractions
"""

from app.infrastructure.repositories.poi_repository import POIRepository
from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, TripLengthInput,
    DailyTimeWindow, BudgetInput
)
from datetime import date

print("="*80)
print("🧪 MANUAL TEST - ETAP 1 FIXES")
print("="*80)

# Initialize services
poi_repo = POIRepository("data/zakopane.xlsx")
plan_service = PlanService(poi_repo)

print(f"\n✅ POI Repository: {len(poi_repo.get_all())} POIs loaded")

# Create test request
trip_input = TripInput(
    location=LocationInput(city="Zakopane", country="Poland", region_type="mountain"),
    group=GroupInput(type="family_kids", size=4, children_age=8, crowd_tolerance=1),
    trip_length=TripLengthInput(days=1, start_date=date(2026, 2, 15)),
    daily_time_window=DailyTimeWindow(start="09:00", end="18:00"),
    budget=BudgetInput(level=2, daily_limit=500),
    transport_modes=["car"],
    preferences=["family_kids", "outdoor"],
    travel_style="balanced"
)

print("\n📋 Generating plan...")
plan = plan_service.generate_plan(trip_input)

print(f"\n✅ Plan generated: {plan.plan_id}")
print(f"   Days: {len(plan.days)}")

day1 = plan.days[0]
print(f"\n📊 Day 1: {len(day1.items)} items")

# Verify FIX #1: Parking walk_time_min
print("\n" + "="*80)
print("🔍 FIX #1 VERIFICATION: parking_walk_time_min")
print("="*80)

parking_item = None
first_attraction = None

for item in day1.items:
    if item.type == "parking":
        parking_item = item
    elif item.type == "attraction" and parking_item and not first_attraction:
        first_attraction = item
        break

if parking_item and first_attraction:
    walk_time = parking_item.walk_time_min
    poi_name = first_attraction.name
    
    print(f"Parking: {parking_item.name}")
    print(f"  walk_time_min: {walk_time}")
    print(f"First attraction: {poi_name}")
    
    # Check if it's Zoo (should be 1, not 5)
    if "Zoo" in poi_name:
        if walk_time == 1:
            print("✅ FIX #1 SUCCESS: walk_time_min = 1 (correct!)")
        else:
            print(f"❌ FIX #1 FAILED: walk_time_min = {walk_time} (expected 1)")
    else:
        print(f"ℹ️  walk_time_min = {walk_time} (POI: {poi_name})")
else:
    print("⚠️  No parking or first attraction found")

# Verify FIX #2: No free_time before open attractions
print("\n" + "="*80)
print("🔍 FIX #2 VERIFICATION: Free_time before opening")
print("="*80)

free_time_count = 0
problematic_free_time = []

for i, item in enumerate(day1.items):
    if item.type == "free_time":
        free_time_count += 1
        
        # Check if next item is attraction
        if i < len(day1.items) - 1:
            next_item = day1.items[i + 1]
            if next_item.type == "attraction":
                problematic_free_time.append({
                    'free_time': f"{item.start_time}-{item.end_time}",
                    'next_attraction': next_item.name,
                    'attraction_start': next_item.start_time
                })

print(f"Total free_time items: {free_time_count}")

if problematic_free_time:
    print("\n❌ FIX #2 POTENTIAL ISSUES:")
    for item in problematic_free_time:
        print(f"  • Free_time: {item['free_time']}")
        print(f"    Before: {item['next_attraction']} (starts {item['attraction_start']})")
else:
    print("✅ FIX #2 SUCCESS: No free_time before attractions")

print("\n" + "="*80)
print("📊 SUMMARY")
print("="*80)
print(f"Total items: {len(day1.items)}")
print(f"Attractions: {sum(1 for i in day1.items if i.type == 'attraction')}")
print(f"Transit: {sum(1 for i in day1.items if i.type == 'transit')}")
print(f"Free_time: {free_time_count}")
print(f"Parking: {sum(1 for i in day1.items if i.type == 'parking')}")

print("\n" + "="*80)
print("✅ ETAP 1 TEST COMPLETE")
print("="*80)
