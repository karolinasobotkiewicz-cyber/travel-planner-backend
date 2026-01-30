"""
Opening hours parser and validator.
Handles various formats from zakopane.xlsx:
- Daily hours: "mon:9:00-17:00,tue:9:00-17:00,..."
- Seasonal dates: '"date_from": "06-01","date_to": "09-30",...'
- Single day: "Sat:15:30-18:00"
"""
import re
from typing import Optional, Tuple
from datetime import datetime


# Day of week mapping
WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def parse_opening_hours(opening_hours_str: str) -> dict:
    """
    Parse opening_hours string from Excel into structured format.
    
    Returns dict:
    {
        "seasonal": {"from": "06-01", "to": "09-30"} or None,
        "weekday_hours": {0: (540, 1020), 1: (540, 1020), ...} or {}
    }
    
    Examples:
    - "mon:9:00-17:00,tue:9:00-17:00" → weekday_hours only
    - '"date_from": "06-01","date_to": "09-30",mon:9:00-17:00' → both
    - "Sat:15:30-18:00" → weekday_hours only (Sat)
    """
    if not opening_hours_str or opening_hours_str.strip() == "":
        return {"seasonal": None, "weekday_hours": {}}
    
    result = {
        "seasonal": None,
        "weekday_hours": {}
    }
    
    # 1. Extract seasonal date range
    date_from_match = re.search(r'"date_from"\s*:\s*"(\d{2}-\d{2})"', opening_hours_str)
    date_to_match = re.search(r'"date_to"\s*:\s*"(\d{2}-\d{2})"', opening_hours_str)
    
    if date_from_match and date_to_match:
        result["seasonal"] = {
            "from": date_from_match.group(1),
            "to": date_to_match.group(1)
        }
    
    # 2. Extract weekday hours - pattern: mon:9:00-17:00 or Mon:9:00-17:00
    weekday_pattern = r'(mon|tue|wed|thu|fri|sat|sun):(\d{1,2}:\d{2})-(\d{1,2}:\d{2})'
    
    for match in re.finditer(weekday_pattern, opening_hours_str, re.IGNORECASE):
        day_name = match.group(1).lower()
        start_time = match.group(2)
        end_time = match.group(3)
        
        if day_name in WEEKDAY_MAP:
            day_index = WEEKDAY_MAP[day_name]
            result["weekday_hours"][day_index] = (
                _time_to_minutes(start_time),
                _time_to_minutes(end_time)
            )
    
    return result


def _time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def is_date_in_season(current_date: Tuple[int, int, int], seasonal: Optional[dict]) -> bool:
    """
    Check if current date (year, month, day) is within seasonal range.
    
    Args:
        current_date: (year, month, day) tuple, e.g. (2026, 2, 15)
        seasonal: {"from": "06-01", "to": "09-30"} or None
    
    Returns:
        True if no seasonal restriction OR date is in season
        False if seasonal restriction exists AND date is outside season
    """
    if not seasonal:
        return True  # No seasonal restriction
    
    year, month, day = current_date
    
    # Parse seasonal range
    from_month, from_day = map(int, seasonal["from"].split("-"))
    to_month, to_day = map(int, seasonal["to"].split("-"))
    
    # Convert to comparable tuples
    current = (month, day)
    season_from = (from_month, from_day)
    season_to = (to_month, to_day)
    
    # Handle year-crossing seasons (e.g., 12-01 to 03-31)
    if season_from <= season_to:
        # Normal season (e.g., 06-01 to 09-30)
        return season_from <= current <= season_to
    else:
        # Year-crossing season (e.g., 12-01 to 03-31)
        return current >= season_from or current <= season_to


def is_poi_open_at_time(
    opening_hours_str: str,
    current_date: Tuple[int, int, int],
    weekday: int,
    start_time_minutes: int,
    duration_minutes: int
) -> bool:
    """
    Check if POI is open at given time.
    
    Args:
        opening_hours_str: Raw opening_hours from Excel
        current_date: (year, month, day) tuple
        weekday: 0=Monday, 6=Sunday
        start_time_minutes: Start time in minutes since midnight (e.g., 540 = 09:00)
        duration_minutes: Duration of visit
    
    Returns:
        True if POI is open and visit fits within opening hours
        False otherwise
    """
    if not opening_hours_str or opening_hours_str.strip() == "":
        # No opening hours specified = assume always open
        return True
    
    parsed = parse_opening_hours(opening_hours_str)
    
    # 1. Check seasonal restriction (hard filter)
    if not is_date_in_season(current_date, parsed["seasonal"]):
        return False
    
    # 2. Check weekday hours
    if not parsed["weekday_hours"]:
        # No weekday hours specified = assume open all day
        return True
    
    if weekday not in parsed["weekday_hours"]:
        # POI not open on this day of week
        return False
    
    open_start, open_end = parsed["weekday_hours"][weekday]
    visit_end = start_time_minutes + duration_minutes
    
    # Check if visit fits within opening hours
    return start_time_minutes >= open_start and visit_end <= open_end


# =========================
# Unit tests
# =========================

if __name__ == "__main__":
    # Test 1: Muzeum Oscypka - tylko sobota 15:30-18:00
    oh1 = "Sat:15:30-18:00"
    parsed1 = parse_opening_hours(oh1)
    print("Test 1 - Muzeum Oscypka:")
    print(f"  Input: {oh1}")
    print(f"  Parsed: {parsed1}")
    print(f"  Saturday 16:00 for 1h: {is_poi_open_at_time(oh1, (2026, 2, 15), 5, 960, 60)}")  # Should be True
    print(f"  Sunday 16:00 for 1h: {is_poi_open_at_time(oh1, (2026, 2, 16), 6, 960, 60)}")  # Should be False
    print()
    
    # Test 2: Zjazd pontonem - czerwiec-wrzesień, różne godziny
    oh2 = '"date_from": "06-01","date_to": "09-30",mon:9:00-17:00,tue:9:00-17:00,wed:9:00-17:00,thu:9:00-17:00,fri:11:00-19:00,sat:11:00-19:00,sun:10:00-18:00,'
    parsed2 = parse_opening_hours(oh2)
    print("Test 2 - Zjazd pontonem:")
    print(f"  Seasonal: {parsed2['seasonal']}")
    print(f"  February 15 (Mon): {is_poi_open_at_time(oh2, (2026, 2, 15), 0, 540, 60)}")  # Should be False (off-season)
    print(f"  July 15 (Mon) 10:00: {is_poi_open_at_time(oh2, (2026, 7, 15), 0, 600, 60)}")  # Should be True
    print(f"  July 15 (Fri) 12:00: {is_poi_open_at_time(oh2, (2026, 7, 15), 4, 720, 60)}")  # Should be True
    print()
    
    # Test 3: Daily hours without seasonal
    oh3 = "mon:8:00-20:00,tue:8:00-20:00,wed: 8:00-20:00,thu:8:00-20:00,fri:8:00-20:00,sat: 8:00-20:00,sun:8:00-20:00,"
    parsed3 = parse_opening_hours(oh3)
    print("Test 3 - Daily hours:")
    print(f"  Seasonal: {parsed3['seasonal']}")
    print(f"  Monday 10:00: {is_poi_open_at_time(oh3, (2026, 2, 15), 0, 600, 120)}")  # Should be True
