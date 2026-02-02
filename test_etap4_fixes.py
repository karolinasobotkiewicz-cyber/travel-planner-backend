"""
Test ETAP 4 fixes (02.02.2026):
- FIX #5: Evening/night time scoring (kulig po zmroku)
"""
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from app.domain.scoring.time_of_day_scoring import (
    time_to_period,
    calculate_time_of_day_score
)


def test_time_to_period_evening_night():
    """Test FIX #5: Evening/night period mapping"""
    print("\n=== TEST FIX #5: Evening/Night Period Mapping ===")
    
    # Test evening (18:00-20:00)
    assert time_to_period("18:00") == "evening", "18:00 should be evening"
    assert time_to_period("19:00") == "evening", "19:00 should be evening"
    assert time_to_period("19:30") == "evening", "19:30 should be evening"
    
    # Test night (20:00+)
    assert time_to_period("20:00") == "night", "20:00 should be night"
    assert time_to_period("21:00") == "night", "21:00 should be night"
    assert time_to_period("22:00") == "night", "22:00 should be night"
    
    # Test day periods (regression)
    assert time_to_period("10:00") == "morning", "10:00 should be morning"
    assert time_to_period("12:00") == "midday", "12:00 should be midday"
    assert time_to_period("15:00") == "afternoon", "15:00 should be afternoon"
    assert time_to_period("16:00") == "afternoon", "16:00 should be afternoon"
    
    print("✓ Evening: 18:00-20:00")
    print("✓ Night: 20:00+")
    print("✓ Day periods: morning/midday/afternoon (regression OK)")
    print("✅ Period mapping PASSED\n")


def test_kulig_evening_bonus():
    """Test FIX #5: KULIGI gets bonus when scheduled in evening"""
    print("=== TEST FIX #5: Kulig Evening Bonus ===")
    
    kulig = {
        "name": "KULIGI w Zakopanem",
        "recommended_time_of_day": "evening"
    }
    
    # Test 1: Kulig at 18:30 (evening) = BONUS +15
    score_evening = calculate_time_of_day_score(kulig, {}, {}, 18*60 + 30)  # 1110 min
    print(f"Kulig at 18:30 (evening): score = {score_evening} (expected +15)")
    assert score_evening == 15, f"Evening kulig should get +15 bonus, got {score_evening}"
    
    # Test 2: Kulig at 20:30 (night) = BONUS +10 (compatible)
    score_night = calculate_time_of_day_score(kulig, {}, {}, 20*60 + 30)  # 1230 min
    print(f"Kulig at 20:30 (night): score = {score_night} (expected +10)")
    assert score_night == 10, f"Night kulig should get +10 bonus (compatible), got {score_night}"
    
    print("✅ Kulig evening/night bonus PASSED\n")


def test_kulig_day_penalty():
    """Test FIX #5: KULIGI gets severe penalty when scheduled during day"""
    print("=== TEST FIX #5: Kulig Day Penalty ===")
    
    kulig = {
        "name": "KULIGI w Zakopanem",
        "recommended_time_of_day": "evening"
    }
    
    # Test 1: Kulig at 15:54 (afternoon) = PENALTY -50
    score_afternoon = calculate_time_of_day_score(kulig, {}, {}, 15*60 + 54)  # 954 min
    print(f"Kulig at 15:54 (afternoon): score = {score_afternoon} (expected -50)")
    assert score_afternoon == -50, f"Afternoon kulig should get -50 penalty, got {score_afternoon}"
    
    # Test 2: Kulig at 12:00 (midday) = PENALTY -50
    score_midday = calculate_time_of_day_score(kulig, {}, {}, 12*60)  # 720 min
    print(f"Kulig at 12:00 (midday): score = {score_midday} (expected -50)")
    assert score_midday == -50, f"Midday kulig should get -50 penalty, got {score_midday}"
    
    # Test 3: Kulig at 10:00 (morning) = PENALTY -50
    score_morning = calculate_time_of_day_score(kulig, {}, {}, 10*60)  # 600 min
    print(f"Kulig at 10:00 (morning): score = {score_morning} (expected -50)")
    assert score_morning == -50, f"Morning kulig should get -50 penalty, got {score_morning}"
    
    print("✅ Kulig day penalty PASSED\n")


def test_evening_night_compatibility():
    """Test FIX #5: Evening and night POI are compatible"""
    print("=== TEST FIX #5: Evening/Night Compatibility ===")
    
    # Evening POI at night = +10 bonus
    evening_poi = {"recommended_time_of_day": "evening"}
    score = calculate_time_of_day_score(evening_poi, {}, {}, 21*60)  # 21:00 = night
    print(f"Evening POI at 21:00 (night): score = {score} (expected +10)")
    assert score == 10, f"Evening POI at night should get +10, got {score}"
    
    # Night POI at evening = +10 bonus
    night_poi = {"recommended_time_of_day": "night"}
    score = calculate_time_of_day_score(night_poi, {}, {}, 19*60)  # 19:00 = evening
    print(f"Night POI at 19:00 (evening): score = {score} (expected +10)")
    assert score == 10, f"Night POI at evening should get +10, got {score}"
    
    print("✅ Evening/night compatibility PASSED\n")


def test_day_poi_at_night_penalty():
    """Test FIX #5: Day POI scheduled at night gets penalty"""
    print("=== TEST FIX #5: Day POI at Night Penalty ===")
    
    # Afternoon POI at night = -30 penalty
    afternoon_poi = {"recommended_time_of_day": "afternoon"}
    score = calculate_time_of_day_score(afternoon_poi, {}, {}, 21*60)  # 21:00 = night
    print(f"Afternoon POI at 21:00 (night): score = {score} (expected -30)")
    assert score == -30, f"Afternoon POI at night should get -30 penalty, got {score}"
    
    # Morning POI at evening = -30 penalty (day POI at night/evening)
    morning_poi = {"recommended_time_of_day": "morning"}
    score = calculate_time_of_day_score(morning_poi, {}, {}, 19*60)  # 19:00 = evening
    print(f"Morning POI at 19:00 (evening): score = {score} (expected -30)")
    assert score == -30, f"Morning POI at evening should get -30 penalty, got {score}"
    
    print("✅ Day POI at night penalty PASSED\n")


if __name__ == "__main__":
    try:
        test_time_to_period_evening_night()
        test_kulig_evening_bonus()
        test_kulig_day_penalty()
        test_evening_night_compatibility()
        test_day_poi_at_night_penalty()
        
        print("\n" + "="*60)
        print("🎉 ALL ETAP 4 TESTS PASSED!")
        print("="*60)
        print("\n📊 Summary:")
        print("✅ Evening period: 18:00-20:00")
        print("✅ Night period: 20:00+")
        print("✅ Kulig gets +15 bonus at evening, +10 at night")
        print("✅ Kulig gets -50 penalty during day (afternoon/midday/morning)")
        print("✅ Evening/night POI compatible (+10 cross-period)")
        print("✅ Day POI at night: -30 to -50 penalty")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
