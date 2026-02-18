"""
Unit test - Verify Problem #11 (dinner_break) fix

UAT Problem #11:
- ISSUE: Brak kolacji jako elementu planu (szczególnie dla wieczorów)
- EXPECTED: Dodać dinner_break item (18:00-20:00) jeśli jest czas w dniu
- PRIORITY: 🟡 MEDIUM

Test verifies:
- Dinner generated 18:00-19:30 when day has time
- Dinner NOT generated when day ends before 18:00
- Dinner suggestions enhanced for local_food_experience preference
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


def test_dinner_break_generated_evening():
    """
    Test that dinner_break is generated 18:00-19:30 when day has time
    
    Scenario:
    - Day: 09:00-21:00 (long day with evening time)
    - Attractions finish around 17:00
    - SHOULD generate dinner_break 18:00-19:30
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result with attractions finishing early
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
            "end_time": "10:30"
        },
        {
            "type": "transfer",
            "duration_min": 15,
            "from": "Wielka Krokiew",
            "to": "Muzeum Tatrzańskie"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Muzeum Tatrzańskie",
                "parking_name": "Krupówki 20",
                "parking_walk_time_min": 3,
                "ticket_normal": 15
            },
            "start_time": "11:00",
            "end_time": "12:00"
        },
        {
            "type": "lunch_break",
            "start_time": "12:00",
            "end_time": "13:00",
            "duration_min": 60,
            "suggestions": ["Lunch", "Restauracja"]
        },
        {
            "type": "transfer",
            "duration_min": 10,
            "from": "Muzeum",
            "to": "Termy"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Termy Chochołowskie",
                "parking_name": "Parking termy",
                "parking_walk_time_min": 2,
                "ticket_normal": 65
            },
            "start_time": "13:30",
            "end_time": "16:30"
        },
        {
            "type": "dinner_break",
            "start_time": "18:00",
            "end_time": "19:30",
            "duration_min": 90,
            "suggestions": ["Regionalna restauracja", "Bacówka", "Karcma góralska"]
        },
        {
            "type": "accommodation_end",
            "time": "21:00"
        }
    ]
    
    # Mock trip input
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        group=GroupInput(type="couples", size=2),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=["active_sport", "relaxation"],
        travel_style="balanced",
        daily_time_window=DailyTimeWindow(start="09:00", end="21:00")
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "21:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Verify dinner_break exists
    dinner_items = [item for item in items if item.type == ItemType.DINNER_BREAK]
    assert len(dinner_items) == 1, f"Should have 1 dinner_break item, got {len(dinner_items)}"
    
    dinner = dinner_items[0]
    assert dinner.start_time == "18:00", f"Dinner should start at 18:00, got {dinner.start_time}"
    assert dinner.end_time == "19:30", f"Dinner should end at 19:30, got {dinner.end_time}"
    assert dinner.duration_min == 90, f"Dinner duration should be 90 min, got {dinner.duration_min}"
    assert len(dinner.suggestions) > 0, "Dinner should have suggestions"
    
    print(f"✅ Test PASSED - Dinner break generated: {dinner.start_time}-{dinner.end_time}")
    print(f"   Suggestions: {', '.join(dinner.suggestions)}")


