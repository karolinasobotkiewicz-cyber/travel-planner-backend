"""
Test Critical Bug 3: realistic_timing badge validation
Verify that realistic_timing badge is NOT assigned when timeline has overlaps
"""
from datetime import datetime, timedelta

def test_realistic_timing_badge_validation():
    """Test that realistic_timing badge respects timeline integrity."""
    
    print("="*80)
    print("TEST: realistic_timing Badge Validation (Bug #3)")
    print("="*80)
    
    # Import quality_checker
    import sys
    sys.path.insert(0, 'c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')
    
    from app.domain.planner.quality_checker import validate_day_quality
    
    # Test Case 1: Day with NO overlaps (should get realistic_timing)
    clean_day = {
        "items": [
            {
                "type": "attraction",
                "poi_id": "poi1",
                "start_time": "09:00",
                "end_time": "10:30",
                "duration_min": 90
            },
            {
                "type": "lunch_break",
                "start_time": "12:00",
                "end_time": "13:30",
                "duration_min": 90
            },
            {
                "type": "attraction",
                "poi_id": "poi2",
                "start_time": "14:00",
                "end_time": "15:30",
                "duration_min": 90
            }
        ],
        "end_time": "20:00"
    }
    
    # Test Case 2: Day WITH overlaps (should NOT get realistic_timing)
    overlapping_day = {
        "items": [
            {
                "type": "attraction",
                "poi_id": "poi1",
                "start_time": "09:00",
                "end_time": "10:30",
                "duration_min": 90
            },
            {
                "type": "free_time",
                "start_time": "10:00",  # Overlaps with poi1!
                "end_time": "12:00",
                "duration_min": 120
            },
            {
                "type": "attraction",
                "poi_id": "poi2",
                "start_time": "11:00",  # Overlaps with free_time!
                "end_time": "12:30",
                "duration_min": 90
            }
        ],
        "end_time": "20:00"
    }
    
    # POI data (for enrichment)
    pois_data = [
        {
            "id": "poi1",
            "name": "Test POI 1",
            "type": "museum",
            "priorytet": 10
        },
        {
            "id": "poi2",
            "name": "Test POI 2",
            "type": "park",
            "priorytet": 8
        }
    ]
    
    print("\n📋 Test Case 1: Clean timeline (NO overlaps)")
    print("-" * 80)
    
    badges_clean = validate_day_quality(clean_day, pois_data)
    
    print(f"Badges assigned: {badges_clean}")
    
    has_realistic_timing_clean = "realistic_timing" in badges_clean
    print(f"realistic_timing assigned: {has_realistic_timing_clean}")
    
    if has_realistic_timing_clean:
        print("✅ CORRECT: realistic_timing assigned (no overlaps)")
    else:
        print("⚠️ UNEXPECTED: realistic_timing NOT assigned (but timeline clean?)")
    
    print("\n📋 Test Case 2: Overlapping timeline")
    print("-" * 80)
    
    badges_overlap = validate_day_quality(overlapping_day, pois_data)
    
    print(f"Badges assigned: {badges_overlap}")
    
    has_realistic_timing_overlap = "realistic_timing" in badges_overlap
    print(f"realistic_timing assigned: {has_realistic_timing_overlap}")
    
    if not has_realistic_timing_overlap:
        print("✅ CORRECT: realistic_timing NOT assigned (overlaps detected)")
    else:
        print("❌ BUG: realistic_timing assigned despite overlaps!")
    
    # Final result
    print("\n" + "="*80)
    print("TEST RESULT:")
    print("="*80)
    
    success = (
        has_realistic_timing_clean == True and 
        has_realistic_timing_overlap == False
    )
    
    if success:
        print("✅ SUCCESS: realistic_timing badge validation working correctly")
        print("   - Clean timeline → badge assigned ✓")
        print("   - Overlapping timeline → badge NOT assigned ✓")
        return True
    else:
        print("❌ FAILURE: realistic_timing badge validation not working")
        if not has_realistic_timing_clean:
            print("   - Clean timeline should get badge (currently doesn't)")
        if has_realistic_timing_overlap:
            print("   - Overlapping timeline should NOT get badge (currently does)")
        return False


if __name__ == "__main__":
    import sys
    success = test_realistic_timing_badge_validation()
    sys.exit(0 if success else 1)
