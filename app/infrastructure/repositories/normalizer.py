# type: ignore
# Oryginalny normalizer.py - refaktoryzacja type hints w ETAP 3
import re
import math


# =========================
# Safe helpers
# =========================


def _safe_str(x):
    if x is None:
        return ""
    return str(x).strip()


def _safe_lower(x):
    return _safe_str(x).lower()


def _safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, float) and math.isnan(x):
            return default
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return default


# =========================
# Time parsing
# =========================


def _parse_hhmm(s):
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except (TypeError, ValueError, AttributeError):
        return None


def parse_time_range(raw):
    if not raw:
        return None

    s = raw.replace("–", "-").replace("—", "-")
    m = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", s)
    if not m:
        return None

    a = _parse_hhmm(m.group(1))
    b = _parse_hhmm(m.group(2))
    if a is None or b is None:
        return None

    return (a, b)


def parse_opening_hours(all_raw, seasonal_raw):
    out = {}

    base = parse_time_range(_safe_str(all_raw))
    if base:
        out["all"] = base

    s = _safe_lower(seasonal_raw)

    if not s:
        return out

    for season in ["winter", "spring", "summer", "autumn"]:
        m = re.search(
            season + r"\s*[:\-]?\s*(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})", s
        )
        if m:
            rng = parse_time_range(m.group(1))
            if rng:
                out[season] = rng

    return out


def parse_opening_calendar(p):
    """
    Czyta strukturę:
    date_from, date_to, mon, tue, wed, thu, fri, sat, sun
    i zamienia na listę reguł.
    """
    rules = []

    date_from = p.get("date_from") or p.get("Date from")
    date_to = p.get("date_to") or p.get("Date to")

    def parse_mmdd(s):
        try:
            m, d = str(s).split("-")
            return int(m), int(d)
        except (TypeError, ValueError, AttributeError):
            return None

    df = parse_mmdd(date_from)
    dt = parse_mmdd(date_to)

    if not df or not dt:
        return rules

    dow_map = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }

    hours = {}

    for k, dow in dow_map.items():
        raw = p.get(k)
        if not raw:
            continue

        tr = parse_time_range(str(raw))
        if tr:
            hours[dow] = tr

    if hours:
        rules.append({"date_from": df, "date_to": dt, "hours": hours})

    return rules


# =========================
# Mappings
# =========================

BUDGET_MAP = {
    "tani": 1,
    "budżet": 1,
    "cheap": 1,
    "średni": 2,
    "medium": 2,
    "normal": 2,
    "drogi": 3,
    "drogo": 3,
    "expensive": 3,
}

CROWD_MAP = {
    "brak": 0,
    "niski": 1,
    "mało": 1,
    "średni": 2,
    "umiarkowany": 2,
    "wysoki": 3,
    "tłoczno": 3,
}

WEATHER_MAP = {
    "brak": 0,
    "niska": 1,
    "słaba": 1,
    "średnia": 2,
    "wysoka": 3,
    "duża": 3,
}

ACTIVITY_STYLE_MAP = {
    "relax": "relax",
    "wypoczynek": "relax",
    "spokojny": "relax",
    "balanced": "balanced",
    "zrównoważony": "balanced",
    "aktywny": "active",
    "active": "active",
}


# =========================
# Children age
# =========================


