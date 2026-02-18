# type: ignore
import math
import random
from math import radians, sin, cos, sqrt, atan2

from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.domain.planner.opening_hours_parser import is_poi_open_at_time
from app.domain.scoring import (
    calculate_family_score,
    calculate_budget_score,
    calculate_premium_penalty,
    calculate_crowd_score,
    calculate_body_transition_score,
    get_next_body_state,
)
from app.domain.scoring.family_fit import should_exclude_by_target_group
from app.domain.scoring.intensity_scoring import should_exclude_by_intensity, calculate_intensity_score
from app.domain.scoring.preferences import calculate_preference_score, calculate_priority_bonus
from app.domain.scoring.travel_style import calculate_travel_style_score
from app.domain.scoring.space_scoring import calculate_space_score
from app.domain.scoring.weather_scoring import calculate_weather_dependency_score
from app.domain.scoring.type_matching import calculate_type_matching_score
from app.domain.scoring.time_of_day_scoring import calculate_time_of_day_score
from app.domain.scoring.tag_preferences import calculate_tag_preference_score  # CLIENT DATA UPDATE (05.02.2026)
from app.domain.filters.seasonality import filter_by_season

# =========================
# Helper Functions
# =========================

def is_core_poi(poi):
    """
    Check if POI is a core attraction.
    Core POI have priority_level = 12 (highest priority).
    CLIENT REQUIREMENT (08.02.2026): Used for core POI rotation logic.
    """
    try:
        return int(poi.get("priority_level", 0)) == 12
    except (ValueError, TypeError):
        return False


def _check_time_overlap(plan, new_start_time, new_end_time):
    """
    Check if new item overlaps with existing items in plan.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2):
    Validate time continuity - no overlapping events.
    
    Args:
        plan: List of plan items (dicts with start_time/end_time)
        new_start_time: Start time string "HH:MM"
        new_end_time: End time string "HH:MM"
    
    Returns:
        tuple: (overlaps: bool, conflicting_item: dict or None)
    """
    new_start_min = time_to_minutes(new_start_time)
    new_end_min = time_to_minutes(new_end_time)
    
    for item in plan:
        # Skip items without time range (e.g., accommodation_start)
        if "start_time" not in item or "end_time" not in item:
            continue
        
        item_start_min = time_to_minutes(item["start_time"])
        item_end_min = time_to_minutes(item["end_time"])
        
        # Check overlap: new starts before existing ends AND new ends after existing starts
        if new_start_min < item_end_min and new_end_min > item_start_min:
            return True, item
    
    return False, None


def _add_buffer_item(plan, now, buffer_type, duration_min, reason_context=None, day_end=None):
    """
    Add a buffer item to explain time gaps in the plan.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4):
    Client requirement: "Oś czasu ma dziury, które nie są opisane"
    Solution: Add explicit buffer items for parking_walk, tickets_queue, restroom, photo_stop
    
    BUGFIX (17.02.2026): Added day_end parameter to prevent buffers from exceeding day_end
    
    Args:
        plan: List of plan items
        now: Current time in minutes from midnight
        buffer_type: Type of buffer ("parking_walk", "tickets_queue", "restroom", "photo_stop", "traffic_margin")
        duration_min: Duration of buffer in minutes
        reason_context: Optional context dict (poi_name, etc.)
        day_end: Optional day_end in minutes - if buffer would exceed, skip or shorten it
    
    Returns:
        Updated time (now + duration_min) or now if buffer skipped
    
    Buffer Types:
    - parking_walk: 5-15 min (walking from parking to attraction entrance)
    - tickets_queue: 5-20 min (waiting in line at popular attractions)
    - restroom: 5-10 min (bathroom break after long attractions)
    - photo_stop: 5-15 min (photo opportunity at scenic locations)
    - traffic_margin: 5-10 min (buffer for unexpected delays)
    """
    if duration_min <= 0:
        return now
    
    # BUGFIX (17.02.2026): Check if buffer would exceed day_end
    if day_end is not None and now + duration_min > day_end:
        # Calculate remaining time
        remaining = day_end - now
        if remaining <= 0:
            # No time left - skip buffer
            print(f"[SKIP BUFFER] {buffer_type} would exceed day_end ({minutes_to_time(now)} + {duration_min}min > {minutes_to_time(day_end)})")
            return now
        elif remaining < duration_min:
            # Shorten buffer to fit remaining time
            print(f"[SHORTEN BUFFER] {buffer_type} shortened from {duration_min} to {remaining}min to fit day_end")
            duration_min = remaining
    
    buffer_start = minutes_to_time(now)
    buffer_end = minutes_to_time(now + duration_min)
    
    # Check overlap before adding
    overlaps, conflict = _check_time_overlap(plan, buffer_start, buffer_end)
    if overlaps:
        print(f"[SKIP BUFFER] {buffer_type} {buffer_start}-{buffer_end} overlaps with {conflict.get('type')}")
        return now  # Don't add buffer if it creates overlap
    
    # Generate description based on buffer type
    descriptions = {
        "parking_walk": f"Przejscie z parkingu ({duration_min} min)",
        "tickets_queue": f"Oczekiwanie w kolejce ({duration_min} min)",
        "restroom": f"Przerwa sanitarna ({duration_min} min)",
        "photo_stop": f"Sesja zdjęciowa ({duration_min} min)",
        "traffic_margin": f"Margines na nieprzewidziane opoznienia ({duration_min} min)",
    }
    
    description = descriptions.get(buffer_type, f"Buffer: {buffer_type} ({duration_min} min)")
    
    # Add context to description if provided
    if reason_context:
        poi_name = reason_context.get("poi_name")
        if poi_name and buffer_type in ["parking_walk", "tickets_queue"]:
            # Remove Polish characters from POI name for Windows terminal compatibility
            poi_name_safe = poi_name.encode('ascii', errors='ignore').decode('ascii')
            description = f"{description} - {poi_name_safe}"
    
    buffer_item = {
        "type": "buffer",
        "buffer_type": buffer_type,
        "start_time": buffer_start,
        "end_time": buffer_end,
        "duration_min": duration_min,
        "description": description,
    }
    
    plan.append(buffer_item)
    print(f"[BUFFER ADDED] {buffer_type} at {buffer_start}-{buffer_end}: {description.encode('ascii', errors='ignore').decode('ascii')}")
    
    return now + duration_min


def _validate_and_fix_time_continuity(plan, day_end_str):
    """
    Validate time continuity in plan and fix issues.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #7):
    Client requirement: "Generator powinien automatycznie sprawdzać ciągłość czasu"
    
    Validates:
    1. No unexplained gaps >10 min between items
    2. No overlapping events
    3. All items within day boundaries (day_start → day_end)
    4. If last item ends before day_end with gap >30 min, add free_time
    
    Args:
        plan: List of plan items
        day_end_str: End time string "HH:MM"
    
    Returns:
        tuple: (is_valid: bool, issues: list of strings, fixed_plan: list)
    """
    issues = []
    fixed_plan = list(plan)  # Copy plan for modifications
    
    # Get day_end in minutes
    day_end_min = time_to_minutes(day_end_str)
    
    # Find items with time ranges (skip accommodation_start/end)
    timed_items = []
    for item in fixed_plan:
        if "start_time" in item and "end_time" in item:
            item_copy = dict(item)
            item_copy["start_min"] = time_to_minutes(item["start_time"])
            item_copy["end_min"] = time_to_minutes(item["end_time"])
            timed_items.append(item_copy)
    
    if not timed_items:
        return True, [], fixed_plan  # Empty plan is valid
    
    # Sort by start time
    timed_items.sort(key=lambda x: x["start_min"])
    
    # Check 1: Gaps between consecutive items
    for i in range(len(timed_items) - 1):
        current = timed_items[i]
        next_item = timed_items[i + 1]
        
        gap = next_item["start_min"] - current["end_min"]
        
        if gap > 10:
            # Large gap detected
            gap_start = minutes_to_time(current["end_min"])
            gap_end = minutes_to_time(next_item["start_min"])
            issues.append(
                f"GAP: {gap} min between {current.get('type')} (ends {current['end_time']}) "
                f"and {next_item.get('type')} (starts {next_item['start_time']})"
            )
            print(f"[TIME CONTINUITY] WARNING: {gap} min gap {gap_start}-{gap_end}")
        
        elif gap < 0:
            # Overlap detected
            issues.append(
                f"OVERLAP: {current.get('type')} (ends {current['end_time']}) "
                f"overlaps with {next_item.get('type')} (starts {next_item['start_time']})"
            )
            print(f"[TIME CONTINUITY] ERROR: Overlap detected!")
    
    # Check 2: Last item vs day_end
    last_item = timed_items[-1]
    gap_to_day_end = day_end_min - last_item["end_min"]
    
    if gap_to_day_end > 30:
        # Significant time left until day_end - add free_time
        free_start = last_item["end_time"]
        free_end = day_end_str
        free_duration = gap_to_day_end
        
        # Check if free_time doesn't overlap with existing items
        overlaps, _ = _check_time_overlap(fixed_plan, free_start, free_end)
        
        if not overlaps:
            free_time_item = {
                "type": "free_time",
                "start_time": free_start,
                "end_time": free_end,
                "duration_min": free_duration,
                "description": f"Czas wolny do konca dnia: kolacja, spacer, zakupy ({free_duration} min)"
            }
            
            # Insert before accommodation_end (last item in plan)
            insert_index = len(fixed_plan) - 1
            fixed_plan.insert(insert_index, free_time_item)
            
            print(f"[TIME CONTINUITY] Auto-added free_time {free_start}-{free_end} ({free_duration} min) to fill gap to day_end")
        else:
            issues.append(f"GAP TO DAY_END: {gap_to_day_end} min after last activity (cannot add free_time - overlap)")
    
    elif gap_to_day_end < -10:
        # Last item exceeds day_end
        issues.append(
            f"EXCEEDS DAY_END: Last item ends at {last_item['end_time']}, "
            f"but day_end is {day_end_str} ({abs(gap_to_day_end)} min over)"
        )
        print(f"[TIME CONTINUITY] WARNING: Plan exceeds day_end by {abs(gap_to_day_end)} min")
    
    # Validation result
    is_valid = len([i for i in issues if "OVERLAP" in i or "EXCEEDS" in i]) == 0
    
    return is_valid, issues, fixed_plan


# =========================
# Config
# =========================

DAY_START = "09:00"
DAY_END = "19:00"

LUNCH_TARGET = "13:00"
LUNCH_EARLIEST = "12:00"
LUNCH_LATEST = "14:30"
LUNCH_DURATION_MIN = 40

