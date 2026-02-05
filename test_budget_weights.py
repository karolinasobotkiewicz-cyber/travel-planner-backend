"""
CLIENT REQUIREMENT TEST (04.02.2026): Budget scoring weights verification
Verify that budget scoring weights have been strengthened

Tests calculate_budget_score() directly with mock POI data
"""

import sys
sys.path.insert(0, '.')

from app.domain.scoring.budget import calculate_budget_score

def test_budget_scoring_weights():
    """Test that budget scoring weights are strengthened"""
    print("\n" + "="*80)
    print("CLIENT REQUIREMENT TEST: Budget Scoring Weights")
    print("="*80)
    print("Testing calculate_budget_score() with mock data\n")
    
    # Test cases
    test_cases = [
        {
            "name": "Low-budget user + expensive POI (delta=+2)",
            "user": {"budget": 1},  # Low budget
            "poi": {"budget_level": 3, "ticket_price": 0},  # High budget
            "expected_old": -12.0,  # Old: -6.0 * 2
            "expected_new": -20.0,  # New: -10.0 * 2
        },
        {
            "name": "High-budget user + cheap POI (delta=-2)",
            "user": {"budget": 3},  # High budget
            "poi": {"budget_level": 1, "ticket_price": 0},  # Low budget
            "expected_old": 12.0,   # Old: -6.0 * (-2)
            "expected_new": 20.0,   # New: -10.0 * (-2)
        },
        {
            "name": "Perfect match (delta=0)",
            "user": {"budget": 2},
            "poi": {"budget_level": 2, "ticket_price": 0},
            "expected_old": 0.0,
            "expected_new": 0.0,
        },
        {
            "name": "Low-budget user + expensive POI with perceived cost (1.3x)",
            "user": {"budget": 1},
            "poi": {"budget_level": 3, "ticket_price": 100, "type": "termy"},  # Termy = 1.3x multiplier
            "expected_old": -14.0,  # Old: -12 (base) + -2 (perceived 1.3x for budget=1)
            "expected_new": -23.0,  # New: -20 (base) + -3 (perceived 1.3x for budget=1)
        },
        {
            "name": "Low-budget user + expensive POI with high perceived cost (1.4x)",
            "user": {"budget": 2},  # Medium budget
            "poi": {"budget_level": 3, "ticket_price": 100, "type": "park_rozrywki"},  # 1.4x multiplier
            "expected_old": -13.0,  # Old: -10 (base) + -3 (perceived 1.4x for budget<=2)
            "expected_new": -15.0,  # New: -10 (base) + -5 (perceived 1.4x for budget<=2)
        },
    ]
    
    print("📊 TEST RESULTS:")
    print("-"*80)
    
    all_passed = True
    
    for i, test in enumerate(test_cases, 1):
        score = calculate_budget_score(test["poi"], test["user"])
        expected = test["expected_new"]
        
        print(f"\n{i}. {test['name']}")
        print(f"   User budget: {test['user']['budget']}, POI budget: {test['poi']['budget_level']}")
        print(f"   OLD weight expected: {test['expected_old']:.1f}")
        print(f"   NEW weight expected: {test['expected_new']:.1f}")
        print(f"   ACTUAL score: {score:.1f}")
        
        if abs(score - expected) < 0.1:
            print(f"   ✅ PASS - Matches new weights")
        else:
            print(f"   ❌ FAIL - Expected {expected:.1f}, got {score:.1f}")
            all_passed = False
    
    # Summary
    print("\n" + "="*80)
    print("WEIGHT STRENGTHENING VERIFICATION:")
    print("="*80)
    print("\nBase weight change: -6.0 → -10.0 (66% stronger)")
    print("Perceived cost penalties: -3/-2 → -5/-3 (66% stronger)")
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ PASS | Budget scoring weights successfully strengthened")
        print("         All test cases produce expected scores with new weights")
    else:
        print("❌ FAIL | Some test cases failed")
        print("         Budget scoring weights may not be correctly updated")
    print("="*80 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = test_budget_scoring_weights()
    sys.exit(0 if success else 1)