def parse_children_age(age_raw):
    if not age_raw:
        return None, None

    s = _safe_lower(age_raw)

    if "+" in s:
        try:
            return int(s.replace("+", "")), 99
        except (TypeError, ValueError):
            return None, None

    m = re.match(r"(\d+)\s*-\s*(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))

    return None, None


# =========================
# Simple normalizers
# =========================


def normalize_list(raw):
    if not raw:
        return []
    return [x.strip().lower() for x in str(raw).split(",") if x.strip()]


def normalize_budget(raw):
    s = _safe_lower(raw)
    for k, v in BUDGET_MAP.items():
        if k in s:
            return v
    return 2


def normalize_crowd(raw):
    s = _safe_lower(raw)
    for k, v in CROWD_MAP.items():
        if k in s:
            return v
    return 1


def normalize_weather_sensitivity(raw):
    s = _safe_lower(raw)
    for k, v in WEATHER_MAP.items():
        if k in s:
            return v
    return 1


def normalize_activity_style(raw):
    s = _safe_lower(raw)
    for k, v in ACTIVITY_STYLE_MAP.items():
        if k in s:
            return v
    return "balanced"


# =========================
# Space / Intensity
# =========================


def normalize_space(raw):
    s = _safe_lower(raw)
    if "indoor" in s:
        return "indoor"
    if "outdoor" in s:
        return "outdoor"
    return "mixed"


def normalize_intensity(raw):
    s = _safe_lower(raw)
    if "low" in s:
        return "low"
    if "high" in s:
        return "high"
    return "medium"


# =========================
# Seasonality
# =========================


def normalize_seasonality(raw):
    s = _safe_lower(raw)

    if not s or "all_year" in s or "all year" in s:
        return {"winter": 1, "spring": 1, "summer": 1, "autumn": 1}

    out = {"winter": 0, "spring": 0, "summer": 0, "autumn": 0}

    if "winter" in s or "zima" in s:
        out["winter"] = 1
    if "spring" in s or "wiosna" in s:
        out["spring"] = 1
    if "summer" in s or "lato" in s:
        out["summer"] = 1
    if "autumn" in s or "fall" in s or "jesień" in s:
        out["autumn"] = 1

    return out


# =========================
# Priority
# =========================


def normalize_priority(raw):
    if not raw:
        return 0
    s = _safe_lower(raw)
    if "core" in s:
        return 12
    if "secondary" in s:
        return 6
    if "optional" in s:
        return 2
    return _safe_float(s, 0)


# =========================
# Categories & Wow
# =========================


def normalize_poi_category(p):
    t = _safe_lower(p.get("Type of attraction"))
    tags = normalize_list(p.get("Tags"))

    cats = set()

    if any(k in t for k in ["muzeum", "museum", "galeria", "wystaw"]):
        cats |= {"museum", "culture", "indoor"}

    if any(k in t for k in ["zamek", "castle", "fort"]):
        cats |= {"history", "wow"}

    if any(k in t for k in ["park", "dolina", "szlak", "góry", "mountain"]):
        cats |= {"nature", "outdoor"}

    if any(k in t for k in ["termy", "spa", "basen", "aquapark"]):
        cats |= {"water", "relax", "indoor"}

    if "dzieci" in t or "kids" in tags:
        cats |= {"kids"}

    for tag in tags:
        if tag in ["view", "panorama", "widok", "szczyt"]:
            cats |= {"wow"}
        if tag in ["outdoor", "indoor"]:
            cats.add(tag)

    return cats


def compute_wow_score(priority, must_see, cats):
    score = 0.0
    if priority >= 10:
        score += 2
    if must_see >= 7:
        score += 1.5
    if "wow" in cats:
        score += 1.5
    if "kids" in cats:
        score += 0.5
    return min(score, 5.0)


# =========================
# Experience role
# =========================


def normalize_experience_role(p):
    t = _safe_lower(p.get("Type of attraction"))
    tags = normalize_list(p.get("Tags"))

    if any(k in t for k in ["termy", "spa", "basen", "sauna", "wellness"]):
        return "relax"

    if "kulig" in t or "sunset" in tags or "night" in tags:
        return "finale"

    return "core"


def normalize_poi_role(p, experience_role, activity_style, poi_category):
    """
    Kanoniczny typ POI:
    - RELAX: termy/spa/basen itp.
    - BUFFER: krótkie i elastyczne (dopychacz)
    - FILLER: reszta
    """
    # RELAX ma pierwszeństwo
    if experience_role == "relax":
        return "RELAX"

    # BUFFER: krótkie i elastyczne
    tmin = _safe_float(p.get("time_min"), 30)
    tmax = _safe_float(p.get("time_max"), 60)

    tags = set(normalize_list(p.get("Tags")))
    t = _safe_lower(p.get("Type of attraction"))

    buffer_by_time = tmin <= 45 and tmax <= 90
    buffer_by_tags = any(
        k in tags
        for k in ["quick", "buffer", "short", "punkt", "widok", "panorama"]
    )
    buffer_by_type = (
        any(
            k in t
            for k in [
                "punkt widok",
                "platform",
                "wieża",
                "punkt",
                "galeria",
                "muzeum",
            ]
        )
        and tmin <= 60
    )

    # BUFFER nie powinien być typowo "ciężki"
    heavy = ("mountain" in poi_category) or ("szlak" in t) or ("góry" in t)

    if (buffer_by_time or buffer_by_tags or buffer_by_type) and not heavy:
        return "BUFFER"

    return "FILLER"


# =========================
# Main POI normalizer
# =========================


def normalize_poi(p, index):
    children_min, children_max = parse_children_age(p.get("Children's age"))

    priority = normalize_priority(p.get("priority_level"))
    must_see = _safe_float(p.get("Must see score"))

    poi_category = normalize_poi_category(p)
    wow = compute_wow_score(priority, must_see, poi_category)

    opening_hours_text = parse_opening_hours(
        p.get("Opening hours"), p.get("opening_hours_seasonal")
    )

    opening_hours_calendar = parse_opening_calendar(p)

    opening_hours = {
        "text": opening_hours_text,
        "calendar": opening_hours_calendar,
    }
    experience_role = normalize_experience_role(p)
    activity_style = normalize_activity_style(p.get("Activity_style"))
    poi_role = normalize_poi_role(
        p, experience_role, activity_style, poi_category
    )

    return {
        "id": f"poi_{index}",
        "name": _safe_str(p.get("Name")),
        "lat": _safe_float(p.get("Lat")),
        "lng": _safe_float(p.get("Lng")),
        "time_min": int(_safe_float(p.get("time_min"), 30)),
        "time_max": int(_safe_float(p.get("time_max"), 60)),
        "must_see": must_see,
        "popularity": _safe_float(p.get("popularity_score")),
        "priority": priority,
        "target_groups": normalize_list(p.get("Target group")),
        "children_min": children_min,
        "children_max": children_max,
        "type": _safe_lower(p.get("Type of attraction")),
        "tags": normalize_list(p.get("Tags")),
        "experience_role": experience_role,
        "poi_role": poi_role,
        "space": normalize_space(p.get("Space")),
        "intensity": normalize_intensity(p.get("Intensity")),
        "budget_level": normalize_budget(p.get("Budget type")),
        "crowd_level": normalize_crowd(p.get("crowd_level")),
        "weather_sensitivity": normalize_weather_sensitivity(
            p.get("weather_dependency")
        ),
        "season_fit": normalize_seasonality(
            p.get("Seasonality of attractions")
        ),
        "activity_style": activity_style,
        "parking_walk_min": int(
            _safe_float(p.get("parking_walk_time_min"), 5)
        ),
        "poi_category": poi_category,
        "wow_score": wow,
        "recommended_time_of_day": _safe_lower(
            p.get("recommended_time_of_day")
        ),
        "kids_only": _safe_lower(p.get("kids_only")) == "true",
        "opening_hours": opening_hours,
    }


def normalize_pois(pois):
    return [normalize_poi(p, i) for i, p in enumerate(pois)]
