"""
INTEGRATION TEST: Bug #1 - Parking Overlap Fix

Date: 19.02.2026
Purpose: Test real API call with car transport to verify parking items don't overlap with transits

Test Scenario:
- 3-day trip to Zakopane
- Car transport (parking will be added)
- Check all parking items start AT or AFTER transit ends

Expected Results:
- NO parking/transit overlaps
- Timeline physically possible (user can actually follow the plan)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.application.services.plan_service import PlanService
from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, TripLengthInput, 
    DailyTimeWindow, BudgetInput
)
from app.domain.planner.time_utils import time_to_minutes
from datetime import date


def test_parking_overlap_integration():
    """
    Integration test: Generate real plan and validate no parking/transit overlaps.
    """
    
    print("\n" + "="*80)
    print("INTEGRATION TEST: Parking Overlap Fix (Bug #1)")
    print("="*80)
    
    # Setup
    print("\n[1] Initializing services...")
    poi_repo = POIRepository("data/zakopane.xlsx")
    plan_service = PlanService(poi_repo)
    print(f"   OK Services initialized (POI count: {len(poi_repo.get_all())})")
    
    # Test input (similar to UAT Test 01)
    print("\n[2] Creating trip input...")
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
            days=3,
            start_date=date(2026, 3, 1)
        ),
        daily_time_window=DailyTimeWindow(
            start="09:00",
            end="19:00"
        ),
        budget=BudgetInput(
            level=2,
            daily_limit=500
        ),
        transport_modes=["car"],  # CAR → parking will be added
        preferences=["nature", "adventure", "water_attractions"],
        travel_style="adventure"  # active → adventure
    )
    
    print(f"   • Destination: {trip_input.location.city}")
    print(f"   • Days: {trip_input.trip_length.days}")
    print(f"   • Transport: {trip_input.transport_modes}")
    print(f"   • Group: {trip_input.group.type}, size={trip_input.group.size}")
    
    # Generate plan
    print(f"\n[3] Generating plan...")
    
    try:
        plan_response = plan_service.generate_plan(trip_input)
    except Exception as e:
        print(f"ERROR GENERATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"OK Plan generated: {len(plan_response.days)} days")
    
    # Validate each day
    print(f"\n[4] Validating parking/transit timeline...")
    all_pass = True
    overlap_count = 0
    
    for day in plan_response.days:
        print(f"\n--- Day {day.day} ---")
        
        items = day.items
        
        # Find all transits and parkings
        transits = []
        parkings = []
        
        for i, item in enumerate(items):
            if hasattr(item, 'type'):
                if item.type == "transit":
                    transits.append((i, item))
                elif item.type == "parking":
                    parkings.append((i, item))
        
        print(f"  Transits: {len(transits)}")
        print(f"  Parkings: {len(parkings)}")
        
        # Check each parking
        for parking_idx, parking in parkings:
            parking_start_min = time_to_minutes(parking.start_time)
            parking_end_min = time_to_minutes(parking.end_time)
            
            # Find preceding transit (if any)
            preceding_transit = None
            for transit_idx, transit in transits:
                if transit_idx < parking_idx:
                    preceding_transit = (transit_idx, transit)
            
            if preceding_transit:
                transit_idx, transit = preceding_transit
                transit_end_min = time_to_minutes(transit.end_time)
                
                print(f"\n  Transit {transit_idx}: {transit.start_time} - {transit.end_time}")
                print(f"  Parking {parking_idx}: {parking.start_time} - {parking.end_time}")
                
                # Validation: parking_start >= transit_end
                if parking_start_min < transit_end_min:
                    print(f"  [X] OVERLAP DETECTED!")
                    print(f"     Parking starts at {parking.start_time}")
                    print(f"     But transit ends at {transit.end_time}")
                    print(f"     Overlap: {transit_end_min - parking_start_min} minutes")
                    all_pass = False
                    overlap_count += 1
                elif parking_start_min == transit_end_min:
                    print(f"  [OK] PERFECT: Parking starts exactly when transit ends")
                else:
                    gap = parking_start_min - transit_end_min
                    print(f"  [OK] Parking starts {gap} min after transit ends")
            else:
                print(f"\n  Parking {parking_idx}: {parking.start_time} - {parking.end_time}")
                print(f"  [INFO] No preceding transit (first parking of the day)")
        
        # Also check for any time paradoxes (item starting before previous ends)
        print(f"\n  Timeline Continuity Check:")
        for i in range(1, len(items)):
            prev_item = items[i-1]
            curr_item = items[i]
            
            # Skip day_start/day_end
            if not hasattr(prev_item, 'end_time') or not hasattr(curr_item, 'start_time'):
                continue
            
            prev_end_min = time_to_minutes(prev_item.end_time)
            curr_start_min = time_to_minutes(curr_item.start_time)
            
            if curr_start_min < prev_end_min:
                print(f"  [X] TIME PARADOX: Item {i} starts BEFORE item {i-1} ends")
                print(f"     {prev_item.type} ends: {prev_item.end_time}")
                print(f"     {curr_item.type} starts: {curr_item.start_time}")
                all_pass = False
    
    # Summary
    print(f"\n" + "="*80)
    if all_pass:
        print("[PASS] INTEGRATION TEST PASSED")
        print("   - NO parking/transit overlaps detected")
        print("   - Timeline is physically possible")
        print("   - Bug #1 fix is working correctly")
    else:
        print(f"[FAIL] INTEGRATION TEST FAILED")
        print(f"   - {overlap_count} parking/transit overlaps detected")
        print(f"   - Bug #1 fix may not be working correctly")
    print("="*80)
    
    return all_pass


if __name__ == "__main__":
    success = test_parking_overlap_integration()
    
    if success:
        print("\n[SUCCESS] BUG #1 FIX VALIDATED - Ready for UAT testing")
        print("\nNext Steps:")
        print("1. [OK] Unit test passed")
        print("2. [OK] Integration test passed")
        print("3. [TODO] Run all 10 UAT scenarios")
        print("4. [TODO] Verify no regression (run existing tests)")
        print("5. [TODO] Create comprehensive bugfix report")
    else:
        print("\n[FAIL] BUGFIX NEEDS REVIEW")
        print("Check plan_service.py parking logic")
