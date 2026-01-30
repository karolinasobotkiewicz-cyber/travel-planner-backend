"""
Opening hours parser and validator.
NEW FORMAT (30.01.2026) - Client decision:
- opening_hours: JSON dict with weekdays {"mon": "08:00-16:00", "tue": "08:00-16:00", ...}
- opening_hours_seasonal: JSON dict {"date_from": "05-01", "date_to": "09-30"}

Validation logic:
1. Check seasonal (hard filter)
2. Check day of week
3. Check hours
"""
from typing import Optional, Tuple, Union, Dict, Any


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


def _time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    if not time_str or time_str.lower() in ["closed", "none", ""]:
        return None
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _parse_time_range(time_range: str) -> Optional[Tuple[int, int]]:
    """
    Parse time range string like "08:00-16:00" into (start_min, end_min).
    Returns None if closed or invalid.
    """
    if not time_range or time_range.lower() in ["closed", "none", ""]:
        return None
    
    if "-" not in time_range:
        return None
    
    try:
        start_str, end_str = time_range.split("-")
        start_min = _time_to_minutes(start_str.strip())
        end_min = _time_to_minutes(end_str.strip())
        
        if start_min is None or end_min is None:
            return None
        
        return (start_min, end_min)
    except (ValueError, AttributeError):
        return None


def parse_opening_hours_json(opening_hours: Union[Dict[str, str], str, None]) -> Dict[int, Tuple[int, int]]:
    """
    Parse opening_hours JSON dict into weekday_hours mapping.
    
    Args:
        opening_hours: {"mon": "08:00-16:00", "tue": "08:00-16:00", ..., "sun": "closed"}
    
    Returns:
        {0: (480, 960), 1: (480, 960), ...} - weekday index to (start_min, end_min)
        Empty dict {} if no hours or all closed
    
    Example:
        {"mon": "08:00-16:00", "sun": "closed"} → {0: (480, 960)}
    """
    weekday_hours = {}
    
    if not opening_hours:
        return weekday_hours
    
    # Handle string format (backward compatibility)
    if isinstance(opening_hours, str):
        # Empty or "closed" - return empty dict
        if not opening_hours.strip() or opening_hours.lower() == "closed":
            return weekday_hours
        # Old format - not supported anymore, return empty
        return weekday_hours
    
    # Handle dict format (new standard)
    if isinstance(opening_hours, dict):
        for day_name, time_range in opening_hours.items():
            day_name_lower = day_name.lower()
            
            if day_name_lower not in WEEKDAY_MAP:
                continue
            
            time_tuple = _parse_time_range(time_range)
            if time_tuple:
                day_index = WEEKDAY_MAP[day_name_lower]
                weekday_hours[day_index] = time_tuple
    
    return weekday_hours


def is_date_in_season(
    current_date: Tuple[int, int, int],
    seasonal: Optional[Union[Dict[str, str], str]]
) -> bool:
    """
    Check if current date is within seasonal range.
    
    Args:
        current_date: (year, month, day) tuple, e.g. (2026, 2, 15)
        seasonal: {"date_from": "05-01", "date_to": "09-30"} or None
    
    Returns:
        True if no seasonal restriction OR date is in season
        False if seasonal restriction exists AND date is outside season
    """
    if not seasonal:
        return True  # No seasonal restriction
    
    # Handle string format (backward compatibility)
    if isinstance(seasonal, str):
        # Empty or None - no restriction
        if not seasonal.strip() or seasonal.lower() in ["none", "null"]:
            return True
        # Old format - not supported, assume open
        return True
    
    # Handle dict format (new standard)
    if not isinstance(seasonal, dict):
        return True
    
    date_from = seasonal.get("date_from")
    date_to = seasonal.get("date_to")
    
    if not date_from or not date_to:
        return True  # No valid seasonal range
    
    year, month, day = current_date
    
    # Parse seasonal range
    try:
        from_month, from_day = map(int, date_from.split("-"))
        to_month, to_day = map(int, date_to.split("-"))
    except (ValueError, AttributeError):
        return True  # Invalid format - assume open
    
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
    opening_hours: Union[Dict[str, str], str, None],
    opening_hours_seasonal: Union[Dict[str, str], str, None],
    current_date: Tuple[int, int, int],
    weekday: int,
    start_time_minutes: int,
    duration_minutes: int
) -> bool:
    """
    Check if POI is open at given time.
    
    NEW FORMAT (30.01.2026):
    - opening_hours: JSON dict with weekdays
    - opening_hours_seasonal: JSON dict with date range
    
    Validation logic:
    1. Check seasonal (hard filter)
    2. Check day of week
    3. Check hours
    
    Args:
        opening_hours: {"mon": "08:00-16:00", ...} or None
        opening_hours_seasonal: {"date_from": "05-01", "date_to": "09-30"} or None
        current_date: (year, month, day) tuple
        weekday: 0=Monday, 6=Sunday
        start_time_minutes: Start time in minutes since midnight
        duration_minutes: Duration of visit
    
    Returns:
        True if POI is open and visit fits within hours
        False otherwise
    """
    # 1. Check seasonal restriction (hard filter)
    if not is_date_in_season(current_date, opening_hours_seasonal):
        return False
    
    # 2. Parse weekday hours
    weekday_hours = parse_opening_hours_json(opening_hours)
    
    # If no weekday hours specified, assume open all day
    if not weekday_hours:
        return True
    
    # 3. Check if POI open on this day of week
    if weekday not in weekday_hours:
        return False  # Closed on this day
    
    # 4. Check if visit fits within opening hours
    open_start, open_end = weekday_hours[weekday]
    visit_end = start_time_minutes + duration_minutes
    
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
