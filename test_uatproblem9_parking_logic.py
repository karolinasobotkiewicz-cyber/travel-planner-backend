"""
Unit test - Verify Problem #9 (parking logic reuse) fix

UAT Problem #9:
- ISSUE: Parking references niespójne - Muzeum ma parking "Krupówki 20",
  ale w planie jest tylko "Parking miejski" pod Krokwią
- EXPECTED: Dodać parking item przed atrakcjami gdy transit był CAR

Test verifies:
- Parking generated before first attraction (already working)
- Parking generated before subsequent attractions after CAR transit
- No duplicate parking items (different parking_name)
- No parking when transit was WALK (<10 min)
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import (
    TripInput,
    GroupInput,
    TripLengthInput,
    BudgetInput,
    LocationInput,
    DailyTimeWindow
)
from app.domain.models.plan import ItemType
from unittest.mock import MagicMock


def create_mock_poi_repository():
    """Create mock POI repository for testing"""
    mock_repo = MagicMock()
    mock_repo.get_all.return_value = []
    return mock_repo


def test_parking_before_first_attraction():
    """
    Test that parking is generated before first attraction (existing behavior)
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result: 1 attraction
    engine_result = [
        {
            "type": "accommodation_start",
            "time": "09:00"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Wielka Krokiew",
                "parking_name": "Parking miejski",
                "parking_walk_time_min": 5,
                "ticket_normal": 25
            },
            "start_time": "09:20",
            "end_time": "10:05"
        },
        {
            "type": "accommodation_end",
            "time": "19:00"
        }
    ]
    
    # Mock trip input with car
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        daily_time_window=DailyTimeWindow(start="09:00", end="19:00"),
        group=GroupInput(type="couples", size=2),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=[],
        travel_style="balanced"
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "19:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Verify parking item exists
    parking_items = [item for item in items if item.type == ItemType.PARKING]
    assert len(parking_items) >= 1, "Should have at least 1 parking item"
    
    # Verify parking is before first attraction
    first_parking_idx = next(i for i, item in enumerate(items) if item.type == ItemType.PARKING)
    first_attraction_idx = next(i for i, item in enumerate(items) if item.type == ItemType.ATTRACTION)
    
    assert first_parking_idx < first_attraction_idx, "Parking should be before first attraction"
    
    print(f"✅ Test PASSED - Parking before first attraction: {parking_items[0].name}")