DINNER_TARGET = "19:00"
DINNER_EARLIEST = "18:00"
DINNER_LATEST = "20:00"
DINNER_DURATION_MIN = 90

MIN_TRANSFER_MIN = 5

GROUP_LIMITS = {
    "solo": 5,
    "couples": 5,
    "friends": 6,
    "family_kids": 8,
    "seniors": 5,
}

GROUP_DAILY_ENERGY = {
    "solo": 70,
    "couples": 65,
    "friends": 75,
    "family_kids": 90,
    "seniors": 55,
}

# FIX #7 (02.02.2026): Attraction limits per target_group
# Client requirements:
# - family_kids: 4-6 attractions (max 7), 1-2 core, 2-3 light, 1 long
# - seniors: 3-5 attractions (max 5), 1 must-see, 2-3 calm
# - solo: 5-7 attractions (max 8), 2 core, 3-4 secondary
# - couples: 5-6 attractions (max 6), 1-2 must-see, 2-3 scenic
# - friends: 6-8 attractions (max 8), 2 core, 3-4 active, 1-2 evening
GROUP_ATTRACTION_LIMITS = {
    "family_kids": {
        "soft": 6,  # Start penalty after 6
        "hard": 7,  # Absolute max
        "core_min": 1,  # Minimum core POI
        "core_max": 2,  # Maximum core POI
    },
    "seniors": {
        "soft": 5,
        "hard": 5,  # Hard stop at 5
        "core_min": 1,
        "core_max": 1,
    },
    "solo": {
        "soft": 7,
        "hard": 8,
        "core_min": 2,
        "core_max": 2,
    },
    "couples": {
        "soft": 6,
        "hard": 6,
        "core_min": 1,
        "core_max": 2,
    },
    "friends": {
        "soft": 8,
        "hard": 8,
        "core_min": 2,
        "core_max": 2,
    },
}


# =========================
# Safe casting
# =========================


def _is_nan(x):
    try:
        return isinstance(x, float) and math.isnan(x)
    except (TypeError, ValueError):
        return False


def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if _is_nan(x):
            return default
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return default
        return float(s)
    except (TypeError, ValueError):
        return default


def is_kids_focused_poi(poi):
    """
    Check if POI is kids-focused (target_groups + tags analysis).
    
    CLIENT REQUIREMENT (04.02.2026): Kids-focused POI should have daily limit
    for non-family groups (max 1 per day).
    
    UAT FIX (18.02.2026 - Problem #2): Enhanced detection via tags
    - Original logic: ONLY family_kids in target_groups
    - New logic: Also check for kids-related tags
    
    Args:
        poi: POI dict
        
    Returns:
        bool: True if POI is kids-focused
    """
    # Method 1: ONLY family_kids in target_groups (strictest)
    target_groups = poi.get("target_groups") or []
    if target_groups:
        tg = set([str(x).strip().lower() for x in target_groups])
        if len(tg) == 1 and "family_kids" in tg:
            return True
    
    # Method 2: UAT FIX - Check for kids-specific tags
    # If POI has multiple kids-related tags → likely kids-focused
    poi_tags = poi.get("tags") or []
    tags_str = ",".join([str(t).lower() for t in poi_tags])
    
    kids_indicators = [
        "kids", "children", "playground", "interactive_exhibition_kids",
        "petting_zoo", "farm_animals", "feeding_experience",
        "miniature_world", "fairytale_world", "illusion_kids",
        "aquatic_playground", "adventure_playground", "trampoline_park",
        "family_entertainment_kids", "zoo", "aquarium_kids"
    ]
    
    kids_tag_count = sum(1 for indicator in kids_indicators if indicator in tags_str)
    
    # If POI has 2+ kids indicators → treat as kids-focused
    if kids_tag_count >= 2:
        return True
    
    # Method 3: UAT FIX - Check POI name for obvious kids attractions
    poi_name = str(poi.get("name", "")).lower()
    name_indicators = [
        "mini zoo", "podwodny świat", "dom do góry nogami",
        "myszogród", "playground", "kids park", "children"
    ]
    
    for indicator in name_indicators:
        if indicator in poi_name:
            return True
    
    return False


def is_termy_spa(poi):
    """
    Check if POI is a termy/spa/thermal bath.
    
    BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9):
    Max 1 termy/spa per day for seniors to avoid exhaustion.
    
    Args:
        poi: POI dict
        
    Returns:
        bool: True if POI is termy/spa/thermal bath
    """
    name = safe_str(poi.get("name", ""))
    poi_type = safe_str(poi.get("type", ""))
    tags = poi.get("tags") or []
    tags_str = ",".join([safe_str(x) for x in tags]) if tags else ""
    
    # Check name, type, or tags for termy/spa/thermal keywords
    return (
        any(keyword in name for keyword in ["termy", "spa", "thermal", "basen termalny", "sauna"]) or
        any(keyword in poi_type for keyword in ["termy", "spa", "thermal", "wellness"]) or
        any(keyword in tags_str for keyword in ["relax", "spa", "thermal", "wellness"])
    )


def safe_int(x, default=0):
    return int(round(safe_float(x, default)))


def safe_str(x):
    return str(x).strip().lower() if x is not None else ""


# =========================
# Geo helpers
# =========================


