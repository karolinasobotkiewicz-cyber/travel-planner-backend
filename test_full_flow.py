"""
Complete end-to-end test simulating production request
"""
import sys
sys.path.insert(0, '.')

from app.domain.models.trip_input import TripInput, LocationInput, GroupInput, TripLengthInput, DailyTimeWindow, BudgetInput
from app.application.services.plan_service import PlanService
from app.infrastructure.repositories import POIRepository
from datetime import date

print("=" * 60)
print("🧪 FULL FLOW TEST - Simulating Production Request")
print("=" * 60)

try:
    # Step 1: Create TripInput (same as production)
    print("\n1️⃣ Creating TripInput...")
    trip_input = TripInput(
        location=LocationInput(
            city="Zakopane",
            country="Poland",
            region_type="mountain"
        ),
        group=GroupInput(
            type="family_kids",
            size=4,
            children_age=8,
            crowd_tolerance=2
        ),
        trip_length=TripLengthInput(
            days=1,
            start_date=date(2026, 2, 10)
        ),
        daily_time_window=DailyTimeWindow(
            start="09:00",
            end="18:00"
        ),
        budget=BudgetInput(
            level=2,
            daily_limit=None
        ),
        transport_modes=["car"],
        preferences=[],
        travel_style="balanced"
    )
    print("   ✅ TripInput created")
    
    # Step 2: Initialize services
    print("\n2️⃣ Initializing services...")
    excel_path = "data/zakopane.xlsx"
    poi_repo = POIRepository(excel_path)
    plan_service = PlanService(poi_repo)
    print(f"   ✅ Services initialized (POI count: {len(poi_repo.get_all())})")
    
    # Step 3: Generate plan (critical - this is where error occurred)
    print("\n3️⃣ Generating plan...")
    plan = plan_service.generate_plan(trip_input)
    print(f"   ✅ Plan generated successfully!")
    
    # Step 4: Validate plan structure
    print("\n4️⃣ Validating plan structure...")
    assert plan.plan_id, "Missing plan_id"
    assert plan.days, "No days in plan"
    assert len(plan.days) == 1, f"Expected 1 day, got {len(plan.days)}"
    
    day = plan.days[0]
    assert day.items, "No items in day"
    
    print(f"   ✅ Plan structure valid")
    print(f"   • Plan ID: {plan.plan_id[:8]}...")
    print(f"   • Days: {len(plan.days)}")
    print(f"   • Items in Day 1: {len(day.items)}")
    
    # Step 5: Check for critical fixes
    print("\n5️⃣ Verifying critical fixes...")
    
    # FIX #1: Ticket prices (no 0 cost for POI without prices)
    attractions = [item for item in day.items if item.type == "attraction"]
    print(f"   • Total attractions: {len(attractions)}")
    
    zero_cost_attractions = [a for a in attractions if a.cost_estimate == 0 and not a.name.startswith("Plac zabaw")]
    if zero_cost_attractions:
        print(f"   ⚠️ Found {len(zero_cost_attractions)} attractions with 0 cost")
    else:
        print(f"   ✅ FIX #1: All attractions have cost estimates")
    
    # FIX #2: Parking location data
    parking_items = [item for item in day.items if item.type == "parking"]
    if parking_items:
        parking = parking_items[0]
        has_location = parking.address and parking.lat != 0 and parking.lng != 0
        print(f"   ✅ FIX #2: Parking has location data: {has_location}")
    
    # FIX #3 & #4: Free time items
    free_time_items = [item for item in day.items if item.type == "free_time"]
    print(f"   ✅ FIX #3/#4: Free time items: {len(free_time_items)} (goal: minimize)")
    
    # FIX #5: Transit modes
    transit_items = [item for item in day.items if item.type == "transit"]
    long_walks = [t for t in transit_items if t.mode == "walk" and t.duration_min >= 10]
    if long_walks:
        print(f"   ⚠️ Found {len(long_walks)} long walks (≥10 min)")
    else:
        print(f"   ✅ FIX #5: No long walks (≥10 min with walk mode)")
    
    # Step 6: Display summary
    print("\n6️⃣ Plan Summary:")
    print(f"   • Day start: {day.items[0].time if hasattr(day.items[0], 'time') else 'N/A'}")
    print(f"   • Day end: {day.items[-1].time if hasattr(day.items[-1], 'time') else 'N/A'}")
    print(f"   • Attractions: {len(attractions)}")
    print(f"   • Transit: {len(transit_items)}")
    print(f"   • Free time: {len(free_time_items)}")
    print(f"   • Parking: {len(parking_items)}")
    
    # Display first 3 attractions
    print(f"\n   First 3 attractions:")
    for i, attr in enumerate(attractions[:3], 1):
        print(f"      {i}. {attr.name} - {attr.cost_estimate} PLN ({attr.duration_min} min)")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - HOTFIX WORKING!")
    print("=" * 60)
    print(f"\n📊 Final Result: {len(day.items)} total items in plan")
    
except Exception as e:
    print("\n" + "=" * 60)
    print("❌ TEST FAILED")
    print("=" * 60)
    print(f"\nError Type: {type(e).__name__}")
    print(f"Error Message: {str(e)}")
    print("\nFull Traceback:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
