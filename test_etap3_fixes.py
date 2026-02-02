"""
Test ETAP 3 fixes (02.02.2026):
- FIX #3: Transit name tracking after gap filling
- FIX #7: Attraction limits per target_group
"""
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from unittest.mock import Mock


def test_transit_name_tracking():
    """Test FIX #3: Transit 'to' names updated after gap filling"""
    print("\n=== TEST FIX #3: Transit Name Tracking ===")
    
    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType
    
    # Create mock items using Mock to avoid Pydantic validation
    transit = Mock()
    transit.type = ItemType.TRANSIT
    transit.from_location = "Starting Point"
    transit.to_location = "Original Destination"  # Will be updated
    
    gap_filler = Mock()
    gap_filler.type = ItemType.ATTRACTION
    gap_filler.name = "Gap Filler POI"
    
    original_dest = Mock()
    original_dest.type = ItemType.ATTRACTION
    original_dest.name = "Original Destination"
    
    items = [transit, gap_filler, original_dest]
    
    # Run the fix
    service = PlanService(poi_repository=None)
    updated_items = service._update_transit_destinations(items)
    
    # Verify transit points to NEXT attraction (Gap Filler POI)
    assert transit.to_location == "Gap Filler POI", f"Transit 'to' should be 'Gap Filler POI', got '{transit.to_location}'"
    
    print(f"✓ Transit 'to' updated correctly: '{transit.to_location}'")
    print("✅ FIX #3 PASSED - Transit names track correctly after gap filling\n")


def test_transit_from_after_lunch():
    """Test FIX #4: Transit 'from' after lunch should match last attraction before lunch"""
    print("=== TEST FIX #4: Transit 'from' After Lunch ===")
    
    from app.application.services.plan_service import PlanService
    from app.domain.models.plan import ItemType
    
    # Create mocks
    morning_attr = Mock()
    morning_attr.type = ItemType.ATTRACTION
    morning_attr.name = "Morning Attraction"
    
    lunch = Mock()
    lunch.type = ItemType.LUNCH_BREAK
    
    transit = Mock()
    transit.type = ItemType.TRANSIT
    transit.from_location = "Wrong Location"
    transit.to_location = "Afternoon Attraction"
    
    afternoon_attr = Mock()
    afternoon_attr.type = ItemType.ATTRACTION
    afternoon_attr.name = "Afternoon Attraction"
    
    items = [morning_attr, lunch, transit, afternoon_attr]
    
    service = PlanService(poi_repository=None)
    updated_items = service._update_transit_destinations(items)
    
    # Verify transit 'from' and 'to'
    assert transit.from_location == "Morning Attraction", f"Transit 'from' should be 'Morning Attraction', got '{transit.from_location}'"
    assert transit.to_location == "Afternoon Attraction", f"Transit 'to' should be 'Afternoon Attraction', got '{transit.to_location}'"
    
    print(f"✓ Transit 'from' after lunch: '{transit.from_location}' (correct)")
    print(f"✓ Transit 'to': '{transit.to_location}' (correct)")
    print("✅ FIX #4 PASSED - Transit 'from' tracks last attraction before lunch\n")


def test_attraction_limits():
    """Test FIX #7: Attraction limits per target_group"""
    print("=== TEST FIX #7: Attraction Limits Per Group ===")
    
    from app.domain.planner.engine import GROUP_ATTRACTION_LIMITS
    
    # Verify limits exist for all groups
    expected_groups = ["family_kids", "seniors", "solo", "couples", "friends"]
    
    for group in expected_groups:
        assert group in GROUP_ATTRACTION_LIMITS, f"Missing limits for group: {group}"
        limits = GROUP_ATTRACTION_LIMITS[group]
        
        assert "soft" in limits, f"{group} missing 'soft' limit"
        assert "hard" in limits, f"{group} missing 'hard' limit"
        assert "core_min" in limits, f"{group} missing 'core_min'"
        assert "core_max" in limits, f"{group} missing 'core_max'"
        
        print(f"✓ {group}: soft={limits['soft']}, hard={limits['hard']}, core={limits['core_min']}-{limits['core_max']}")
    
    # Verify specific limits per client requirements
    assert GROUP_ATTRACTION_LIMITS["family_kids"]["hard"] == 7, "family_kids hard limit should be 7"
    assert GROUP_ATTRACTION_LIMITS["seniors"]["hard"] == 5, "seniors hard limit should be 5"
    assert GROUP_ATTRACTION_LIMITS["solo"]["hard"] == 8, "solo hard limit should be 8"
    assert GROUP_ATTRACTION_LIMITS["couples"]["hard"] == 6, "couples hard limit should be 6"
    assert GROUP_ATTRACTION_LIMITS["friends"]["hard"] == 8, "friends hard limit should be 8"
    
    print("✅ FIX #7 PASSED - Attraction limits defined correctly\n")


def test_core_poi_limits():
    """Test FIX #7: Core POI limits enforced"""
    print("=== TEST FIX #7: Core POI Limits ===")
    
    from app.domain.planner.engine import GROUP_ATTRACTION_LIMITS
    
    # Verify core limits exist and are reasonable
    for group, limits in GROUP_ATTRACTION_LIMITS.items():
        core_min = limits["core_min"]
        core_max = limits["core_max"]
        
        assert core_min <= core_max, f"{group}: core_min ({core_min}) > core_max ({core_max})"
        assert core_max <= 2, f"{group}: core_max ({core_max}) too high (should be ≤2)"
        assert core_min >= 1, f"{group}: core_min ({core_min}) too low (should be ≥1)"
        
        print(f"✓ {group}: {core_min}-{core_max} core POI per day")
    
    print("✅ Core POI limits valid for all groups\n")


if __name__ == "__main__":
    try:
        test_transit_name_tracking()
        test_transit_from_after_lunch()
        test_attraction_limits()
        test_core_poi_limits()
        
        print("\n" + "="*60)
        print("🎉 ALL ETAP 3 TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