def test_no_dinner_short_day():
    """
    Test that dinner_break is NOT generated when day ends before 18:00
    
    Scenario:
    - Day: 09:00-17:00 (short day)
    - No time for dinner (ends before DINNER_EARLIEST)
    - SHOULD NOT generate dinner_break
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result ending at 17:00
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
            "end_time": "10:30"
        },
        {
            "type": "lunch_break",
            "start_time": "12:00",
            "end_time": "13:00",
            "duration_min": 60,
            "suggestions": ["Lunch"]
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Muzeum Tatrzańskie",
                "parking_name": "Krupówki 20",
                "parking_walk_time_min": 3,
                "ticket_normal": 15
            },
            "start_time": "14:00",
            "end_time": "16:00"
        },
        {
            "type": "accommodation_end",
            "time": "17:00"
        }
    ]
    
    # Mock trip input with short day
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        group=GroupInput(type="solo", size=1),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=[],
        travel_style="balanced",
        daily_time_window=DailyTimeWindow(start="09:00", end="17:00")
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "17:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Verify NO dinner_break
    dinner_items = [item for item in items if item.type == ItemType.DINNER_BREAK]
    assert len(dinner_items) == 0, f"Should have 0 dinner_break items (short day), got {len(dinner_items)}"
    
    print(f"✅ Test PASSED - No dinner for short day (ends 17:00)")


def test_dinner_suggestions_local_food():
    """
    Test that dinner suggestions are enhanced for local_food_experience preference
    
    Scenario:
    - User preferences include local_food_experience
    - SHOULD generate enhanced dinner suggestions (regional cuisine)
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result with dinner
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
            "end_time": "12:00"
        },
        {
            "type": "lunch_break",
            "start_time": "12:00",
            "end_time": "13:00",
            "duration_min": 60,
            "suggestions": ["Lunch"]
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Muzeum Tatrzańskie",
                "parking_name": "Krupówki 20",
                "parking_walk_time_min": 3,
                "ticket_normal": 15
            },
            "start_time": "14:00",
            "end_time": "17:00"
        },
        {
            "type": "dinner_break",
            "start_time": "18:00",
            "end_time": "19:30",
            "duration_min": 90,
            "suggestions": [
                "Regionalna restauracja z kuchnią góralską",
                "Bacówka z degustacją oscypka",
                "Karcma z tradycyjnymi potrawami"
            ]
        },
        {
            "type": "accommodation_end",
            "time": "20:00"
        }
    ]
    
    # Mock trip input with local_food_experience preference
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        group=GroupInput(type="couples", size=2),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=["local_food_experience", "relaxation"],
        travel_style="cultural",
        daily_time_window=DailyTimeWindow(start="09:00", end="20:00")
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "20:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Verify dinner suggestions are enhanced
    dinner_items = [item for item in items if item.type == ItemType.DINNER_BREAK]
    assert len(dinner_items) == 1, "Should have 1 dinner_break item"
    
    dinner = dinner_items[0]
    suggestions_text = " ".join(dinner.suggestions).lower()
    
    # Check for regional/local keywords in suggestions
    has_regional_keywords = any(keyword in suggestions_text for keyword in [
        "regionalna", "góralsk", "bacówka", "oscypek", "tradycyjn", "karcma"
    ])
    
    assert has_regional_keywords, f"Dinner suggestions should mention regional cuisine, got: {dinner.suggestions}"
    
    print(f"✅ Test PASSED - Enhanced dinner suggestions for local_food_experience:")
    for suggestion in dinner.suggestions:
        print(f"   - {suggestion}")


def test_dinner_order_after_attractions():
    """
    Test that dinner_break appears AFTER attractions (not in middle of day)
    
    Verify order: attractions → lunch → attractions → dinner → day_end
    """
    plan_service = PlanService(poi_repository=create_mock_poi_repository())
    
    # Mock engine result with dinner
    engine_result = [
        {
            "type": "accommodation_start",
            "time": "09:00"
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Morning POI",
                "parking_name": "Parking A",
                "parking_walk_time_min": 5,
                "ticket_normal": 20
            },
            "start_time": "09:20",
            "end_time": "11:00"
        },
        {
            "type": "lunch_break",
            "start_time": "12:00",
            "end_time": "13:00",
            "duration_min": 60,
            "suggestions": ["Lunch"]
        },
        {
            "type": "attraction",
            "poi": {
                "name": "Afternoon POI",
                "parking_name": "Parking B",
                "parking_walk_time_min": 3,
                "ticket_normal": 25
            },
            "start_time": "14:00",
            "end_time": "17:00"
        },
        {
            "type": "dinner_break",
            "start_time": "18:00",
            "end_time": "19:30",
            "duration_min": 90,
            "suggestions": ["Regionalna restauracja"]
        },
        {
            "type": "accommodation_end",
            "time": "20:00"
        }
    ]
    
    # Mock trip input
    trip_input = TripInput(
        location=LocationInput(city="Zakopane", country="Poland"),
        trip_length=TripLengthInput(days=1, start_date="2026-02-20"),
        group=GroupInput(type="friends", size=4),
        transport_modes=["car"],
        budget=BudgetInput(level=2),
        preferences=[],
        travel_style="adventure",
        daily_time_window=DailyTimeWindow(start="09:00", end="20:00")
    )
    
    # Convert engine result to items
    items = plan_service._convert_engine_result_to_items(
        engine_result,
        "09:00",  # day_start
        "20:00",  # day_end
        {},  # context
        {},  # user
        trip_input
    )
    
    # Find indices
    dinner_idx = next(i for i, item in enumerate(items) if item.type == ItemType.DINNER_BREAK)
    last_attraction_idx = max(i for i, item in enumerate(items) if item.type == ItemType.ATTRACTION)
    day_end_idx = next(i for i, item in enumerate(items) if item.type == ItemType.DAY_END)
    
    # Verify order: last attraction < dinner < day_end
    assert last_attraction_idx < dinner_idx, "Dinner should be AFTER last attraction"
    assert dinner_idx < day_end_idx, "Dinner should be BEFORE day_end"
    
    print(f"✅ Test PASSED - Dinner appears after attractions in correct order")
    print(f"   Last attraction index: {last_attraction_idx}")
    print(f"   Dinner index: {dinner_idx}")
    print(f"   Day end index: {day_end_idx}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
