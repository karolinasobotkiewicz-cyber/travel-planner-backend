# type: ignore
import math
from math import radians, sin, cos, sqrt, atan2

from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.domain.planner.opening_hours_parser import is_poi_open_at_time
from app.domain.scoring import (
    calculate_family_score,
    calculate_budget_score,
    calculate_crowd_score,
    calculate_body_transition_score,
    get_next_body_state,
)
from app.domain.scoring.preferences import calculate_preference_score, calculate_priority_bonus
from app.domain.scoring.travel_style import calculate_travel_style_score
from app.domain.scoring.space_scoring import calculate_space_score
from app.domain.scoring.weather_scoring import calculate_weather_dependency_score
from app.domain.scoring.type_matching import calculate_type_matching_score
from app.domain.scoring.time_of_day_scoring import calculate_time_of_day_score
from app.domain.filters.seasonality import filter_by_season

# =========================
# Config
# =========================

DAY_START = "09:00"
DAY_END = "19:00"

LUNCH_TARGET = "13:00"
LUNCH_EARLIEST = "12:00"
LUNCH_LATEST = "14:30"
LUNCH_DURATION_MIN = 40

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

    # bazowe
    score += safe_float(p.get("must_see")) * 2.0
    score += safe_float(p.get("priority"))

    # dopasowanie - existing modules
    score += calculate_family_score(p, user)
    score += calculate_budget_score(p, user)
    score += calculate_crowd_score(p, user, current_time_minutes=now)  # Added current_time for peak_hours

    # ETAP 1 ROZSZERZONY - preferences + travel_style
    score += calculate_preference_score(p, user)
    score += calculate_travel_style_score(p, user)
    
    # FIX #6 (02.02.2026): Priority_level bonus (core: +30, secondary: +10, optional: 0)
    score += calculate_priority_bonus(p, user)
    
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
# Main planner
# =========================


def build_day(pois, user, context, day_start=None, day_end=None):
    """
    Build daily plan from POIs.
    
    Args:
        pois: List of POI dicts
        user: User dict (preferences, target_group, etc.)
        context: Context dict (season, date, weather, etc.)
        day_start: Start time string "HH:MM" (default: DAY_START global)
        day_end: End time string "HH:MM" (default: DAY_END global)
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

    plan = [{"type": "accommodation_start", "time": start_time_str}]

    energy = GROUP_DAILY_ENERGY[user["target_group"]]
    fatigue = 0
    used = set()
    last_poi = None

    # FIX #7 (02.02.2026): Track attraction counts for limits
    attraction_count = 0
    core_attraction_count = 0
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

    while now < end:
        # === LUNCH CHECKPOINT ===
        if not lunch_done:
            lunch_target = time_to_minutes(LUNCH_TARGET)
            lunch_latest = time_to_minutes(LUNCH_LATEST)

            # jezeli po 13:00 lub przeskocym 14:30 -> lunch teraz
            if now >= lunch_target or now + 60 > lunch_latest:
                plan.append(
                    {
                        "type": "lunch_break",
                        "start_time": minutes_to_time(now),
                        "end_time": minutes_to_time(
                            min(end, now + LUNCH_DURATION_MIN)
                        ),
                        "duration_min": LUNCH_DURATION_MIN,
                        "suggestions": ["Lunch", "Restauracja", "Odpoczynek"],
                    }
                )
                now += LUNCH_DURATION_MIN
                lunch_done = True
                fatigue = max(0, fatigue - 2)
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
            
            # FIX #7: Check core POI limit
            is_core = str(p.get("priority_level", "")).strip().lower() == "core"
            if is_core and core_attraction_count >= limits["core_max"]:
                continue  # Skip - too many core POI already

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
            # Old: 22 min = -2.2 penalty (too weak)
            # New: 22 min = -11 penalty (strong preference for nearby)
            score -= travel * 0.5

            if score > best_score:
                best = p
                best_score = score
                best_travel = travel
                best_duration = duration
        
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
                    
                    plan.append({
                        "type": "free_time",
                        "start_time": minutes_to_time(now),
                        "end_time": minutes_to_time(now + free_duration),
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

        if now + transfer_time + best_duration > end:
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

        plan.append(
            {
                "type": "attraction",
                "poi": best,  # Całe POI dla PlanService
                "name": poi_name(best),
                "start_time": minutes_to_time(now),
                "end_time": minutes_to_time(now + best_duration),
                "meta": {
                    "experience_role": best.get("experience_role"),
                    "is_culture": bool(is_culture(best)),
                    "body_state_after": get_next_body_state(best, body_state),
                },
            }
        )

        now += best_duration
        energy -= energy_cost(best, best_duration, ctx)
        fatigue += 1
        used.add(poi_id(best))
        last_poi = best
        
        # FIX #7 (02.02.2026): Update attraction counters
        attraction_count += 1
        is_core_poi = str(best.get("priority_level", "")).strip().lower() == "core"
        if is_core_poi:
            core_attraction_count += 1
        print(f"[LIMITS] Added attraction: {attraction_count}/{limits['hard']} total, {core_attraction_count}/{limits['core_max']} core")

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
                    is_core_soft = str(p.get("priority_level", "")).strip().lower() == "core"
                    if is_core_soft:
                        core_attraction_count += 1
                    print(f"[LIMITS] Added soft POI: {attraction_count}/{limits['hard']} total, {core_attraction_count}/{limits['core_max']} core")
                    
                    soft_filled = True
                    break  # Fill one soft POI per gap
                
                # If no soft POI fits, add free_time (max 40 min)
                if not soft_filled and gap_duration > 20:
                    free_duration = min(40, gap_duration)
                    plan.append({
                        "type": "free_time",
                        "start_time": minutes_to_time(now),
                        "end_time": minutes_to_time(now + free_duration),
                        "duration_min": free_duration,
                        "description": "Czas wolny: spacer, kawa, odpoczynek"
                    })
                    now += free_duration
        else:
            culture_streak = 0

        # update body
        body_state = get_next_body_state(best, body_state)

        # finale lock
        if is_finale(best):
            finale_done = True

    plan.append({"type": "accommodation_end", "time": minutes_to_time(end)})
    
    # NOTE: Gap filling moved to PlanService (after parking/transit timing adjustments)
    # This ensures gaps are detected AFTER all time shifts from parking
    
    return plan


def fill_plan_gaps(plan, pois, used_poi_ids, ctx):
    """
    Post-process plan to fill gaps >20 min between attractions.
    Client requirement: gaps should be filled with soft POI or free_time (max 40 min).
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
