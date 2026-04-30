"""
Debug: Check what _validate_and_fix_time_continuity returns for overlapping day
"""
import sys
sys.path.insert(0, 'c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import _validate_and_fix_time_continuity, DAY_END

# Overlapping day
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

print("Testing _validate_and_fix_time_continuity with overlapping day...")
print()

is_valid, issues, fixed_plan = _validate_and_fix_time_continuity(overlapping_day, "20:00")

print(f"is_valid: {is_valid}")
print(f"issues: {issues}")
print(f"Number of items in fixed_plan: {len(fixed_plan.get('items', []))}")
print()
print("Fixed plan items:")
for item in fixed_plan.get("items", []):
    print(f"  {item.get('type'):15} {item.get('start_time'):6} - {item.get('end_time'):6}")
print()

has_critical = any("OVERLAP" in i or "EXCEEDS" in i for i in issues)
print(f"has_critical_issues: {has_critical}")
