# type: ignore
import math

from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.domain.planner.opening_hours_parser import is_poi_open_at_time
from app.domain.scoring import (
    calculate_family_score,
    calculate_budget_score,
    calculate_crowd_score,
    calculate_body_transition_score,
    get_next_body_state,
)
from app.domain.scoring.preferences import calculate_preference_score
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
    if not a or not b:
        return 0

    dist = distance_km(a, b)
    transport = context.get("transport", "car")

    if transport == "walk":
        speed = 4
    elif transport == "public":
        speed = 18
    else:
        speed = 40

    return int((dist / speed) * 60)


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
    }


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
    
    Uses opening_hours_parser to validate:
    - Seasonal date ranges (e.g., "date_from": "06-01", "date_to": "09-30")
    - Weekday hours (e.g., mon:9:00-17:00, Sat:15:30-18:00)
    
    Args:
        p: POI dict with "opening_hours" field
        now: Start time in minutes since midnight
        duration: Visit duration in minutes
        season: Season string (unused, kept for compatibility)
        context: Context dict with "date" = (year, month, day, weekday)
    
    Returns:
        True if POI is open and visit fits within hours
        False otherwise (including off-season)
    """
    oh = p.get("opening_hours", "")
    
    # If no opening_hours or empty string, assume always open
    if not oh or (isinstance(oh, str) and oh.strip() == ""):
        return True
    
    # Extract date info from context
    if not context or "date" not in context:
        # No date context - use legacy simple validation
        day_start = time_to_minutes("09:00")
        day_end = time_to_minutes("20:00")
        return (now >= day_start) and (now < day_end)
    
    # Parse context date
    year, month, day, weekday = context["date"]
    current_date = (year, month, day)
    
    # Use opening_hours_parser for proper validation
    return is_poi_open_at_time(
        opening_hours_str=oh,
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

        best = None
        best_score = -9999
        best_travel = 0
        best_duration = 0

        for p in pois:
            if poi_id(p) in used:
                continue

            travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
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

            # kara za dojazdy
            score -= travel * 0.1

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
                    
                    # Soft POI criteria
                    if p.get("intensity") != "low":
                        continue
                    if p.get("time_min", 60) > 30:  # Max 30 min
                        continue
                    if p.get("must_see", 0) > 2:  # Low priority
                        continue
                    
                    travel = travel_time_minutes(last_poi, p, ctx) if last_poi else 0
                    start_time = now + travel
                    
                    if start_time >= end:
                        continue
                    
                    duration = min(p.get("time_min", 15), remaining_time - travel)
                    if duration < 10:  # Too short
                        continue
                    
                    if not is_open(p, start_time, duration, ctx["season"], ctx):
                        continue
                    
                    # Simple scoring for soft POI
                    score = 10 - travel * 0.5  # Prefer nearby
                    
                    if score > soft_score:
                        soft_best = p
                        soft_score = score
                        soft_duration = duration
                
                if soft_best:
                    # Found soft POI - add it
                    best = soft_best
                    best_score = soft_score
                    best_travel = travel_time_minutes(last_poi, best, ctx) if last_poi else 0
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

        # update kultur
        if is_culture(best):
            culture_streak += 1
        else:
            culture_streak = 0

        # update body
        body_state = get_next_body_state(best, body_state)

        # finale lock
        if is_finale(best):
            finale_done = True

    plan.append({"type": "accommodation_end", "time": minutes_to_time(end)})
    return plan
