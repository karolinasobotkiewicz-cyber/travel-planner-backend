"""
Opening hours parser and validator.
NEW FORMAT (06.02.2026) - Multi-season support:
- opening_hours_seasonal: List of season dicts [{"date_from": "01-01", "date_to": "03-30", "mon": "08:00-16:00", ...}]
- Each season has its own opening hours for weekdays

OLD FORMAT (30.01.2026) - kept for backward compatibility:
- opening_hours: JSON dict with weekdays {"mon": "08:00-16:00", "tue": "08:00-16:00", ...}
- opening_hours_seasonal: JSON dict {"date_from": "05-01", "date_to": "09-30"}

Validation logic:
1. Find matching season (from list)
2. Check day of week
3. Check hours
"""
from typing import Optional, Tuple, Union, Dict, Any, List


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
    Parse time range string like "08:00-16:00" or single time "14:00" into (start_min, end_min).
    
    NEW (06.02.2026): Support single time format (e.g., "14:00" for shows/events)
    - Single time "14:00" → (840, 900) meaning 14:00-15:00 (1 hour slot)
    
    Returns None if closed or invalid.
    """
    if not time_range or time_range.lower() in ["closed", "none", ""]:
        return None
    
    time_range_clean = time_range.strip()
    
    # CLIENT DATA UPDATE (06.02.2026): Single time format support
    if "-" not in time_range_clean:
        # Single time format (e.g., "14:00" for show/event)
        # Treat as 1-hour slot: 14:00 becomes 14:00-15:00
        single_time = _time_to_minutes(time_range_clean)
        if single_time is None:
            return None
        return (single_time, single_time + 60)  # Add 1 hour
    
    # Range format (e.g., "08:00-16:00")
    try:
        start_str, end_str = time_range_clean.split("-")
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
    DEPRECATED - kept for backward compatibility.
    Use find_current_season() for new list format.
    
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


def find_current_season(
    current_date: Tuple[int, int, int],
    seasonal_list: Optional[List[Dict[str, str]]]
) -> Optional[Dict[str, str]]:
    """
    Find the season that matches current date from list of seasons.
    
    NEW FORMAT (06.02.2026): Multi-season support
    
    Args:
        current_date: (year, month, day) tuple, e.g. (2026, 2, 15)
        seasonal_list: [{"date_from": "01-01", "date_to": "03-30", "mon": "08:00-16:00", ...}, ...]
    
    Returns:
        Season dict with opening hours for matching season
        None if no matching season found or no seasons provided
    
    Example:
        current_date = (2026, 2, 15)  # February 15
        seasonal_list = [
            {"date_from": "01-01", "date_to": "03-30", "mon": "08:00-16:00"},
            {"date_from": "04-01", "date_to": "08-30", "mon": "07:00-20:00"}
        ]
        Returns: {"date_from": "01-01", "date_to": "03-30", "mon": "08:00-16:00"}
    """
    if not seasonal_list:
        return None
    
    year, month, day = current_date
    current = (month, day)
    
    for season in seasonal_list:
        date_from = season.get("date_from")
        date_to = season.get("date_to")
        
        if not date_from or not date_to:
            continue  # Skip invalid season
        
        try:
            from_month, from_day = map(int, date_from.split("-"))
            to_month, to_day = map(int, date_to.split("-"))
        except (ValueError, AttributeError):
            continue  # Skip invalid format
        
        season_from = (from_month, from_day)
        season_to = (to_month, to_day)
        
        # Check if current date is in this season
        if season_from <= season_to:
            # Normal season (e.g., 04-01 to 08-30)
            if season_from <= current <= season_to:
                return season
        else:
            # Year-crossing season (e.g., 12-01 to 03-31)
            if current >= season_from or current <= season_to:
                return season
    
    return None  # No matching season found


def is_poi_open_at_time(
    opening_hours: Union[Dict[str, str], str, None],
    opening_hours_seasonal: Union[List[Dict[str, str]], Dict[str, str], str, None],
    current_date: Tuple[int, int, int],
    weekday: int,
    start_time_minutes: int,
    duration_minutes: int
) -> bool:
    """
    Check if POI is open at given time.
    
    NEW FORMAT (06.02.2026): Multi-season support
    - opening_hours: DEPRECATED - kept for backward compatibility
    - opening_hours_seasonal: List[Dict] with seasons or single Dict (old format)
    
    Format examples:
    
    NEW (List of seasons):
    [
        {"date_from": "01-01", "date_to": "03-30", "mon": "08:00-16:00", "tue": "08:00-16:00", ...},
        {"date_from": "04-01", "date_to": "08-30", "mon": "07:00-20:00", "tue": "07:00-20:00", ...}
    ]
    
    OLD (Single season):
    {"date_from": "05-01", "date_to": "09-30", "opening_hours": {"mon": "08:00-16:00", ...}}
    
    Validation logic:
    1. Find matching season for current date
    2. Check if POI open on this day of week
    3. Check if visit fits within opening hours
    
    Args:
        opening_hours: DEPRECATED - old format, kept for backward compatibility
        opening_hours_seasonal: List[Dict] with seasons or Dict (old format) or None
        current_date: (year, month, day) tuple, e.g. (2026, 2, 15)
        weekday: 0=Monday, 6=Sunday
        start_time_minutes: Start time in minutes since midnight (e.g. 540 for 09:00)
        duration_minutes: Duration of visit (e.g. 60 for 1 hour)
    
    Returns:
        True if POI is open and visit fits within hours
        False otherwise
    """
    # CLIENT DATA UPDATE (06.02.2026): Multi-season support
    # Convert old format to new format for backward compatibility
    seasonal_list = None
    
    if isinstance(opening_hours_seasonal, list):
        # NEW format: List of seasons
        seasonal_list = opening_hours_seasonal
    elif isinstance(opening_hours_seasonal, dict):
        # OLD format: Single season dict - convert to list
        seasonal_list = [opening_hours_seasonal]
    elif opening_hours_seasonal is None:
        # No seasonal data
        seasonal_list = None
    else:
        # String or other - invalid format, assume closed
        return False
    
    # 1. Find matching season for current date
    current_season = find_current_season(current_date, seasonal_list)
    
    if current_season is None:
        # No matching season found - POI closed in this period
        return False
    
    # 2. Get opening hours from season dict
    # NEW format: hours directly in season dict (mon, tue, wed, ...)
    # OLD format: hours in nested "opening_hours" key
    
    weekday_hours_dict = None
    
    # Try NEW format first (hours directly in season)
    weekday_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    if any(day in current_season for day in weekday_names):
        # NEW format: hours in season dict
        weekday_hours_dict = current_season
    elif "opening_hours" in current_season:
        # OLD format: hours in nested dict
        weekday_hours_dict = current_season["opening_hours"]
    else:
        # Fallback to deprecated opening_hours parameter
        weekday_hours_dict = opening_hours if isinstance(opening_hours, dict) else None
    
    # Parse weekday hours
    weekday_hours = parse_opening_hours_json(weekday_hours_dict)
    
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