def distance_km(a, b):
    R = 6371
    lat1, lon1 = math.radians(a["lat"]), math.radians(a["lng"])
    lat2, lon2 = math.radians(b["lat"]), math.radians(b["lng"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    x = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(x))


def travel_time_minutes(a, b, context):
    """Calculate travel time between two POIs using haversine distance and realistic driving speeds."""
    if not a or not b:
        return 0
    
    # Use haversine distance calculation for accurate GPS-based distance
    has_car = context.get("has_car", True)
    if not has_car:
        return 0
    
    lat1, lng1 = a.get("lat"), a.get("lng")
    lat2, lng2 = b.get("lat"), b.get("lng")
    
    if not all([lat1, lng1, lat2, lng2]):
        return 10  # fallback minimum
    
    distance_km = haversine_distance(lat1, lng1, lat2, lng2)
    
    # Mountain roads: 45 km/h average + 5 min parking/finding spot
    drive_time = (distance_km / 45) * 60 + 5
    return max(int(drive_time), 10)  # minimum 10 minutes


# =========================
# Context helpers
# =========================


def _get_context(context):
    if not isinstance(context, dict):
        context = {}

    season = safe_str(context.get("season")) or None
    region_type = safe_str(context.get("region_type")) or None
    weather = context.get("weather") or {}

    return {
        "season": season,
        "region_type": region_type,
        "temp": safe_float(weather.get("temp"), 15),
        "precip": bool(weather.get("precip", False)),
        "wind": safe_float(weather.get("wind"), 0),
        "transport": safe_str(context.get("transport")) or "car",
        "daylight_end": context.get("daylight_end"),
        "date": context.get("date"),  # CRITICAL FIX: Add date for opening_hours validation
    }


# =========================
# Distance calculation
# =========================


def haversine_distance(lat1, lng1, lat2, lng2):
    """
    Calculate distance in km between two GPS points using Haversine formula.
    """
    R = 6371  # Earth radius in km
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c


def calculate_drive_time(poi_from, poi_to, has_car=True):
    """
    Calculate driving time between two POIs in minutes.
    
    Args:
        poi_from: POI dict with lat/lng
        poi_to: POI dict with lat/lng
        has_car: Whether user has car
    
    Returns:
        Driving time in minutes (minimum 10 min for nearby, +5 for parking)
    """
    if not has_car:
        return 0
    
    lat1 = poi_from.get('lat')
    lng1 = poi_from.get('lng')
    lat2 = poi_to.get('lat')
    lng2 = poi_to.get('lng')
    
    if not all([lat1, lng1, lat2, lng2]):
        return 10  # Default if no coordinates
    
    distance_km = haversine_distance(lat1, lng1, lat2, lng2)
    
    # 45 km/h average speed in mountains + 5 min parking
    drive_time = (distance_km / 45) * 60 + 5
    
    return max(int(drive_time), 10)  # Minimum 10 min


# =========================
# POI helpers
# =========================


def poi_id(p):
    return p.get("id", "")


def poi_name(p):
    return p.get("name", "Unnamed")


def is_culture(p):
    t = safe_str(p.get("type"))
    return any(
        k in t
        for k in [
            "museum",
            "muzeum",
            "gallery",
            "galeria",
            "exhibition",
            "wystaw",
        ]
    )


def is_finale(p):
    return p.get("experience_role") == "finale"


# =========================
# Opening hours
# =========================


def is_open(p, now, duration, season, context=None):
    """
    Check if POI is open at given time.
    
    NEW FORMAT (30.01.2026) - Uses opening_hours_parser to validate:
    - opening_hours: JSON dict {"mon": "08:00-16:00", ...}
    - opening_hours_seasonal: JSON dict {"date_from": "05-01", "date_to": "09-30"}
    
    Args:
        p: POI dict with "opening_hours" and "opening_hours_seasonal" fields
        now: Start time in minutes since midnight
        duration: Visit duration in minutes
        season: Season string (unused, kept for compatibility)
        context: Context dict with "date" = (year, month, day, weekday)
    
    Returns:
        True if POI is open and visit fits within hours
        False otherwise (including off-season)
    """
    oh = p.get("opening_hours")
    oh_seasonal = p.get("opening_hours_seasonal")
    
    # If no opening_hours specified, assume always open
    if not oh:
        return True
    
    # Extract date info from context
    if not context or "date" not in context:
        # No date context - use legacy simple validation
        day_start = time_to_minutes("09:00")
        day_end = time_to_minutes("20:00")
        return (now >= day_start) and (now < day_end)
    
    # Parse context date - handle datetime objects, tuples, and strings
    date_obj = context["date"]
    if hasattr(date_obj, 'year'):
        # It's a datetime object
        year, month, day = date_obj.year, date_obj.month, date_obj.day
        weekday = date_obj.weekday()
    elif isinstance(date_obj, str):
        # It's a string "YYYY-MM-DD"
        from datetime import datetime
        dt = datetime.strptime(date_obj, "%Y-%m-%d")
        year, month, day = dt.year, dt.month, dt.day
        weekday = dt.weekday()
    else:
        # It's a tuple (year, month, day, weekday)
        year, month, day, weekday = date_obj
    
    current_date = (year, month, day)
    
    # Use opening_hours_parser for proper validation
    return is_poi_open_at_time(
        opening_hours=oh,
        opening_hours_seasonal=oh_seasonal,
        current_date=current_date,
        weekday=weekday,
        start_time_minutes=now,
        duration_minutes=duration
    )


# =========================
# Energy
# =========================


def energy_cost(p, duration, context):
    base = max(15, duration) / 10
    if p.get("intensity") == "high":
        base *= 1.5
    if p.get("space") == "outdoor":
        base *= 1.2
    if _get_context(context)["region_type"] == "mountain":
        base *= 1.2
    return base


# =========================
# Duration
# =========================


def choose_duration(p, now, end, lunch_done):
    tmin = safe_int(p.get("time_min"), 30)
    tmax = safe_int(p.get("time_max"), 60)

    if end - now < tmin:
        return 0

    lunch_target = time_to_minutes(LUNCH_TARGET)
    lunch_latest = time_to_minutes(LUNCH_LATEST)

    # jesli lunch nie zrobiony, sprawdź czy POI zmieści tmin przed lunchem
    if not lunch_done and now < lunch_latest:
        max_before_lunch = (
            lunch_target - now if now < lunch_target else lunch_latest - now
        )
        # BLOCK POI jeśli jego tmin przekroczyłby lunch
        if max_before_lunch < tmin:
            return 0

    # Wybierz rozsądny duration: około 70% zakresu (tmin → tmax)
    # Przykład: tmin=60, tmax=150 → preferred = 60 + 0.7*(90) = 123
    # To daje bardziej realistyczne czasy niż zawsze max
    preferred_duration = tmin + int(0.7 * (tmax - tmin))
    
    return min(preferred_duration, end - now)


# =========================
# Scoring
# =========================


def score_poi(
    p,
    user,
    fatigue,
    used,
    now,
    energy_left,
    context,
    culture_streak,
    body_state,
    finale_done,
):
    score = 0.0

    # UAT FIX (18.02.2026 - Problem #10): Must_see conditional scoring
    # Tests 03, 06, 07, 08, 09: Wielka Krokiew appears in every plan
    # Problem: must_see * 2.0 bonus (20 points for Krokiew) dominates all other scoring
    # Solution: Full bonus only when POI matches user preferences
    # This keeps must_see important but not overwhelming when user wants different experiences
    
    # First calculate if POI matches user preferences (check tag bonus)
    user_preferences = user.get("preferences", [])
    poi_matches_preferences = False
    tag_bonus = 0
    
    if user_preferences:
        # Calculate tag-based preference bonus
        tag_bonus = calculate_tag_preference_score(p, user_preferences)
        poi_matches_preferences = (tag_bonus > 0)
    
    # Apply conditional must_see bonus
    must_see_value = safe_float(p.get("must_see"))
    if poi_matches_preferences or not user_preferences:
        # Full bonus when: preferences match OR user has no preferences
        score += must_see_value * 2.0
    else:
        # Reduced bonus when: user has preferences but POI doesn't match
        score += must_see_value * 1.0  # 50% reduction
        if must_see_value > 5:  # Log for high must_see POI
            poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
            print(f"    [MUST_SEE REDUCED] {poi_name_safe}: {must_see_value * 1.0:.1f} (no preference match, user wants: {user_preferences})")
    
    score += safe_float(p.get("priority"))

    # dopasowanie - existing modules
    score += calculate_family_score(p, user)
    score += calculate_budget_score(p, user)
    score += calculate_premium_penalty(p, user)  # CLIENT REQUIREMENT (08.02.2026): Premium experience penalty at budget/standard levels
    score += calculate_crowd_score(p, user, current_time_minutes=now)  # Added current_time for peak_hours
    
    # UAT FIX (18.02.2026 - Problem #3): Popularity penalty for low crowd_tolerance
    # Tests 02, 04, 05, 06: crowd_tolerance=1 users get top magnets (Morskie Oko, Krupówki, Krokiew)
    # Solution: Additional penalty for popular POI (popularity_score >= 7) + low tolerance (0-1)
    popularity = safe_float(p.get("popularity_score", 0), 0)
    crowd_tolerance = safe_int(user.get("crowd_tolerance", 1), 1)
    
    if popularity >= 7 and crowd_tolerance <= 1:
        # Strong penalty for popular attractions when user has low crowd tolerance
        penalty = -15.0
        score += penalty
        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
        print(f"    [POPULARITY PENALTY] {poi_name_safe}: {penalty} (popularity={popularity:.1f}, tolerance={crowd_tolerance})")

    # ETAP 1 ROZSZERZONY - preferences + travel_style
    score += calculate_preference_score(p, user)
    score += calculate_travel_style_score(p, user)
    
    # FIX #6 (02.02.2026): Priority_level bonus (core: +25, secondary: +10, optional: 0)
    score += calculate_priority_bonus(p, user)
    
    # FEEDBACK KLIENTKI (03.02.2026): Intensity soft scoring
    score += calculate_intensity_score(p, user)
    
    # CLIENT DATA UPDATE (05.02.2026): Tag-based preference scoring
    # NOTE: tag_bonus already calculated above in must_see conditional logic
    # Add the bonus to score here with logging
    if tag_bonus > 0:
        score += tag_bonus
        # ASCII-safe print for Windows terminal (polish characters)
        poi_name_safe = str(p.get('name', 'Unknown')).encode('ascii', errors='ignore').decode('ascii')
        print(f"    [TAG BONUS] {poi_name_safe}: +{tag_bonus} from preferences {user_preferences}")
    
    # ETAP 1 ENHANCEMENT (29.01.2026) - New scoring modules
    score += calculate_space_score(p, user, context)  # indoor/outdoor vs weather
    score += calculate_weather_dependency_score(p, user, context)  # weather dependency
    score += calculate_type_matching_score(p, user, context)  # type + group/style matching
    score += calculate_time_of_day_score(p, user, context, now)  # recommended_time_of_day

    # POI ROLE LOGIC
    role = p.get("poi_role", "FILLER")

    # prime time dnia (10:00–15:00)
    if 600 <= now <= 900:
        if role == "FILLER":
            score -= 15.0
        if role == "BUFFER":
            score -= 5.0
        if role == "RELAX":
            score += 6.0

    # po 15:00 chcemy RELAX albo FINALE
    if now >= 900:
        if role == "RELAX":
            score += 10.0
        if role == "FILLER":
            score -= 10.0

    # zmeczenie
    score -= float(fatigue)

    ctx = _get_context(context)

    # pogoda: deszcz + outdoor
    if ctx["precip"] and p.get("space") == "outdoor":
        score -= 5.0

    # kara za kulture z rzedu
    if is_culture(p) and culture_streak >= 2:
        score -= 20.0

    # body state transitions
    score += calculate_body_transition_score(p, body_state)

    # RELAX kiedy cialo tego potrzebuje
    if body_state == "cold" and role == "RELAX":
        score += 12.0

    if body_state == "warm" and role == "BUFFER":
        score += 4.0

    # final dnia
    if is_finale(p):
        if finale_done:
            score -= 100.0  # nie dokladamy drugiego finalu
        else:
            if now >= time_to_minutes("15:00"):
                score += 18.0
            else:
                score -= 25.0  # przed 15:00 final nie ma sensu

    return score


# =========================
# Multi-day Planner
# =========================


def plan_multiple_days(pois, user, contexts, day_start, day_end):
    """
    Build multi-day plan with cross-day POI tracking and core POI distribution.
    
    ETAP 2 - DAY 3 (15.02.2026): Multi-day planning core.
    
    Key features:
    - Cross-day POI tracking: No duplicate POIs across days
    - Core POI distribution: Spread core attractions across days (not all on Day 1)
    - Day-to-day energy continuity: Reset energy each day but track usage patterns
    
    Args:
        pois: List of POI dicts
        user: User dict (preferences, target_group, etc.)
        contexts: List of context dicts (one per day - season, date, weather, etc.)
        day_start: Start time string "HH:MM"
        day_end: End time string "HH:MM"
    
    Returns:
        List of day plans (list of dicts, one per day)
    """
    num_days = len(contexts)
    
    # Global tracking across ALL days
    global_used_pois = set()
    
    # UAT FIX (18.02.2026 - Problem #6): Track termy/spa count across all days
    # Test 08: 5 termy in 7 days is too much
    # Limit: max 2-3 termy in 7+ day plans (1 termy per 2-3 days)
    max_termy_total = max(2, num_days // 3)  # 2-day: 2 termy, 3-day: 2, 5-day: 2, 7-day: 3
    global_termy_tracking = {"count": 0, "max": max_termy_total}
    
    print(f"[MULTI-DAY] Termy limit for {num_days} days: max {max_termy_total} total")
    
    # Core POI distribution strategy
    # Get all core POIs (priority_level == 12)
    core_pois = [p for p in pois if is_core_poi(p)]
    
    print(f"[MULTI-DAY] Planning {num_days} days with {len(core_pois)} core POIs available")
    print(f"[MULTI-DAY] Core POI IDs: {[p.get('poi_id', 'unknown') for p in core_pois]}")
    
    # Get core limits for this target group
    target_group = user.get("target_group", "solo")
    limits = GROUP_ATTRACTION_LIMITS.get(target_group, {
        "soft": 7,
        "hard": 8,
        "core_min": 1,
        "core_max": 2,
    })
    
    # Calculate core POIs to distribute
    # Each day wants core_min (usually 1), but we have limited core POIs
    # Distribute fairly: min(total_core_pois, num_days * core_min)
    total_core_needed = num_days * limits.get("core_min", 1)
    total_core_available = len(core_pois)
    
    # If we have more core POIs than needed, great!
    # If we have fewer, distribute what we have
    cores_to_distribute = min(total_core_available, total_core_needed)
    
    print(f"[MULTI-DAY] Distributing {cores_to_distribute} core POIs across {num_days} days (need {total_core_needed}, have {total_core_available})")
    
    # Build each day with cross-day tracking
    all_day_plans = []
    
    for day_num in range(num_days):
        context = contexts[day_num]
        
        print(f"\n[MULTI-DAY] === Building Day {day_num + 1}/{num_days} ===")
        print(f"[MULTI-DAY] Global used POIs so far: {len(global_used_pois)}")
        
        # Build day with global tracking
        # The global_used set will be updated inside build_day()
        # UAT FIX (18.02.2026 - Problem #6): Pass termy tracking dict
        day_plan = build_day(
            pois=pois,
            user=user,
            context=context,
            day_start=day_start,
            day_end=day_end,
            global_used=global_used_pois,  # Pass reference to global set
            global_termy_tracking=global_termy_tracking  # Pass termy limit tracker
        )
        
        # Count POIs used in this day
        day_poi_count = 0
        day_core_count = 0
        for item in day_plan:
            if item.get("type") == "attraction" and item.get("poi"):
                day_poi_count += 1
                if is_core_poi(item["poi"]):
                    day_core_count += 1
        
        print(f"[MULTI-DAY] Day {day_num + 1} complete: {day_poi_count} POIs ({day_core_count} core)")
        print(f"[MULTI-DAY] Global used POIs after Day {day_num + 1}: {len(global_used_pois)}")
        print(f"[MULTI-DAY] Global termy count after Day {day_num + 1}: {global_termy_tracking['count']}/{global_termy_tracking['max']}")
        
        all_day_plans.append(day_plan)
    
    return all_day_plans


# =========================
# Single-day Planner
# =========================


def build_day(pois, user, context, day_start=None, day_end=None, global_used=None, global_termy_tracking=None):
    """
    Build daily plan from POIs.
    
    Args:
        pois: List of POI dicts
        user: User dict (preferences, target_group, etc.)
        context: Context dict (season, date, weather, etc.)
        day_start: Start time string "HH:MM" (default: DAY_START global)
        day_end: End time string "HH:MM" (default: DAY_END global)
        global_used: Optional set of POI IDs already used in previous days (for multi-day planning)
        global_termy_tracking: Optional dict {"count": int, "max": int} for tracking termy/spa across all days
    """
    ctx = _get_context(context)
    
    # SEASONALITY HARD FILTER (ETAP 1 enhancement - 29.01.2026)
    # Exclude POI outside current season BEFORE scoring
    current_date = context.get("date")
    if current_date:
        pois = filter_by_season(pois, current_date)

    # Use user-provided times or fallback to global defaults
    start_time_str = day_start or DAY_START
    end_time_str = day_end or DAY_END
    
    now = time_to_minutes(start_time_str)
    end = time_to_minutes(end_time_str)

    if ctx["daylight_end"]:
        end = min(end, time_to_minutes(ctx["daylight_end"]))

    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #10):
    # Standardize all items to use start_time/end_time (not "time")
    plan = [{
        "type": "accommodation_start",
        "start_time": start_time_str,
        "end_time": start_time_str  # Point-in-time event
    }]

    energy = GROUP_DAILY_ENERGY[user["target_group"]]
    fatigue = 0
    
    # ETAP 2 - DAY 3 (15.02.2026): Multi-day cross-day POI tracking
    # Initialize used set from global_used (if provided) to avoid duplicates across days
    used = set(global_used) if global_used is not None else set()
    
    last_poi = None

    # FIX #7 (02.02.2026): Track attraction counts for limits
    attraction_count = 0
    core_attraction_count = 0
    
    # CLIENT REQUIREMENT (04.02.2026): Track kids-focused POI for daily limit
    kids_focused_count = 0  # Max 1/day for non-family groups
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9): Track termy/spa for daily limit
    termy_count = 0  # Max 1/day for seniors
    
    limits = GROUP_ATTRACTION_LIMITS.get(user["target_group"], {
        "soft": 7,
        "hard": 8,
        "core_min": 1,
        "core_max": 2,
    })

    # HUMAN STATE
    culture_streak = 0
    body_state = "neutral"
    finale_done = False
    lunch_done = False
    dinner_done = False  # UAT Problem #11: Track dinner_break
    
    # BUDGET TRACKING (FIX 07.02.2026)
    # Track daily cost to enforce daily_limit hard constraint
    daily_cost = 0  # Sum of ticket_price for all POI added today
    
    # UAT FIX (18.02.2026 - Problem #5): Enhanced daily_limit detection
    # Check multiple possible locations for daily_limit in user dict
    daily_limit = user.get("daily_limit")  # Direct: user.daily_limit
    
    if daily_limit is None:
        # Try user.budget.daily_limit
        budget_dict = user.get("budget", {})
        if isinstance(budget_dict, dict):
            daily_limit = budget_dict.get("daily_limit")
    
    if daily_limit is None:
        # Try user.group.daily_limit
        group_dict = user.get("group", {})
        if isinstance(group_dict, dict):
            daily_limit = group_dict.get("daily_limit")
    
    # Convert to int if string
    if daily_limit is not None:
        try:
            daily_limit = int(daily_limit)
            print(f"[BUDGET] Daily limit detected: {daily_limit} PLN")
        except (ValueError, TypeError):
            daily_limit = None
            print(f"[BUDGET] WARNING: Invalid daily_limit value: {user.get('daily_limit')}")
    else:
        print(f"[BUDGET] No daily_limit set - budget tracking disabled")

    while now < end:
        # FEEDBACK KLIENTKI (03.02.2026): Enforce core_min POI
        # If we're in second half of day and no core POI yet, boost core POI heavily
        half_day = (end + time_to_minutes(start_time_str)) // 2
        if now > half_day and core_attraction_count < limits.get("core_min", 1):
            print(f"[CORE POI] Mid-day checkpoint: {core_attraction_count} core POI, boosting core attractions")
        
        
        # === LUNCH CHECKPOINT ===
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #8):
        # Enforce strict lunch time window (12:00-14:30)
        # - Insert lunch as soon as we reach 12:00
        # - If passed 14:30, insert lunch immediately with warning
        if not lunch_done:
            lunch_earliest = time_to_minutes(LUNCH_EARLIEST)  # 12:00
            lunch_target = time_to_minutes(LUNCH_TARGET)      # 13:00
            lunch_latest = time_to_minutes(LUNCH_LATEST)      # 14:30

            should_insert_lunch = False
            is_late_lunch = False
            
            # Case 1: We've reached earliest lunch time (12:00)
            if now >= lunch_earliest:
                should_insert_lunch = True
                
                # Case 1a: Already past latest lunch time (14:30) - late lunch!
                if now > lunch_latest:
                    is_late_lunch = True
                    print(f"[LUNCH] WARNING: Late lunch scheduled at {minutes_to_time(now)} (should be by {LUNCH_LATEST})")
            
            if should_insert_lunch:
                lunch_start_time = minutes_to_time(now)
                lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))
                
                # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding lunch
                overlaps, conflict = _check_time_overlap(plan, lunch_start_time, lunch_end_time)
                if overlaps:
                    print(f"[OVERLAP DETECTED] lunch_break {lunch_start_time}-{lunch_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                    # Adjust lunch time - move to after conflicting item
                    conflict_end_min = time_to_minutes(conflict.get('end_time', lunch_start_time))
                    now = conflict_end_min
                    lunch_start_time = minutes_to_time(now)
                    lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))
                
                plan.append(
                    {
                        "type": "lunch_break",
                        "start_time": lunch_start_time,
                        "end_time": lunch_end_time,
                        "duration_min": LUNCH_DURATION_MIN,
                        "suggestions": ["Lunch", "Restauracja", "Odpoczynek"],
                    }
                )
                now += LUNCH_DURATION_MIN
                lunch_done = True
                fatigue = max(0, fatigue - 2)
                print(f"[LUNCH] Inserted lunch at {lunch_start_time}-{lunch_end_time}")
                continue

        # UAT Problem #11: DINNER_BREAK
        # Add dinner break if:
        # - NOT done yet
        # - Current time >= DINNER_EARLIEST (18:00)
        # - Enough time left in day (at least 90 min before day_end)
        if not dinner_done:
            dinner_earliest = time_to_minutes(DINNER_EARLIEST)  # 18:00
            dinner_target = time_to_minutes(DINNER_TARGET)      # 19:00
            dinner_latest = time_to_minutes(DINNER_LATEST)      # 20:00
            should_insert_dinner = False
            is_late_dinner = False
            
            # Case 1: We've reached earliest dinner time (18:00)
            if now >= dinner_earliest:
                should_insert_dinner = True
                
                # Case 1a: Already past latest dinner time (20:00) - late dinner!
                if now > dinner_latest:
                    is_late_dinner = True
                    print(f"[DINNER] WARNING: Late dinner scheduled at {minutes_to_time(now)} (should be by {DINNER_LATEST})")
            
            if should_insert_dinner:
                dinner_start_time = minutes_to_time(now)
                dinner_end_time = minutes_to_time(min(end, now + DINNER_DURATION_MIN))
                
                # Check overlap before adding dinner
                overlaps, conflict = _check_time_overlap(plan, dinner_start_time, dinner_end_time)
                if overlaps:
                    print(f"[OVERLAP DETECTED] dinner_break {dinner_start_time}-{dinner_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                    # Adjust dinner time - move to after conflicting item
                    conflict_end_min = time_to_minutes(conflict.get('end_time', dinner_start_time))
                    now = conflict_end_min
                    dinner_start_time = minutes_to_time(now)
                    dinner_end_time = minutes_to_time(min(end, now + DINNER_DURATION_MIN))
                
                # Generate suggestions based on preferences
                dinner_suggestions = ["Regionalna restauracja", "Bacówka", "Karcma góralska"]
                if "local_food_experience" in user.get("preferences", []):
                    dinner_suggestions = [
                        "Regionalna restauracja z kuchnią góralską",
                        "Bacówka z degustacją oscypka",
                        "Karcma z tradycyjnymi potrawami"
                    ]
                
                plan.append(
                    {
                        "type": "dinner_break",
                        "start_time": dinner_start_time,
                        "end_time": dinner_end_time,
                        "duration_min": DINNER_DURATION_MIN,
                        "suggestions": dinner_suggestions,
                    }
                )
                now += DINNER_DURATION_MIN
                dinner_done = True
                fatigue = max(0, fatigue - 2)
                print(f"[DINNER] Inserted dinner at {dinner_start_time}-{dinner_end_time}")
                continue

        # swiety final
        if finale_done:
            break
        
        # FIX #7 (02.02.2026): Hard stop if attraction limit reached
        if attraction_count >= limits["hard"]:
            print(f"[LIMITS] Hard stop: {attraction_count}/{limits['hard']} attractions reached")
            break

        best = None
        best_score = -9999
        best_travel = 0
        best_duration = 0

        for p in pois:
            if poi_id(p) in used:
                continue
            
            # FEEDBACK KLIENTKI (03.02.2026) - HARD FILTERS
            # STEP 1: Target group hard filter
            if should_exclude_by_target_group(p, user):
                print(f"[FILTER] EXCLUDED by target_group: {p.get('Name', 'Unknown')} (poi_id={poi_id(p)}) - user={user.get('target_group')}, poi_groups={p.get('target_groups', [])}, kids_only={p.get('kids_only', False)}")
                continue  # EXCLUDE - target group mismatch
            
            # STEP 2: Intensity hard filter
            if should_exclude_by_intensity(p, user):
                print(f"[FILTER] EXCLUDED by intensity: {p.get('Name', 'Unknown')} (poi_id={poi_id(p)}) - user={user.get('target_group')}, poi_intensity={p.get('intensity', 'unknown')}")
                continue  # EXCLUDE - intensity conflict
            
            # FIX #7: Check core POI limit
            is_core = is_core_poi(p)
            if is_core and core_attraction_count >= limits["core_max"]:
                continue  # Skip - too many core POI already
            
            # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
            user_group = user.get("target_group", "")
            if user_group in ['solo', 'couples', 'friends', 'seniors']:
                if is_kids_focused_poi(p) and kids_focused_count >= 1:
                    print(f"[LIMITS] Skip kids-focused POI ID: {poi_id(p)} (already have {kids_focused_count}/1)")
                    continue  # Skip - already have 1 kids-focused POI today
            
            # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9): Max 1 termy/spa per day for seniors
            if user_group == 'seniors':
                if is_termy_spa(p) and termy_count >= 1:
                    print(f"[LIMITS] Skip termy/spa POI ID: {poi_id(p)} (already have {termy_count}/1 for seniors)")
                    continue  # Skip - already have 1 termy/spa today
            
            # UAT FIX (18.02.2026 - Problem #6): Global termy limit across all days
            # Test 08: 5 termy in 7 days is too much (max 2-3)
            if global_termy_tracking is not None and is_termy_spa(p):
                if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                    print(f"[LIMITS] Skip termy/spa POI ID: {poi_id(p)} (global limit {global_termy_tracking['count']}/{global_termy_tracking['max']})")
                    continue  # Skip - global termy limit reached
            
            # STEP 3: Budget hard filter (FIX 07.02.2026)
            # If daily_limit is set, check if adding this POI would exceed budget
            # FIX (07.02.2026 v2): daily_limit is per GROUP, so multiply ticket_price by group_size
            if daily_limit is not None:
                group_size = user.get("group_size", 1)
                poi_cost_per_person = float(p.get("ticket_price", 0))
                poi_cost_total = poi_cost_per_person * group_size
                potential_cost = daily_cost + poi_cost_total
                if potential_cost > daily_limit:
                    print(f"[FILTER] EXCLUDED by budget: POI_ID={poi_id(p)} (cost={poi_cost_per_person}x{group_size}={poi_cost_total} PLN, current={daily_cost}/{daily_limit} PLN)")
                    continue  # EXCLUDE - would exceed daily budget limit

            travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
            
            # BUGFIX: For first POI with car, add parking (15 min) + walk_time
            if not last_poi and ctx.get("has_car", True):
                parking_duration = 15
                walk_time = p.get("parking_walk_time_min", 5)
                travel = parking_duration + walk_time
            
            start_time = now + travel

            # jezeli po transferze nie ma juz czasu – pomijamy POI
            if start_time >= end:
                continue

            duration = choose_duration(p, start_time, end, lunch_done)
            if duration <= 0:
                continue

            if not is_open(p, start_time, duration, ctx["season"], ctx):
                continue

            score = score_poi(
                p=p,
                user=user,
                fatigue=fatigue,
                used=used,
                now=start_time,
                energy_left=energy,
                context=ctx,
                culture_streak=culture_streak,
                body_state=body_state,
                finale_done=finale_done,
            )
            
            # FEEDBACK KLIENTKI (03.02.2026): Boost core POI if core_min not met
            # If we need core POI and this is core, add massive bonus
            if core_attraction_count < limits.get("core_min", 1) and is_core:
                score += 50  # Huge bonus to ensure core POI gets selected
                print(f"[CORE POI] Boosting {p.get('Name')} (core) by +50 to meet core_min")

            # BUGFIX (31.01.2026 - Problem #7): Increased travel penalty from 0.1 to 0.5
            # Prefer closer POI - e.g., Termy Zakopiańskie (closer) over Gorący Potok (farther)
            # Old: 22 min = -2.2 penalty (too weak)
            # New: 22 min = -11 penalty (strong preference for nearby)
            score -= travel * 0.5
            
            # FIX #7 (02.02.2026): Soft limit penalty
            # After soft limit, heavily penalize additional attractions
            if attraction_count >= limits["soft"]:
                score -= 50  # Strong penalty to discourage exceeding soft limit
                print(f"[LIMITS] Soft limit penalty: {attraction_count}/{limits['soft']} attractions, -50 score")

            # CLIENT REQUIREMENT (04.02.2026): Collect candidates within 1% of best score for variety
            # This prevents always selecting same POI, adds diversity to plans
            if score > best_score:
                best = p
                best_score = score
                best_travel = travel
                best_duration = duration
        
        # CLIENT REQUIREMENT (08.02.2026): CORE POI ROTATION
        # Special handling when we need core POI: collect ALL viable core candidates
        # (not just 1% threshold) to enable rotation among top core POI
        # This prevents always selecting same high-scoring core (e.g., Morskie Oko)
        if best:
            # Check if we need to select a core POI
            if core_attraction_count < limits.get("core_min", 1):
                # CORE POI ROTATION LOGIC
                # Collect ALL viable core POI candidates to enable rotation
                core_candidates = []
                
                for p in pois:
                    if poi_id(p) in used:
                        continue
                    
                    # Only collect core POI for rotation
                    is_core = is_core_poi(p)
                    if not is_core:
                        continue
                    
                    # Apply same filters as main loop
                    if should_exclude_by_target_group(p, user):
                        continue
                    if should_exclude_by_intensity(p, user):
                        continue
                    
                    if is_core and core_attraction_count >= limits["core_max"]:
                        continue
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue
                    
                    # BUGFIX (16.02.2026 - Problem #9): Max 1 termy/spa per day for seniors
                    if user_group == 'seniors':
                        if is_termy_spa(p) and termy_count >= 1:
                            continue
                    
                    # BUDGET HARD FILTER
                    if daily_limit is not None:
                        group_size = user.get("group_size", 1)
                        poi_cost_total = float(p.get("ticket_price", 0)) * group_size
                        if daily_cost + poi_cost_total > daily_limit:
                            continue
                    
                    travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    if not last_poi and ctx.get("has_car", True):
                        parking_duration = 15
                        walk_time = p.get("parking_walk_time_min", 5)
                        travel = parking_duration + walk_time
                    
                    start_time = now + travel
                    if start_time >= end:
                        continue
                    
                    duration = choose_duration(p, start_time, end, lunch_done)
                    if duration <= 0:
                        continue
                    
                    if not is_open(p, start_time, duration, ctx["season"], ctx):
                        continue
                    
                    # Calculate score with core boost
                    score = score_poi(
                        p=p, user=user, fatigue=fatigue, used=used, now=start_time,
                        energy_left=energy, context=ctx, culture_streak=culture_streak,
                        body_state=body_state, finale_done=finale_done,
                    )
                    
                    score += 50  # Core boost (same as main loop)
                    score -= travel * 0.5
                    
                    if attraction_count >= limits["soft"]:
                        score -= 50
                    
                    core_candidates.append({
                        "poi": p,
                        "score": score,
                        "travel": travel,
                        "duration": duration
                    })
                
                # Sort by score and select randomly from top 4-5 core POI
                if core_candidates:
                    core_candidates.sort(key=lambda x: x["score"], reverse=True)
                    top_core = core_candidates[:5]  # Top 5 core POI
                    
                    # Random selection from top core POI for variety
                    selected = random.choice(top_core)
                    best = selected["poi"]
                    best_score = selected["score"]
                    best_travel = selected["travel"]
                    best_duration = selected["duration"]
                    print(f"[CORE ROTATION] Selected from {len(top_core)} top core POI: POI_ID={poi_id(best)} (score={best_score:.1f})")
            
            else:
                # NORMAL VARIETY LOGIC (when core_min already met or for non-core POI)
                # CLIENT REQUIREMENT (04.02.2026): Randomize within 1% of top score
                threshold = best_score * 0.99  # 1% tolerance
                candidates = []
                
                # Re-scan to find all POI within 1% of best score
                for p in pois:
                    if poi_id(p) in used:
                        continue
                    
                    # Apply same filters as before
                    if should_exclude_by_target_group(p, user):
                        continue
                    if should_exclude_by_intensity(p, user):
                        continue
                    
                    is_core = is_core_poi(p)
                    if is_core and core_attraction_count >= limits["core_max"]:
                        continue
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue
                    
                    # BUGFIX (16.02.2026 - Problem #9): Max 1 termy/spa per day for seniors
                    if user_group == 'seniors':
                        if is_termy_spa(p) and termy_count >= 1:
                            continue
                    
                    # BUDGET HARD FILTER (FIX 07.02.2026): Apply to candidate collection
                    # FIX (07.02.2026 v2): Multiply by group_size for per-group budget
                    if daily_limit is not None:
                        group_size = user.get("group_size", 1)
                        poi_cost_total = float(p.get("ticket_price", 0)) * group_size
                        if daily_cost + poi_cost_total > daily_limit:
                            continue  # EXCLUDE - would exceed daily budget limit
                    
                    travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    if not last_poi and ctx.get("has_car", True):
                        parking_duration = 15
                        walk_time = p.get("parking_walk_time_min", 5)
                        travel = parking_duration + walk_time
                    
                    start_time = now + travel
                    if start_time >= end:
                        continue
                    
                    duration = choose_duration(p, start_time, end, lunch_done)
                    if duration <= 0:
                        continue
                    
                    if not is_open(p, start_time, duration, ctx["season"], ctx):
                        continue
                    
                    # Calculate same score
                    score = score_poi(
                        p=p, user=user, fatigue=fatigue, used=used, now=start_time,
                        energy_left=energy, context=ctx, culture_streak=culture_streak,
                        body_state=body_state, finale_done=finale_done,
                    )
                    
                    if core_attraction_count < limits.get("core_min", 1) and is_core:
                        score += 50
                    
                    score -= travel * 0.5
                    
                    if attraction_count >= limits["soft"]:
                        score -= 50
                    
                    # Collect candidates within 1% threshold
                    if score >= threshold:
                        candidates.append({
                            "poi": p,
                            "score": score,
                            "travel": travel,
                            "duration": duration
                        })
                
                # Randomize selection from top candidates
                if len(candidates) > 1:
                    selected = random.choice(candidates)
                    best = selected["poi"]
                    best_score = selected["score"]
                    best_travel = selected["travel"]
                    best_duration = selected["duration"]
                    print(f"[VARIETY] Selected from {len(candidates)} candidates within 1% of top score: POI_ID={poi_id(best)} (score={best_score:.1f})")
                elif len(candidates) == 1:
                    # Only one candidate, use it (same as before)
                    best = candidates[0]["poi"]
                    best_score = candidates[0]["score"]
                    best_travel = candidates[0]["travel"]
                    best_duration = candidates[0]["duration"]
        
        # Check if POI was selected

        if not best:
            # FALLBACK for gaps >20 min: Try soft POI or add free_time
            # Client requirement: gaps >20 min should have soft POI or free_time
            
            remaining_time = end - now
            
            if remaining_time >= 20:  # Only handle gaps >20 min
                # Try to find soft POI: low intensity, short duration, low must_see
                soft_best = None
                soft_score = -9999
                soft_duration = 0
                
                for p in pois:
                    if poi_id(p) in used:
                        continue
                    
                    # HOTFIX #10.8: Apply hard filters (target_group + intensity) to soft POI selection
                    if should_exclude_by_target_group(p, user):
                        continue  # EXCLUDE - target group mismatch
                    
                    if should_exclude_by_intensity(p, user):
                        continue  # EXCLUDE - intensity conflict
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue  # Skip - already have 1 kids-focused POI today
                    
                    # BUDGET HARD FILTER (FIX 07.02.2026): Apply to soft POI too
                    # FIX (07.02.2026 v2): Multiply by group_size for per-group budget
                    if daily_limit is not None:
                        group_size = user.get("group_size", 1)
                        poi_cost_total = float(p.get("ticket_price", 0)) * group_size
                        if daily_cost + poi_cost_total > daily_limit:
                            continue  # EXCLUDE - would exceed daily budget limit
                    
                    # UAT FIX (18.02.2026 - Problem #6): Check global termy limit (fallback soft POI)
                    if global_termy_tracking is not None and is_termy_spa(p):
                        if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                            continue  # Skip - global termy limit reached
                    
                    # Soft POI criteria (client requirements)
                    # Since all Zakopane POI have intensity='medium', accept medium intensity
                    # Focus on: short duration (10-30 min) + low must_see_score (0-2)
                    
                    time_min = p.get("time_min", 60)
                    if time_min > 30 or time_min < 10:  # 10-30 min range
                        continue
                    
                    must_see_score = p.get("must_see", p.get("must_see_score", 10))
                    if must_see_score > 7:  # Allow POI with must_see up to 7
                        continue
                    
                    # Calculate travel time
                    soft_travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    
                    # For first soft POI with car, add parking + walk
                    if not last_poi and ctx.get("has_car", True):
                        parking_duration = 15
                        walk_time = p.get("parking_walk_time_min", 5)
                        soft_travel = parking_duration + walk_time
                    
                    start_time = now + soft_travel
                    
                    if start_time >= end:
                        continue
                    
                    duration = min(time_min, remaining_time - soft_travel)
                    if duration < 10:  # Too short
                        continue
                    
                    if not is_open(p, start_time, duration, ctx["season"], ctx):
                        continue
                    
                    # Simple scoring for soft POI (prefer nearby, quick visits)
                    score = 10 - soft_travel * 0.5 + (30 - time_min) * 0.2
                    
                    if score > soft_score:
                        soft_best = p
                        soft_score = score
                        soft_duration = duration
                        soft_travel_time = soft_travel  # Store travel time
                
                if soft_best:
                    # Found soft POI - add it
                    best = soft_best
                    best_score = soft_score
                    best_travel = soft_travel_time  # Use stored travel time
                    best_duration = soft_duration
                else:
                    # No soft POI - add free_time (max 40 min)
                    free_duration = min(40, remaining_time)
                    free_start_time = minutes_to_time(now)
                    free_end_time = minutes_to_time(now + free_duration)
                    
                    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding
                    overlaps, conflict = _check_time_overlap(plan, free_start_time, free_end_time)
                    if overlaps:
                        print(f"[OVERLAP DETECTED] free_time {free_start_time}-{free_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                        # Skip this free_time, continue loop
                        now += 15
                        continue
                    
                    plan.append({
                        "type": "free_time",
                        "start_time": free_start_time,
                        "end_time": free_end_time,
                        "duration_min": free_duration,
                        "description": "Czas wolny: spacer, kawa, odpoczynek"
                    })
                    
                    now += free_duration
                    continue
            else:
                # Gap <20 min or not enough time - just advance time
                now += 15
                if now + 30 >= end:
                    break
                continue
        
        # POI selected (either normal or soft) - add to plan
        if not best:
            continue

        transfer_time = (
            max(best_travel, MIN_TRANSFER_MIN) if last_poi else 0
        )

        # BUGFIX (17.02.2026): Check if POI + buffers would exceed day_end
        # Estimate buffer time: parking_walk (~5 min) + restroom (~5-10 min) + photo_stop (~10 min) = ~20-25 min
        # Add 30 min safety margin to account for buffers
        estimated_buffer_time = 30
        if now + transfer_time + best_duration + estimated_buffer_time > end:
            poi_name_safe = str(poi_name(best)).encode('ascii', errors='ignore').decode('ascii')
            print(f"[POI SKIP] POI {poi_name_safe} would exceed day_end with buffers ({minutes_to_time(now + transfer_time + best_duration + estimated_buffer_time)} > {minutes_to_time(end)})")
            break

        if last_poi:
            transfer_time = max(best_travel, MIN_TRANSFER_MIN)

            plan.append(
                {
                    "type": "transfer",
                    "from": poi_name(last_poi),
                    "to": poi_name(best),
                    "duration_min": transfer_time,
                }
            )

            now += transfer_time
            
            # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add parking_walk buffer after car transfer
            # Client requirement: "Oś czasu ma dziury" - dodaj buffer parking_walk po transfer
            if ctx.get("has_car", True):
                parking_walk_duration = best.get("parking_walk_time_min", 5)
                # Ensure reasonable range: 5-15 min
                parking_walk_duration = max(5, min(15, int(parking_walk_duration)))
                now = _add_buffer_item(
                    plan, 
                    now, 
                    "parking_walk", 
                    parking_walk_duration,
                    reason_context={"poi_name": poi_name(best)},
                    day_end=end
                )
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add tickets_queue buffer for popular attractions
        # Client requirement: Add buffer for waiting in line at popular places
        popularity_score = best.get("popularity_score", 0)
        if popularity_score >= 7:  # Popular attractions (score 7-10)
            # Queue time: 5-20 min based on popularity
            queue_duration = int(5 + (popularity_score - 7) * 5)  # 7→5min, 8→10min, 9→15min, 10→20min
            queue_duration = max(5, min(20, queue_duration))
            now = _add_buffer_item(
                plan,
                now,
                "tickets_queue",
                queue_duration,
                reason_context={"poi_name": poi_name(best)},
                day_end=end
            )

        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding attraction
        attraction_start_time = minutes_to_time(now)
        attraction_end_time = minutes_to_time(now + best_duration)
        
        overlaps, conflict = _check_time_overlap(plan, attraction_start_time, attraction_end_time)
        if overlaps:
            print(f"[OVERLAP DETECTED] attraction {poi_name(best)} {attraction_start_time}-{attraction_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
            # Skip this POI, mark as used to avoid retry, continue loop
            used.add(poi_id(best))
            now += 15  # Advance time slightly
            continue

        plan.append(
            {
                "type": "attraction",
                "poi": best,  # Całe POI dla PlanService
                "name": poi_name(best),
                "start_time": attraction_start_time,
                "end_time": attraction_end_time,
                "meta": {
                    "experience_role": best.get("experience_role"),
                    "is_culture": bool(is_culture(best)),
                    "body_state_after": get_next_body_state(best, body_state),
                },
            }
        )

        # HOTFIX #10.7: Debug logging - track which POI engine adds
        print(f"[ENGINE SELECTION] ADDED POI: id={poi_id(best)}, time={minutes_to_time(now)}")
        
        # BUDGET TRACKING (FIX 07.02.2026): Update daily cost
        # FIX (07.02.2026 v2): Multiply by group_size for per-group budget
        group_size = user.get("group_size", 1)
        poi_cost_per_person = float(best.get("ticket_price", 0))
        poi_cost_total = poi_cost_per_person * group_size
        daily_cost += poi_cost_total
        if daily_limit is not None:
            print(f"[BUDGET] POI cost: {poi_cost_per_person}×{group_size}={poi_cost_total} PLN, daily total: {daily_cost}/{daily_limit} PLN")

        now += best_duration
        energy -= energy_cost(best, best_duration, ctx)
        fatigue += 1
        used.add(poi_id(best))
        
        # ETAP 2 - DAY 3 (15.02.2026): Update global_used for cross-day tracking
        if global_used is not None:
            global_used.add(poi_id(best))
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add restroom buffer after long attractions
        # Client requirement: Add realistic buffers for bathroom breaks
        if best_duration >= 60:  # Long attraction (60+ min)
            restroom_duration = min(10, max(5, int(best_duration / 60) * 5))  # 5-10 min based on duration
            now = _add_buffer_item(
                plan,
                now,
                "restroom",
                restroom_duration,
                reason_context={"poi_name": poi_name(best)},
                day_end=end
            )
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #4): Add photo_stop buffer at scenic locations
        # Client requirement: Add buffer for photo opportunities at viewpoints
        poi_tags = best.get("tags", []) or []
        tag_list = [str(t).lower() for t in poi_tags if t]
        is_scenic = any(tag in tag_list for tag in ["viewpoint", "scenic", "panorama", "mountain_view"])
        
        if is_scenic:
            photo_duration = 10  # Standard 10 min for photo stop
            now = _add_buffer_item(
                plan,
                now,
                "photo_stop",
                photo_duration,
                reason_context={"poi_name": poi_name(best)},
                day_end=end
            )
        
        last_poi = best
        
        # FIX #7 (02.02.2026): Update attraction counters
        attraction_count += 1
        is_core_attraction = is_core_poi(best)
        if is_core_attraction:
            core_attraction_count += 1
        print(f"[LIMITS] Added attraction: {attraction_count}/{limits['hard']} total, {core_attraction_count}/{limits['core_max']} core")
        
        # CLIENT REQUIREMENT (04.02.2026): Increment kids-focused counter for non-family
        user_group = user.get("target_group", "")
        if user_group in ['solo', 'couples', 'friends', 'seniors']:
            if is_kids_focused_poi(best):
                kids_focused_count += 1
                print(f"[LIMITS] Kids-focused POI added: {kids_focused_count}/1 for today")
        
        # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #9): Increment termy counter for seniors
        if user_group == 'seniors':
            if is_termy_spa(best):
                termy_count += 1
                print(f"[LIMITS] Termy/spa POI added: {termy_count}/1 for seniors today")
        
        # UAT FIX (18.02.2026 - Problem #6): Increment global termy counter
        if global_termy_tracking is not None and is_termy_spa(best):
            global_termy_tracking["count"] += 1
            print(f"[LIMITS] Global termy count: {global_termy_tracking['count']}/{global_termy_tracking['max']}")

        # update kultur
        if is_culture(best):
            culture_streak += 1
        
        # GAP FILLING: Check if next POI creates gap >20 min
        # Look ahead to see when next POI would start
        remaining = end - now
        if remaining > 20:  # Only if enough time left
            # Try to find next POI to calculate potential gap
            next_poi_time = None
            next_best_travel = 999
            
            for p in pois:
                if poi_id(p) in used:
                    continue
                
                travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                test_start = now + travel
                
                if test_start >= end:
                    continue
                
                test_duration = choose_duration(p, test_start, end, lunch_done)
                if test_duration <= 0:
                    continue
                
                if not is_open(p, test_start, test_duration, ctx["season"], ctx):
                    continue
                
                # Found potential next POI
                if travel < next_best_travel:
                    next_best_travel = travel
                    next_poi_time = test_start
                    break  # Use first viable POI for gap check
            
            # Check if there's a gap before next POI
            if next_poi_time and (next_poi_time - now) > 20:
                gap_duration = next_poi_time - now
                
                # Try to fill gap with soft POI
                soft_filled = False
                for p in pois:
                    if poi_id(p) in used:
                        continue
                    
                    # HOTFIX #10.8: Apply hard filters (target_group + intensity) to soft POI selection
                    if should_exclude_by_target_group(p, user):
                        continue  # EXCLUDE - target group mismatch
                    
                    if should_exclude_by_intensity(p, user):
                        continue  # EXCLUDE - intensity conflict
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p) and kids_focused_count >= 1:
                            continue  # Skip - already have 1 kids-focused POI today
                    
                    # BUGFIX (16.02.2026 - Problem #9): Max 1 termy/spa per day for seniors
                    if user_group == 'seniors':
                        if is_termy_spa(p) and termy_count >= 1:
                            continue  # Skip - already have 1 termy/spa today
                    
                    # UAT FIX (18.02.2026 - Problem #6): Check global termy limit
                    if global_termy_tracking is not None and is_termy_spa(p):
                        if global_termy_tracking["count"] >= global_termy_tracking["max"]:
                            continue  # Skip - global termy limit reached
                    
                    # FIX #7 (02.02.2026): Check hard limit before adding soft POI
                    if attraction_count >= limits["hard"]:
                        break  # Stop gap filling if limit reached
                    
                    # Soft POI criteria
                    time_min = p.get("time_min", 60)
                    if time_min > 30 or time_min < 10:
                        continue
                    
                    must_see_score = p.get("must_see", p.get("must_see_score", 10))
                    if must_see_score > 7:  # Allow POI with must_see up to 7
                        continue
                    
                    soft_travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    soft_start = now + soft_travel
                    
                    if soft_start >= next_poi_time or soft_start >= end:
                        continue
                    
                    soft_duration = min(time_min, gap_duration - soft_travel, next_poi_time - soft_start)
                    if soft_duration < 10:
                        continue
                    
                    if not is_open(p, soft_start, soft_duration, ctx["season"], ctx):
                        continue
                    
                    # Add soft POI to fill gap
                    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding
                    soft_start_time = minutes_to_time(now + soft_travel)
                    soft_end_time = minutes_to_time(now + soft_travel + soft_duration)
                    
                    overlaps, conflict = _check_time_overlap(plan, soft_start_time, soft_end_time)
                    if overlaps:
                        print(f"[OVERLAP DETECTED] soft POI {poi_name(p)} {soft_start_time}-{soft_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
                        continue  # Skip this soft POI
                    
                    if soft_travel > 0:
                        plan.append({
                            "type": "transfer",
                            "from": poi_name(last_poi),
                            "to": poi_name(p),
                            "duration_min": soft_travel,
                        })
                        now += soft_travel
                    
                    plan.append({
                        "type": "attraction",
                        "poi": p,
                        "name": poi_name(p),
                        "start_time": minutes_to_time(now),
                        "end_time": minutes_to_time(now + soft_duration),
                        "meta": {
                            "experience_role": "filler",  # Mark as gap filler
                            "is_culture": bool(is_culture(p)),
                            "body_state_after": get_next_body_state(p, body_state),
                        },
                    })
                    
                    now += soft_duration
                    used.add(poi_id(p))
                    last_poi = p
                    
                    # FIX #7 (02.02.2026): Update counters for soft POI too
                    attraction_count += 1
                    is_core_soft = is_core_poi(p)
                    if is_core_soft:
                        core_attraction_count += 1
                    print(f"[LIMITS] Added soft POI: {attraction_count}/{limits['hard']} total, {core_attraction_count}/{limits['core_max']} core")
                    
                    # CLIENT REQUIREMENT (04.02.2026): Increment kids-focused counter for non-family
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p):
                            kids_focused_count += 1
                            print(f"[LIMITS] Kids-focused POI added (soft): {kids_focused_count}/1 for today")
                    
                    # BUGFIX (16.02.2026 - Problem #9): Increment termy counter for seniors (soft POI)
                    if user_group == 'seniors':
                        if is_termy_spa(p):
                            termy_count += 1
                            print(f"[LIMITS] Termy/spa POI added (soft): {termy_count}/1 for seniors today")
                    
                    # UAT FIX (18.02.2026 - Problem #6): Increment global termy counter (gap filler)
                    if global_termy_tracking is not None and is_termy_spa(p):
                        global_termy_tracking["count"] += 1
                        print(f"[LIMITS] Global termy count (gap filler): {global_termy_tracking['count']}/{global_termy_tracking['max']}")
                    
                    soft_filled = True
                    break  # Fill one soft POI per gap
                
                # If no soft POI fits, add free_time (max 40 min)
                if not soft_filled and gap_duration > 20:
                    free_duration = min(40, gap_duration)
                    free_start_time = minutes_to_time(now)
                    free_end_time = minutes_to_time(now + free_duration)
                    
                    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #2): Check overlap before adding
                    overlaps, conflict = _check_time_overlap(plan, free_start_time, free_end_time)
                    if not overlaps:
                        plan.append({
                            "type": "free_time",
                            "start_time": free_start_time,
                            "end_time": free_end_time,
                            "duration_min": free_duration,
                            "description": "Czas wolny: spacer, kawa, odpoczynek"
                        })
                        now += free_duration
                    else:
                        print(f"[OVERLAP DETECTED] gap-fill free_time {free_start_time}-{free_end_time} conflicts with {conflict.get('type')} {conflict.get('start_time')}-{conflict.get('end_time')}")
        else:
            culture_streak = 0

        # update body
        body_state = get_next_body_state(best, body_state)

        # finale lock
        if is_finale(best):
            finale_done = True

    # UAT FIX (18.02.2026 - Problem #4): Fill massive time gaps before day_end
    # Tests 03, 06, 07, 08, 09: Days end at 14:30, day_end at 19:00 (4.5h gap)
    # Solution: If (day_end - current_time) > 180min, add light activities
    remaining_to_end = end - now
    
    if remaining_to_end > 180:  # 3+ hours remaining
        print(f"[GAP FILL END] Large gap remaining: {remaining_to_end}min ({minutes_to_time(now)} → {minutes_to_time(end)})")
        
        # Try to add 1-2 light activities to fill the gap
        gap_fill_attempts = 0
        max_gap_fill = 2  # Max 2 additional light activities
        
        while remaining_to_end > 90 and gap_fill_attempts < max_gap_fill:
            # Find soft POI (light activity: 30-60 min, low must_see)
            soft_best = None
            soft_score = -9999
            soft_duration = 0
            soft_travel = 0
            
            for p in pois:
                if poi_id(p) in used:
                    continue
                
                # Apply hard filters
                if should_exclude_by_target_group(p, user):
                    continue
                if should_exclude_by_intensity(p, user):
                    continue
                
                # Limits
                user_group = user.get("target_group", "")
                if user_group in ['solo', 'couples', 'friends', 'seniors']:
                    if is_kids_focused_poi(p) and kids_focused_count >= 1:
                        continue
                if user_group == 'seniors':
                    if is_termy_spa(p) and termy_count >= 1:
                        continue
                if attraction_count >= limits["hard"]:
                    break
                
                # Budget filter
                if daily_limit is not None:
                    group_size = user.get("group_size", 1)
                    poi_cost_total = float(p.get("ticket_price", 0)) * group_size
                    if daily_cost + poi_cost_total > daily_limit:
                        continue
                
                # Soft POI criteria: 10-60 min, must_see <= 7
                time_min = p.get("time_min", 60)
                if time_min < 10 or time_min > 60:
                    continue
                must_see_score = p.get("must_see", p.get("must_see_score", 10))
                if must_see_score > 7:
                    continue
                
                # Calculate travel + duration
                travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                start_time = now + travel
                if start_time >= end:
                    continue
                
                duration = min(time_min, remaining_to_end - travel)
                if duration < 10:
                    continue
                
                if not is_open(p, start_time, duration, ctx["season"], ctx):
                    continue
                
                # Simple scoring: prefer nearby, quick visits
                score = 10 - travel * 0.5
                
                if score > soft_score:
                    soft_best = p
                    soft_score = score
                    soft_duration = duration
                    soft_travel = travel
            
            if soft_best:
                # Add soft POI to fill gap
                if soft_travel > 0:
                    plan.append({
                        "type": "transfer",
                        "from": poi_name(last_poi) if last_poi else "start",
                        "to": poi_name(soft_best),
                        "duration_min": soft_travel,
                    })
                    now += soft_travel
                
                plan.append({
                    "type": "attraction",
                    "poi": soft_best,
                    "name": poi_name(soft_best),
                    "start_time": minutes_to_time(now),
                    "end_time": minutes_to_time(now + soft_duration),
                    "meta": {
                        "experience_role": "gap_filler",
                        "is_culture": bool(is_culture(soft_best)),
                        "body_state_after": get_next_body_state(soft_best, body_state),
                    },
                })
                
                now += soft_duration
                used.add(poi_id(soft_best))
                if global_used is not None:
                    global_used.add(poi_id(soft_best))
                
                # Update counters
                attraction_count += 1
                if is_core_poi(soft_best):
                    core_attraction_count += 1
                if user_group in ['solo', 'couples', 'friends', 'seniors']:
                    if is_kids_focused_poi(soft_best):
                        kids_focused_count += 1
                if user_group == 'seniors':
                    if is_termy_spa(soft_best):
                        termy_count += 1
                
                # Update budget
                if daily_limit is not None:
                    group_size = user.get("group_size", 1)
                    poi_cost_total = float(soft_best.get("ticket_price", 0)) * group_size
                    daily_cost += poi_cost_total
                
                last_poi = soft_best
                remaining_to_end = end - now
                gap_fill_attempts += 1
                
                print(f"[GAP FILL END] Added light activity: {poi_name(soft_best)} ({soft_duration}min), remaining={remaining_to_end}min")
            else:
                # No soft POI available, add free_time (max 90min)
                free_duration = min(90, remaining_to_end)
                free_start_time = minutes_to_time(now)
                free_end_time = minutes_to_time(now + free_duration)
                
                overlaps, conflict = _check_time_overlap(plan, free_start_time, free_end_time)
                if not overlaps:
                    plan.append({
                        "type": "free_time",
                        "start_time": free_start_time,
                        "end_time": free_end_time,
                        "duration_min": free_duration,
                        "description": "Czas wolny na relaks: spacer, kawa, zakupy, odpoczynek"
                    })
                    now += free_duration
                    remaining_to_end = end - now
                    print(f"[GAP FILL END] Added free_time ({free_duration}min), remaining={remaining_to_end}min")
                
                break  # Exit after adding free_time (stop gap filling)

    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #10):
    # Standardize all items to use start_time/end_time (not "time")
    plan.append({
        "type": "accommodation_end",
        "start_time": minutes_to_time(end),
        "end_time": minutes_to_time(end)  # Point-in-time event
    })
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #7):
    # Validate time continuity and auto-fix gaps to day_end
    print(f"[TIME CONTINUITY] Validating plan with day_end={end_time_str}")
    is_valid, issues, fixed_plan = _validate_and_fix_time_continuity(plan, end_time_str)
    
    if issues:
        print(f"[TIME CONTINUITY] Found {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue}")
    
    if not is_valid:
        print(f"[TIME CONTINUITY] WARNING: Plan has critical issues (overlaps or exceeds day_end)")
    else:
        print(f"[TIME CONTINUITY] Plan validated successfully")
    
    # Use fixed plan (may have auto-added free_time to day_end)
    plan = fixed_plan
    
    # BUGFIX (16.02.2026 - CLIENT FEEDBACK Problem #11):
    # Detect empty/sparse days (>50% free_time) and report error
    total_minutes = end - time_to_minutes(start_time_str)
    free_time_minutes = sum(
        item.get("duration_min", 0) 
        for item in plan 
        if item.get("type") == "free_time"
    )
    
    # Count actual attractions (not buffers, transits, lunch)
    attraction_count_final = sum(
        1 for item in plan if item.get("type") == "attraction"
    )
    
    if total_minutes > 0:
        free_time_pct = (free_time_minutes / total_minutes) * 100
        
        if free_time_pct > 50 or attraction_count_final == 0:
            print(f"\n[EMPTY DAY WARNING] Day is sparse or empty:")
            print(f"  - Free time: {free_time_minutes}/{total_minutes} min ({free_time_pct:.1f}%)")
            print(f"  - Attractions: {attraction_count_final}")
            print(f"  - Suggestion: Relax filters (target_group, intensity, budget, distance)")
    
    # NOTE: Gap filling moved to PlanService (after parking/transit timing adjustments)
    # This ensures gaps are detected AFTER all time shifts from parking
    
    return plan


def fill_plan_gaps(plan, pois, used_poi_ids, ctx, user):
    """
    Post-process plan to fill gaps >20 min between attractions.
    Client requirement: gaps should be filled with soft POI or free_time (max 40 min).
    HOTFIX #10.8: Added user parameter to apply hard filters (target_group + intensity).
    """
    print(f"[GAP FILLING DEBUG] Starting with {len(plan)} items", flush=True)
    print(f"[GAP FILLING DEBUG] RAW PLAN DUMP:", flush=True)
    for i, item in enumerate(plan):
        item_type = item.get('type')
        if item_type == 'attraction':
            print(f"  {i}. {item_type}: {item.get('name')} | start={item.get('start_time')} end={item.get('end_time')}", flush=True)
        elif item_type == 'transfer':
            print(f"  {i}. {item_type}: {item.get('from')} -> {item.get('to')} | duration={item.get('duration_min')} | HAS start_time={('start_time' in item)} HAS end_time={('end_time' in item)}", flush=True)
        elif item_type in ['lunch_break', 'free_time']:
            print(f"  {i}. {item_type}: start={item.get('start_time')} end={item.get('end_time')}", flush=True)
        else:
            print(f"  {i}. {item_type}: {item.get('time', 'N/A')}", flush=True)
    
    filled_plan = []
    last_end_time = None  # Track end time of previous item for transfers
    
    for i, item in enumerate(plan):
        filled_plan.append(item)
        
        print(f"[GAP FILLING DEBUG] Item {i}: type={item['type']}", flush=True)
        
        # Check for gap before next item
        if i < len(plan) - 1:
            next_item = plan[i + 1]
            
            # Get end time of current item
            current_end = None
            if item["type"] == "accommodation_start":
                current_end = time_to_minutes(item["time"])
            elif item["type"] == "attraction":
                current_end = time_to_minutes(item["end_time"])
            elif item["type"] in ["transfer", "transit"]:
                # Transfer in raw plan has no start_time/end_time, only duration_min
                # Calculate end time from last_end_time + duration
                if "end_time" in item:
                    current_end = time_to_minutes(item["end_time"])
                elif "start_time" in item:
                    current_end = time_to_minutes(item["start_time"]) + item["duration_min"]
                elif last_end_time is not None:
                    # Raw transfer: calculate from previous item's end
                    current_end = last_end_time + item["duration_min"]
                else:
                    # Can't determine end time
                    continue
            elif item["type"] == "lunch_break":
                current_end = time_to_minutes(item["end_time"])
            elif item["type"] == "free_time":
                current_end = time_to_minutes(item["end_time"])
            
            if current_end is None:
                continue
            
            # Remember this for next transfer
            last_end_time = current_end
            
            print(f"[GAP FILLING DEBUG] current_end={current_end}, last_end_time={last_end_time}", flush=True)
            
            if current_end is None:
                continue
            
            # Get start time of next item
            next_start = None
            if next_item["type"] == "attraction":
                next_start = time_to_minutes(next_item["start_time"])
                print(f"[GAP FILLING DEBUG] next attraction at {next_start}", flush=True)
            elif next_item["type"] == "lunch_break":
                next_start = time_to_minutes(next_item["start_time"])
                print(f"[GAP FILLING DEBUG] next lunch at {next_start}", flush=True)
            elif next_item["type"] in ["transfer", "transit"]:
                # No gap before transfer/transit - they happen immediately
                print(f"[GAP FILLING DEBUG] next is transfer/transit - skipping", flush=True)
                continue
            elif next_item["type"] == "accommodation_end":
                # No gap before day end
                print(f"[GAP FILLING DEBUG] next is day_end - skipping", flush=True)
                continue
            
            if next_start is None:
                print(f"[GAP FILLING DEBUG] next_start is None - skipping", flush=True)
                continue
            
            # Calculate gap
            gap_minutes = next_start - current_end
            print(f"[GAP FILLING DEBUG] GAP DETECTED: {gap_minutes} min (current_end={current_end}, next_start={next_start})", flush=True)
            
            # Fill gaps >20 min
            if gap_minutes > 20:
                print(f"[GAP FILLING DEBUG] Gap >20 min - trying to fill...", flush=True)
                # Try to find soft POI to fill gap
                soft_filled = False
                for p in pois:
                    if poi_id(p) in used_poi_ids:
                        continue
                    
                    # HOTFIX #10.8: Apply hard filters (target_group + intensity) to soft POI selection
                    if should_exclude_by_target_group(p, user):
                        continue  # EXCLUDE - target group mismatch
                    
                    if should_exclude_by_intensity(p, user):
                        continue  # EXCLUDE - intensity conflict
                    
                    # CLIENT REQUIREMENT (04.02.2026): Max 1 kids-focused POI per day for non-family
                    # Note: fill_plan_gaps doesn't have kids_focused_count, so this check is approximate
                    # (will be enforced in main loop, this is additional safety)
                    user_group = user.get("target_group", "")
                    if user_group in ['solo', 'couples', 'friends', 'seniors']:
                        if is_kids_focused_poi(p):
                            # Check if plan already has kids-focused POI
                            has_kids_focused = any(
                                is_kids_focused_poi(item.get("poi", {}))
                                for item in filled_plan
                                if item.get("type") == "attraction"
                            )
                            if has_kids_focused:
                                continue  # Skip - already have kids-focused POI
                    
                    # Soft POI criteria
                    time_min = p.get("time_min", 60)
                    if time_min > 30 or time_min < 10:
                        continue
                    
                    must_see_score = p.get("must_see", p.get("must_see_score", 10))
                    if must_see_score > 7:  # Allow POI with must_see up to 7
                        continue
                    
                    # Check if POI fits in gap
                    # Soft POI duration should fit in gap
                    available_time = gap_minutes
                    if time_min > available_time:
                        continue
                    
                    # Check opening hours at current_end time
                    season = ctx.get("season")
                    date_ctx = ctx  # Full context for opening_hours
                    if not is_open(p, current_end, time_min, season, date_ctx):
                        continue
                    
                    # Add soft POI
                    filled_plan.append({
                        "type": "attraction",
                        "poi": p,
                        "name": poi_name(p),
                        "start_time": minutes_to_time(current_end),
                        "end_time": minutes_to_time(current_end + time_min),
                        "meta": {
                            "experience_role": "gap_filler",
                            "is_culture": bool(is_culture(p)),
                        },
                    })
                    
                    used_poi_ids.add(poi_id(p))
                    current_end += time_min
                    gap_minutes = next_start - current_end
                    soft_filled = True
                    break  # Fill one soft POI per gap
                
                # If still gap >20 min and no soft POI, add free_time (max 40 min)
                if not soft_filled and gap_minutes > 20:
                    free_duration = min(40, gap_minutes)
                    print(f"[GAP FILLING DEBUG] No soft POI - adding free_time ({free_duration} min)", flush=True)
                    filled_plan.append({
                        "type": "free_time",
                        "start_time": minutes_to_time(current_end),
                        "end_time": minutes_to_time(current_end + free_duration),
                        "duration_min": free_duration,
                        "description": "Czas wolny: spacer, kawa, odpoczynek"
                    })
                else:
                    print(f"[GAP FILLING DEBUG] Gap filled with soft POI or gap now <20 min", flush=True)
    
    print(f"[GAP FILLING DEBUG] Finished - returning {len(filled_plan)} items", flush=True)
    return filled_plan
