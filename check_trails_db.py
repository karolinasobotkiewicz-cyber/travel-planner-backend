"""
Check TrailDB database - verify trail durations
"""
import sys
sys.path.insert(0, 'c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.infrastructure.database import get_session
from app.infrastructure.database.models import TrailDB

def check_trail_durations():
    """Check trail durations in database."""
    session = next(get_session())
    
    print("="*80)
    print("TRAILDB DATABASE - Duration Check")
    print("="*80)
    
    # Query all trails
    trails = session.query(TrailDB).order_by(TrailDB.difficulty_level.desc(), TrailDB.trail_name).all()
    
    print(f"\nTotal trails in DB: {len(trails)}")
    print("\nTrail durations:")
    print("-"*80)
    
    problem_trails = []
    
    for trail in trails:
        time_min = trail.time_min
        time_max = trail.time_max
        time_min_h = time_min / 60
        time_max_h = time_max / 60
        
        # Check if duration suspiciously short (< 2 hours)
        is_problem = time_max < 120
        
        status = "⚠️ PROBLEM" if is_problem else "✅ OK"
        
        print(f"{status} | {trail.trail_name[:45]:45} | {trail.difficulty_level:10} | "
              f"{time_min:4}min ({time_min_h:4.1f}h) - {time_max:4}min ({time_max_h:4.1f}h)")
        
        if is_problem:
            problem_trails.append(trail)
    
    print("\n" + "="*80)
    print(f"SUMMARY: {len(problem_trails)} trails with duration < 2 hours")
    print("="*80)
    
    if problem_trails:
        print("\nProblem trails (duration too short):")
        for trail in problem_trails:
            print(f"  - {trail.trail_name}: {trail.time_min}-{trail.time_max} min "
                  f"({trail.difficulty_level})")
    
    session.close()
    
    return len(problem_trails) == 0


if __name__ == "__main__":
    success = check_trail_durations()
    sys.exit(0 if success else 1)
