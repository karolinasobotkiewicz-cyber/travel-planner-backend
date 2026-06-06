"""
Seasonality filtering module.

Hard filter: excludes POI completely if outside current season.
"""

import re
from datetime import datetime


def derive_season(date):
    """
    Derive season from date.
    
    Args:
        date: datetime object, date object, tuple (year, month, day[, weekday]), or string "YYYY-MM-DD"
    
    Returns:
        str: "winter", "spring", "summer", or "fall"
    """
    if isinstance(date, str):
        # Parse if string (format: YYYY-MM-DD)
        date = datetime.strptime(date, "%Y-%m-%d")
    elif isinstance(date, tuple):
        # Handle tuple (year, month, day) or (year, month, day, weekday)
        if len(date) == 4:
            year, month, day, weekday = date
        else:
            year, month, day = date
        date = datetime(year, month, day)
    
    month = date.month
    
    if 3 <= month <= 5:
        return "spring"
    elif 6 <= month <= 8:
        return "summer"
    elif 9 <= month <= 11:
        return "fall"
    else:  # 12, 1, 2
        return "winter"


def filter_by_season(pois, current_date):
    """
    Filter POI by seasonality - HARD FILTER (exclude completely if not in season).
    
    Args:
        pois: List of POI dicts with optional 'seasonality' field
        current_date: datetime object representing current date
    
    Returns:
        list: Filtered POI list (excludes POI outside season)
    """
    current_season = derive_season(current_date)
    # derive_season() returns "fall"; the normalized season_fit dict and the POI data
    # use "autumn". Map between them so both representations match.
    _SEASON_KEY = {"winter": "winter", "spring": "spring", "summer": "summer", "fall": "autumn"}
    season_key = _SEASON_KEY.get(current_season, current_season)

    filtered_pois = []

    for poi in pois:
        # FIX #163 (06.06.2026 - CLIENT FEEDBACK JSON2): use the authoritative normalized
        # `season_fit` dict ({"winter":1,"spring":0,...}). The old code read poi["seasonality"],
        # but normalize_poi() drops that key and only keeps season_fit — so the filter was a
        # silent no-op and summer-only POIs (e.g. "Kąpielisko na Polanie Szymoszkowej")
        # appeared in winter plans. season_fit with all-year data is all 1s (always passes).
        season_fit = poi.get("season_fit")
        if isinstance(season_fit, dict) and season_fit:
            if season_fit.get(season_key, 0):
                filtered_pois.append(poi)
            # else: HARD FILTER — POI not available in the current season
            continue

        # Legacy fallback (e.g. trails expose a "seasonality" list/string).
        seasonality = poi.get("seasonality", [])
        if not seasonality:
            # No seasonality info → assume available all year.
            filtered_pois.append(poi)
            continue
        if isinstance(seasonality, str):
            # Split multi-season strings like "winter, summer" / "spring,summer,autumn".
            seasonality = [s.strip() for s in re.split(r"[,/;]", seasonality) if s.strip()]
        seasonality = [s.lower() for s in seasonality]
        # Treat "fall"/"autumn" and "all_year" as equivalents.
        if (
            current_season in seasonality
            or season_key in seasonality
            or "all_year" in seasonality
            or "all year" in seasonality
        ):
            filtered_pois.append(poi)
        # Else: HARD FILTER - exclude this POI

    return filtered_pois
