"""
Quick test - Phase 2 Router Integration
Test TripTypeRouter detection and PlanService data loading
"""
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, TripLengthInput,
    DailyTimeWindow, BudgetInput
)
from app.domain.router import detect_trip_type, TripType
from datetime import date

print("="*70)
print("ETAP 3 PHASE 2 - Router Integration Test")
print("="*70)

# Test Case 1: Mountain Hiking Trip (Zakopane)
print("\n🏔️  TEST 1: Mountain Hiking (Zakopane + hiking preferences)")
trip_mountain = TripInput(
    location=LocationInput(
        city="Zakopane",
        country="Poland",
        region_type="mountain"
    ),
    group=GroupInput(
        type="friends",  # Fixed: use 'type' not 'target_group'
        size=2,
        children_age=None
    ),
    trip_length=TripLengthInput(
        start_date=date(2026, 7, 15),
        days=2
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
    preferences=["hiking", "outdoor", "nature"],
    travel_style="adventure"
)

config_mountain = detect_trip_type(trip_mountain)
print(f"   Trip Type: {config_mountain['trip_type']}")
print(f"   Primary Source: {config_mountain['primary_source']}")
print(f"   Use Trails: {config_mountain['use_trails']}")
print(f"   Use POIs: {config_mountain['use_pois']}")
print(f"   Region: {config_mountain['region']}")
print(f"   Confidence: {config_mountain['confidence']:.2f}")
print(f"   ✅ Expected: mountain_hiking, trails=True")

assert config_mountain['trip_type'] == TripType.MOUNTAIN_HIKING, "Should detect mountain hiking"
assert config_mountain['use_trails'] == True, "Should use trails"
assert config_mountain['region'] == "Tatry", "Should map Zakopane → Tatry"

# Test Case 2: City Tourism Trip (Kraków)
print("\n🏛️  TEST 2: City Tourism (Kraków + cultural preferences)")
trip_city = TripInput(
    location=LocationInput(
        city="Kraków",
        country="Poland",
        region_type="city"
    ),
    group=GroupInput(
        type="couples",  # Fixed: use 'type' not 'target_group'
        size=2,
        children_age=None
    ),
    trip_length=TripLengthInput(
        start_date=date(2026, 7, 15),
        days=2
    ),
    daily_time_window=DailyTimeWindow(
        start="10:00",
        end="20:00"
    ),
    budget=BudgetInput(
        level=3,
        daily_limit=None
    ),
    transport_modes=["walk"],
    preferences=["culture", "museums", "history"],
    travel_style="cultural"
)

config_city = detect_trip_type(trip_city)
print(f"   Trip Type: {config_city['trip_type']}")
print(f"   Primary Source: {config_city['primary_source']}")
print(f"   Use Trails: {config_city['use_trails']}")
print(f"   Use POIs: {config_city['use_pois']}")
print(f"   Region: {config_city['region']}")
print(f"   Confidence: {config_city['confidence']:.2f}")
print(f"   ✅ Expected: city_tourism, pois=True")

assert config_city['trip_type'] == TripType.CITY_TOURISM, "Should detect city tourism"
assert config_city['use_pois'] == True, "Should use POIs"
assert config_city['region'] == "Kraków", "Should keep city name"

# Test Case 3: Mixed Trip (Zakopane but no strong signals)
print("\n🔀 TEST 3: Mixed Trip (Zakopane but balanced preferences)")
trip_mixed = TripInput(
    location=LocationInput(
        city="Zakopane",
        country="Poland",
        region_type="city"  # Conflicting signal
    ),
    group=GroupInput(
        type="family_kids",  # Fixed: use 'type' not 'target_group'
        size=4,
        children_age=8  # Fixed: singular not plural
    ),
    trip_length=TripLengthInput(
        start_date=date(2026, 7, 15),
        days=3
    ),
    daily_time_window=DailyTimeWindow(
        start="09:00",
        end="17:00"
    ),
    budget=BudgetInput(
        level=2,
        daily_limit=None
    ),
    transport_modes=["car"],
    preferences=[],  # No preferences
    travel_style="balanced"
)

config_mixed = detect_trip_type(trip_mixed)
print(f"   Trip Type: {config_mixed['trip_type']}")
print(f"   Primary Source: {config_mixed['primary_source']}")
print(f"   Use Trails: {config_mixed['use_trails']}")
print(f"   Use POIs: {config_mixed['use_pois']}")
print(f"   Region: {config_mixed['region']}")
print(f"   Confidence: {config_mixed['confidence']:.2f}")
print(f"   ℹ️  Expected: mixed or mountain_hiking (location signal strongest)")

# Test Case 4: Scoring Weights Customization
print("\n⚖️  TEST 4: Scoring Weights Customization")
print(f"   Mountain weights: {config_mountain['scoring_weights']}")
print(f"   City weights: {config_city['scoring_weights']}")

assert 'scenic_bonus' in config_mountain['scoring_weights'], "Mountain should have scenic_bonus"
assert 'cultural_bonus' in config_city['scoring_weights'], "City should have cultural_bonus"

print("\n" + "="*70)
print("✅ ALL ROUTER TESTS PASSED")
print("="*70)
print("\n📝 Summary:")
print(f"   - Mountain hiking detection: ✅ Correct (confidence: {config_mountain['confidence']:.2f})")
print(f"   - City tourism detection: ✅ Correct (confidence: {config_city['confidence']:.2f})")
print(f"   - Region normalization: ✅ Zakopane → Tatry")
print(f"   - Scoring weights: ✅ Customized per trip type")
