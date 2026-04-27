"""
REGRESSION TEST - Phase 7 Destination Clusters (27.04.2026)

Sprawdza czy:
1. Wszystkie 15 single cities działają (Phase 6 regression)
2. Wszystkie 3 klastry działają (Phase 7 new feature)
3. Router poprawnie wykrywa cluster vs single city

Expected results:
- 15 single cities generate valid plans
- 3 clusters generate valid plans
- Total: 18 destinations working

Cities:
- Poznań, Gdańsk, Gdynia, Sopot, Zakopane, Kraków,
  Kłodzko, Polanica-Zdrój, Kudowa-Zdrój, Karpacz,
  Szklarska Poręba, Jelenia Góra, Wrocław, Katowice, Warszawa

Clusters:
- Trójmiasto (Gdańsk+Gdynia+Sopot)
- Kotlina Kłodzka (Kłodzko+Polanica+Kudowa)
- Karkonosze (Karpacz+Jelenia Góra+Szklarska)

Usage:
    cd travel-planner-backend
    python test_regression_phase7.py
"""

import sys
from datetime import date
from app.domain.models.trip_input import (
    TripInput,
    LocationInput,
    GroupInput,
    BudgetInput,
    TripLengthInput,
    DailyTimeWindow
)
from app.domain.config import DestinationClusters
from app.domain.router import detect_trip_type
from app.application.services.plan_service import PlanService
from app.api.dependencies import get_poi_repository

print("=" * 80)
print("ETAP 3 PHASE 7 - REGRESSION TEST (15 Cities + 3 Clusters)")
print("=" * 80)
print()

# Initialize service
print("Initializing PlanService...")
poi_repository = get_poi_repository()
plan_service = PlanService(poi_repository)
print("[OK] PlanService initialized")
print()

# =============================================================================
# TEST 1: 15 Single Cities (Phase 6 Regression)
# =============================================================================
print("[TEST 1] Single Cities - Phase 6 Regression")
print("-" * 80)

SINGLE_CITIES = [
    ("Poznań", "urban"),
    ("Gdańsk", "urban"),
    ("Gdynia", "urban"),
    ("Sopot", "urban"),
    ("Zakopane", "mountain"),
    ("Kraków", "urban"),
    ("Kłodzko", "spa_region"),
    ("Polanica-Zdrój", "spa_region"),
    ("Kudowa-Zdrój", "spa_region"),
    ("Karpacz", "mountain"),
    ("Szklarska Poręba", "mountain"),
    ("Jelenia Góra", "urban"),
    ("Wrocław", "urban"),
    ("Katowice", "urban"),
    ("Warszawa", "urban"),
]

passed_cities = []
failed_cities = []

for city_name, region_type in SINGLE_CITIES:
    try:
        print(f"\nTesting: {city_name} ({region_type})...")
        
        # Create trip input
        trip_input = TripInput(
            location=LocationInput(
                city=city_name,
                country="Poland",
                region_type=region_type,
                is_cluster=False
            ),
            trip_length=TripLengthInput(
                days=2,
                start_date=date(2026, 6, 15)
            ),
            daily_time_window=DailyTimeWindow(
                start="09:00",
                end="19:00"
            ),
            group=GroupInput(
                type="couples",
                size=2
            ),
            budget=BudgetInput(
                total_budget=800.0,
                currency="PLN"
            ),
            preferences=["culture", "nature"],
            travel_style="balanced",
            transport_modes=["car"]
        )
        
        # Test router
        router_config = detect_trip_type(trip_input)
        assert router_config["trip_type"] != "cluster", f"Router incorrectly detected cluster for single city {city_name}"
        
        # Generate plan
        plan = plan_service.generate_plan(trip_input)
        
        # Validate plan
        assert len(plan.days) > 0, f"Plan has no days for {city_name}"
        
        day1_items = len(plan.days[0].items)
        print(f"  [OK] {city_name}: {len(plan.days)} days, {day1_items} items (Day 1)")
        
        passed_cities.append(city_name)
        
    except Exception as e:
        print(f"  [FAIL] {city_name}: {str(e)}")
        failed_cities.append((city_name, str(e)))

print()
print(f"[RESULT] Single Cities: {len(passed_cities)}/15 passed")
if failed_cities:
    print(f"[FAIL] Failed cities:")
    for city, error in failed_cities:
        print(f"  - {city}: {error}")
else:
    print("[OK] All 15 single cities passed!")

# =============================================================================
# TEST 2: 3 Clusters (Phase 7 New Feature)
# =============================================================================
print()
print("[TEST 2] Clusters - Phase 7 New Feature")
print("-" * 80)

CLUSTERS = [
    ("Trójmiasto", "urban", ["culture", "beach"], ["Gdańsk", "Gdynia", "Sopot"]),
    ("Kotlina Kłodzka", "spa_region", ["wellness", "nature"], ["Kłodzko", "Polanica-Zdrój", "Kudowa-Zdrój"]),
    ("Karkonosze", "mountain", ["hiking", "nature"], ["Karpacz", "Jelenia Góra", "Szklarska Poręba"]),
]

passed_clusters = []
failed_clusters = []

