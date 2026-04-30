"""
Test Critical Bug 2: Verify trail durations in generated plan
Generate Zakopane 2-day plan with trails and check if durations are correct
"""
import sys
import json
sys.path.insert(0, 'c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.application.services.plan_service import PlanService
from app.infrastructure.repositories.poi_repository import POIRepository
from app.infrastructure.repositories.restaurant_repository import RestaurantRepository
from app.infrastructure.repositories.trail_repository import TrailRepository

def test_trail_durations_in_plan():
    """Test that trails in generated plan have correct durations (not 60min)."""
    
    print("="*80)
    print("TEST: Trail Durations in Generated Plan")
    print("="*80)
    
    # Initialize repositories with proper paths
    zakopane_excel = "c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend\\data\\zakopane.xlsx"
    
    poi_repo = POIRepository(zakopane_excel)
    restaurant_repo = RestaurantRepository()
    trail_repo = TrailRepository()
    
    # Initialize service
    plan_service = PlanService(poi_repo, restaurant_repo, trail_repo)
    
    # Test request: Zakopane 2 days with mountain_trails preference
    request_data = {
        "city": "Zakopane",
        "days_count": 2,
        "target_group": "adventure_seekers",
        "budget_level": 2,
        "preferences": ["mountain_trails", "hiking", "nature", "outdoor"],
        "special_needs": []
    }
    
    print("\n📋 Request:")
    print(f"  Location: {request_data['city']}")
    print(f"  Days: {request_data['days_count']}")
    print(f"  Group: {request_data['target_group']}")
    print(f"  Preferences: {request_data['preferences']}")
    
    # Generate plan
    print("\n🔄 Generating plan...")
    result = plan_service.generate_plan(request_data)
    
    if not result.get("success"):
        print(f"\n❌ Plan generation failed: {result.get('error')}")
        return False
    
    plan = result.get("plan", {})
    days = plan.get("days", [])
    
    print(f"\n✅ Plan generated: {len(days)} days")
    
    # Find trails in plan
    trail_items = []
    
    for day_idx, day in enumerate(days, 1):
        items = day.get("items", [])
        for item in items:
            if item.get("type") == "attraction":
                # Check if this is a trail (has trail-specific fields)
                poi = item.get("poi", {})
                poi_type = poi.get("type", "")
                
                # Trail detection: has difficulty_level, elevation_gain, length_km
                if "difficulty_level" in poi or poi_type == "trail":
                    trail_items.append({
                        "day": day_idx,
                        "name": poi.get("name", "Unknown trail"),
                        "difficulty": poi.get("difficulty_level", "unknown"),
                        "duration_min": item.get("duration_min", 0),
                        "start_time": item.get("start_time"),
                        "end_time": item.get("end_time"),
                        "time_min": poi.get("time_min"),
                        "time_max": poi.get("time_max"),
                    })
    
    print(f"\n🏔️ Trails found in plan: {len(trail_items)}")
    print("-"*80)
    
    problem_trails = []
    
    for trail in trail_items:
        duration = trail["duration_min"]
        duration_h = duration / 60
        
        # Check if duration suspiciously short (< 120 min = 2h)
        is_problem = duration < 120
        
        status = "⚠️ PROBLEM" if is_problem else "✅ OK"
        
        print(f"{status} Day {trail['day']}: {trail['name'][:50]:50}")
        print(f"       Duration in plan: {duration} min ({duration_h:.1f}h)")
        print(f"       Time: {trail['start_time']} - {trail['end_time']}")
        print(f"       POI time_min/max: {trail['time_min']}/{trail['time_max']} min")
        print(f"       Difficulty: {trail['difficulty']}")
        print()
        
        if is_problem:
            problem_trails.append(trail)
    
    print("="*80)
    print(f"SUMMARY: {len(problem_trails)} trails with duration < 2 hours")
    print("="*80)
    
    if problem_trails:
        print("\n❌ PROBLEM TRAILS (duration too short):")
        for trail in problem_trails:
            print(f"  - Day {trail['day']}: {trail['name']} = {trail['duration_min']} min "
                  f"(expected: {trail['time_min']}-{trail['time_max']} min)")
        return False
    else:
        print("\n✅ All trails have realistic durations (>=2h)")
        return True


if __name__ == "__main__":
    success = test_trail_durations_in_plan()
    
    if success:
        print("\n" + "="*80)
        print("CRITICAL BUG 2 CHECK: ✅ PASSED - No trail duration problems found")
        print("="*80)
        sys.exit(0)
    else:
        print("\n" + "="*80)
        print("CRITICAL BUG 2 CHECK: ❌ FAILED - Trails have wrong durations in plan")
        print("="*80)
        sys.exit(1)