def test_parking_after_car_transit():
    """
    Test UAT Problem #9: Parking generated before attraction after CAR transit
    
    Scenario:
    - Wielka Krokiew (parking: "Parking miejski")
    - CAR transit 15 min
    - Muzeum Tatrzańskie (parking: "Krupówki 20")
    
    SHOULD generate 2 parking items (different parking_name)
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result: 2 attractions with CAR transit between
    engine_result = [
        {
            "type": "accommodation_start",
            "time": "09:00"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Wielka Krokiew",
                "parking_name": "Parking miejski",
                "parking_walk_time_min": 5,
                "ticket_normal": 25
            },
            "start_time": "09:20",
            "end_time": "10:05"
        },
        {
            "type": "transfer",
            "duration_min": 15,  # CAR transit (>= 10 min)
            "from": "Wielka Krokiew",
            "to": "Muzeum Tatrzańskie"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Muzeum Tatrzańskie",
                "parking_name": "Krupówki 20",  # Different parking!
                "parking_walk_time_min": 3,
                "ticket_normal": 15
            },
            "start_time": "10:45",
            "end_time": "11:45"
        },
        {
            "type": "accommodation_end",
            "time": "19:00"
        }
    ]
    
    # Mock trip input with car
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        daily_time_window=DailyTimeWindow(start="09:00", end="19:00"),
        group=GroupInput(type="friends", size=4),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=["active_sport", "history_mystery"],
        travel_style="adventure"
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "19:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Verify 2 parking items exist
    parking_items = [item for item in items if item.type == ItemType.PARKING]
    assert len(parking_items) == 2, f"Should have 2 parking items, got {len(parking_items)}"
    
    # Verify different parking names
    parking_names = [p.name for p in parking_items]
    assert "Parking miejski" in parking_names[0], f"First parking should be 'Parking miejski', got {parking_names[0]}"
    assert "Krupówki 20" in parking_names[1], f"Second parking should be 'Krupówki 20', got {parking_names[1]}"
    
    # Verify order: parking1 -> attraction1 -> transit -> parking2 -> attraction2
    item_types = [item.type for item in items[:8]]  # First 8 items
    
    parking1_idx = next(i for i, item in enumerate(items) if item.type == ItemType.PARKING)
    attraction1_idx = next(i for i, item in enumerate(items) if item.type == ItemType.ATTRACTION)
    transit_idx = next(i for i, item in enumerate(items) if item.type == ItemType.TRANSIT)
    parking2_idx = next(i for i, item in enumerate(items) if i > parking1_idx and item.type == ItemType.PARKING)
    
    assert parking1_idx < attraction1_idx < transit_idx < parking2_idx, (
        "Order should be: parking1 -> attraction1 -> transit -> parking2"
    )
    
    print(f"✅ Test PASSED - 2 parking items:")
    print(f"   1. {parking_items[0].name} (before first attraction)")
    print(f"   2. {parking_items[1].name} (before second attraction after CAR transit)")


def test_no_parking_after_walk_transit():
    """
    Test that parking is NOT generated after WALK transit (<10 min)
    
    Scenario:
    - Muzeum (parking: "Krupówki 20")
    - WALK transit 5 min
    - Dom do góry nogami (parking: "Krupówki 15")
    
    SHOULD have only 1 parking (both attractions in same area, walking distance)
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result: 2 attractions with WALK transit between
    engine_result = [
        {
            "type": "accommodation_start",
            "time": "09:00"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Muzeum Tatrzańskie",
                "parking_name": "Krupówki 20",
                "parking_walk_time_min": 3,
                "ticket_normal": 15
            },
            "start_time": "09:20",
            "end_time": "10:20"
        },
        {
            "type": "transfer",
            "duration_min": 5,  # WALK transit (< 10 min)
            "from": "Muzeum Tatrzańskie",
            "to": "Dom do góry nogami"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Dom do góry nogami",
                "parking_name": "Krupówki 15",  # Different parking, but WALK distance
                "parking_walk_time_min": 2,
                "ticket_normal": 21
            },
            "start_time": "10:25",
            "end_time": "11:10"
        },
        {
            "type": "accommodation_end",
            "time": "19:00"
        }
    ]
    
    # Mock trip input with car
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        daily_time_window=DailyTimeWindow(start="09:00", end="19:00"),
        group=GroupInput(type="couples", size=2),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=["museum_heritage", "relaxation"],
        travel_style="cultural"
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "19:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Verify only 1 parking item (reused for both attractions)
    parking_items = [item for item in items if item.type == ItemType.PARKING]
    assert len(parking_items) == 1, f"Should have 1 parking item (reused), got {len(parking_items)}"
    
    print(f"✅ Test PASSED - Only 1 parking item (reused for walking distance)")


def test_no_duplicate_parking_same_name():
    """
    Test that duplicate parking items are NOT created for same parking_name
    
    Even if transit is CAR, if parking_name is same, don't create duplicate
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result: 2 attractions, SAME parking name
    engine_result = [
        {
            "type": "accommodation_start",
            "time": "09:00"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "POI 1",
                "parking_name": "Parking centrum",
                "parking_walk_time_min": 5,
                "ticket_normal": 20
            },
            "start_time": "09:20",
            "end_time": "10:20"
        },
        {
            "type": "transfer",
            "duration_min": 12,  # CAR transit
            "from": "POI 1",
            "to": "POI 2"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "POI 2",
                "parking_name": "Parking centrum",  # SAME parking!
                "parking_walk_time_min": 5,
                "ticket_normal": 25
            },
            "start_time": "10:50",
            "end_time": "11:50"
        },
        {
            "type": "accommodation_end",
            "time": "19:00"
        }
    ]
    
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        daily_time_window=DailyTimeWindow(start="09:00", end="19:00"),
        group=GroupInput(type="solo", size=1),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=[],
        travel_style="balanced"
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "19:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Verify only 1 parking item (no duplicates)
    parking_items = [item for item in items if item.type == ItemType.PARKING]
    assert len(parking_items) == 1, f"Should have 1 parking item (no duplicates), got {len(parking_items)}"
    
    print(f"✅ Test PASSED - No duplicate parking for same parking_name")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
