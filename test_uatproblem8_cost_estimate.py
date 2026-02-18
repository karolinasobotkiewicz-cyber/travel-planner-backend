"""
Unit test - Verify Problem #8 (cost_estimate) is fixed

Test verifies that _estimate_cost() correctly multiplies ticket_normal by group_size
for couples (Test 06 UAT scenario).

Expected behavior:
- Rusinowa Polana: ticket_normal=11, group_size=2
- cost_estimate should be: 11 × 2 = 22 PLN (not 10 PLN)
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.application.services.plan_service import PlanService
from app.infrastructure.repositories import POIRepository


def test_cost_estimate_couples_test06():
    """
    Test exact scenario from UAT Problem #8:
    - Group type: couples
    - Group size: 2 people
    - POI: Rusinowa Polana (ticket_normal=11)
    - Expected: 11 × 2 = 22 PLN
    """
    # Initialize plan service without POI repo (not needed for _estimate_cost)
    plan_service = PlanService(poi_repository=None)
    
    # Mock POI dict (Rusinowa Polana data)
    poi_dict = {
        "name": "Rusinowa Polana",
        "ticket_normal": 11,
        "ticket_reduced": 0,
        "free_entry": False
    }
    
    # Mock user dict (Test 06 - couples, 2 people)
    user = {
        "target_group": "couples",
        "group_size": 2,
        "preferences": ["museum_heritage", "relaxation", "local_food_experience"]
    }
    
    # Calculate cost estimate
    cost_estimate = plan_service._estimate_cost(poi_dict, user)
    
    # Verify
    expected_cost = 11 * 2  # 22 PLN
    assert cost_estimate == expected_cost, (
        f"cost_estimate should be {expected_cost} PLN "
        f"(ticket_normal {poi_dict['ticket_normal']} × group_size {user['group_size']}), "
        f"got {cost_estimate} PLN"
    )
    
    print(f"✅ Test PASSED: cost_estimate = {cost_estimate} PLN (expected {expected_cost} PLN)")


def test_cost_estimate_all_group_types():
    """
    Test _estimate_cost for all group types to ensure consistency.
    """
    plan_service = PlanService(poi_repository=None)
    
    # Mock POI
    poi_dict = {
        "name": "Test POI",
        "ticket_normal": 30,
        "ticket_reduced": 20,
        "free_entry": False
    }
    
    # Test cases: (group_type, group_size, expected_cost)
    test_cases = [
        ("solo", 1, 30),           # 1 × 30 = 30
        ("couples", 2, 60),        # 2 × 30 = 60
        ("friends", 3, 90),        # 3 × 30 = 90
        ("family_kids", 4, 100),   # (2×30 + 2×20) = 100
        ("seniors", 2, 40),        # 2 × 20 = 40
    ]
    
    for group_type, group_size, expected in test_cases:
        user = {
            "target_group": group_type,
            "group_size": group_size
        }
        
        cost = plan_service._estimate_cost(poi_dict, user)
        
        assert cost == expected, (
            f"{group_type} (size {group_size}): expected {expected} PLN, got {cost} PLN"
        )
        
        print(f"✅ {group_type} (size {group_size}): {cost} PLN")
    
    print("✅ All group types test PASSED")


def test_cost_estimate_free_entry():
    """Test that free_entry POI always returns 0."""
    plan_service = PlanService(poi_repository=None)
    
    poi_dict = {
        "name": "Free POI",
        "ticket_normal": 30,
        "ticket_reduced": 20,
        "free_entry": True
    }
    
    user = {"target_group": "family_kids", "group_size": 4}
    
    cost = plan_service._estimate_cost(poi_dict, user)
    
    assert cost == 0, f"Free entry POI should cost 0 PLN, got {cost} PLN"
    print(f"✅ Free entry test PASSED: cost = {cost} PLN")


def test_cost_estimate_no_price_data():
    """Test fallback when POI has no price data (50 PLN per person)."""
    plan_service = PlanService(poi_repository=None)
    
    poi_dict = {
        "name": "No Price Data",
        "ticket_normal": 0,
        "ticket_reduced": 0,
        "free_entry": False
    }
    
    user = {"target_group": "couples", "group_size": 2}
    
    cost = plan_service._estimate_cost(poi_dict, user)
    
    expected = 2 * 50  # 100 PLN fallback
    assert cost == expected, f"No price data fallback should be {expected} PLN, got {cost} PLN"
    print(f"✅ No price data fallback test PASSED: cost = {cost} PLN")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