for cluster_name, region_type, preferences, expected_cities in CLUSTERS:
    try:
        print(f"\nTesting: {cluster_name} ({region_type})...")
        print(f"  Expected cities: {expected_cities}")
        
        # Create trip input
        trip_input = TripInput(
            location=LocationInput(
                city=cluster_name,
                country="Poland",
                region_type=region_type,
                is_cluster=True
            ),
            trip_length=TripLengthInput(
                days=2,
                start_date=date(2026, 7, 1)
            ),
            daily_time_window=DailyTimeWindow(
                start="09:00",
                end="19:00"
            ),
            group=GroupInput(
                type="friends",
                size=4
            ),
            budget=BudgetInput(
                total_budget=1200.0,
                currency="PLN"
            ),
            preferences=preferences,
            travel_style="balanced",
            transport_modes=["car"]
        )
        
        # Test router
        router_config = detect_trip_type(trip_input)
        assert router_config["trip_type"] == "cluster", f"Router didn't detect cluster for {cluster_name}"
        assert router_config["cities"] == expected_cities, f"Wrong cities for {cluster_name}: {router_config['cities']} vs {expected_cities}"
        
        print(f"  [OK] Router detected cluster: {router_config['trip_type']}")
        print(f"  [OK] Cities: {router_config['cities']}")
        
        # Generate plan
        plan = plan_service.generate_plan(trip_input)
        
        # Validate plan
        assert len(plan.days) > 0, f"Plan has no days for {cluster_name}"
        
        day1_items = len(plan.days[0].items)
        print(f"  [OK] {cluster_name}: {len(plan.days)} days, {day1_items} items (Day 1)")
        
        passed_clusters.append(cluster_name)
        
    except Exception as e:
        print(f"  [FAIL] {cluster_name}: {str(e)}")
        failed_clusters.append((cluster_name, str(e)))

print()
print(f"[RESULT] Clusters: {len(passed_clusters)}/3 passed")
if failed_clusters:
    print(f"[FAIL] Failed clusters:")
    for cluster, error in failed_clusters:
        print(f"  - {cluster}: {error}")
else:
    print("[OK] All 3 clusters passed!")

# =============================================================================
# TEST 3: Router Detection Accuracy
# =============================================================================
print()
print("[TEST 3] Router Detection Accuracy")
print("-" * 80)

# Test 3.1: Single city should NOT be detected as cluster
print("\n3.1 Single city detection...")
single_city_test = LocationInput(
    city="Kraków",
    country="Poland",
    is_cluster=False
)
trip_input_single = TripInput(
    location=single_city_test,
    trip_length=TripLengthInput(days=2, start_date=date(2026, 6, 1)),
    daily_time_window=DailyTimeWindow(start="09:00", end="19:00"),
    group=GroupInput(type="solo", size=1),
    budget=BudgetInput(total_budget=500.0, currency="PLN"),
    preferences=["culture"],
    travel_style="relax",
    transport_modes=["public_transport"]
)
router_config_single = detect_trip_type(trip_input_single)
assert router_config_single["trip_type"] != "cluster", "Single city incorrectly detected as cluster"
print(f"  [OK] Kraków detected as: {router_config_single['trip_type']} (NOT cluster)")

# Test 3.2: Cluster should be detected as cluster
print("\n3.2 Cluster detection...")
cluster_test = LocationInput(
    city="Trójmiasto",
    country="Poland",
    region_type="urban",
    is_cluster=True
)
trip_input_cluster = TripInput(
    location=cluster_test,
    trip_length=TripLengthInput(days=2, start_date=date(2026, 6, 1)),
    daily_time_window=DailyTimeWindow(start="09:00", end="19:00"),
    group=GroupInput(type="solo", size=1),
    budget=BudgetInput(total_budget=500.0, currency="PLN"),
    preferences=["culture"],
    travel_style="relax",
    transport_modes=["public_transport"]
)
router_config_cluster = detect_trip_type(trip_input_cluster)
assert router_config_cluster["trip_type"] == "cluster", f"Cluster detected as: {router_config_cluster['trip_type']}"
assert len(router_config_cluster["cities"]) == 3, f"Expected 3 cities, got {len(router_config_cluster['cities'])}"
print(f"  [OK] Trójmiasto detected as: cluster")
print(f"  [OK] Cities: {router_config_cluster['cities']}")

# Test 3.3: Invalid cluster should fail validation
print("\n3.3 Invalid cluster validation...")
try:
    invalid_cluster = LocationInput(
        city="FakeCluster",
        country="Poland",
        is_cluster=True
    )
    print(f"  [FAIL] Invalid cluster accepted")
    sys.exit(1)
except ValueError as e:
    print(f"  [OK] Invalid cluster rejected: {str(e)}")

print()
print("[OK] Router detection accuracy validated")

# =============================================================================
# FINAL SUMMARY
# =============================================================================
print()
print("=" * 80)
print("FINAL SUMMARY")
print("=" * 80)
print()
print(f"Single Cities (Phase 6):  {len(passed_cities)}/15 passed")
print(f"Clusters (Phase 7):       {len(passed_clusters)}/3 passed")
print(f"Total Destinations:       {len(passed_cities) + len(passed_clusters)}/18 working")
print()

if len(passed_cities) == 15 and len(passed_clusters) == 3:
    print("[OK] ALL REGRESSION TESTS PASSED!")
    print()
    print("Phase 7 Implementation Summary:")
    print("  [OK] 15 single cities working (no regressions)")
    print("  [OK] 3 destination clusters working (new feature)")
    print("  [OK] Router correctly detects cluster vs single city")
    print("  [OK] Multi-city data loading operational")
    print()
    print("Ready for production deployment!")
else:
    print("[FAIL] SOME TESTS FAILED")
    if failed_cities:
        print(f"\nFailed single cities ({len(failed_cities)}):")
        for city, error in failed_cities:
            print(f"  - {city}: {error}")
    if failed_clusters:
        print(f"\nFailed clusters ({len(failed_clusters)}):")
        for cluster, error in failed_clusters:
            print(f"  - {cluster}: {error}")
    sys.exit(1)
