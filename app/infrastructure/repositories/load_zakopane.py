# type: ignore
# Oryginalny load_zakopane.py - refaktoryzacja type hints w ETAP 3
import pandas as pd
import re
from typing import Optional, Dict
from app.infrastructure.repositories.normalizer import normalize_pois


def _convert_opening_hours_to_json(opening_hours_str: str) -> Optional[Dict[str, str]]:
    """
    Convert string format to JSON dict format.
    
    Input: "mon:8:00-20:00,tue:8:00-20:00,..." or "Sat:15:30-18:00"
    Output: {"mon": "08:00-20:00", "tue": "08:00-20:00", ...} or {"sat": "15:30-18:00"}
    
    Returns None if empty or invalid.
    """
    if not opening_hours_str or not opening_hours_str.strip():
        return None
    
    result = {}
    
    # Pattern: mon:8:00-20:00 or Mon:8:00-20:00 (case insensitive)
    pattern = r'(mon|tue|wed|thu|fri|sat|sun)\s*:\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
    
    for match in re.finditer(pattern, opening_hours_str, re.IGNORECASE):
        day_name = match.group(1).lower()
        start_time = match.group(2)
        end_time = match.group(3)
        
        # Normalize time format to HH:MM
        start_parts = start_time.split(":")
        end_parts = end_time.split(":")
        
        start_normalized = f"{int(start_parts[0]):02d}:{start_parts[1]}"
        end_normalized = f"{int(end_parts[0]):02d}:{end_parts[1]}"
        
        result[day_name] = f"{start_normalized}-{end_normalized}"
    
    return result if result else None


def _convert_seasonal_to_json(seasonal_str: str) -> Optional[Dict[str, str]]:
    """
    Convert string format to JSON dict format.
    
    Input: '"date_from": "06-01","date_to": "09-30"' or similar
    Output: {"date_from": "06-01", "date_to": "09-30"}
    
    Returns None if empty or invalid.
    """
    if not seasonal_str or not seasonal_str.strip():
        return None
    
    # Pattern: "date_from": "06-01" and "date_to": "09-30"
    date_from_match = re.search(r'"date_from"\s*:\s*"(\d{2}-\d{2})"', seasonal_str)
    date_to_match = re.search(r'"date_to"\s*:\s*"(\d{2}-\d{2})"', seasonal_str)
    
    if date_from_match and date_to_match:
        return {
            "date_from": date_from_match.group(1),
            "date_to": date_to_match.group(1)
        }
    
    return None


def load_zakopane_poi(path: str):
    df = pd.read_excel(path)

    print("KOLUMNY:", list(df.columns))

    pois = []

    for _, row in df.iterrows():
        # Convert opening_hours from string to JSON dict
        opening_hours_raw = str(row.get("Opening hours", "")).strip()
        opening_hours_json = _convert_opening_hours_to_json(opening_hours_raw)
        
        # Convert opening_hours_seasonal from string to JSON dict
        seasonal_raw = str(row.get("opening_hours_seasonal", "")).strip()
        seasonal_json = _convert_seasonal_to_json(seasonal_raw)
        
        poi = {
            "ID": str(row.get("ID", "")).strip(),
            "Name": str(row.get("Name", "")).strip(),
            "Description_short": str(row.get("Description_short", "")).strip(),
            "Description_long": str(row.get("Description_long", "")).strip(),
            "Why visit": str(row.get("Why visit", "")).strip(),
            "Opening hours": opening_hours_json,  # Now JSON dict
            "opening_hours_seasonal": seasonal_json,  # Now JSON dict
            "time_min": row.get("time_min"),
            "time_max": row.get("time_max"),
            "Price": row.get("Price"),
            "ticket_normal": row.get("ticket_normal"),
            "ticket_reduced": row.get("ticket_reduced"),
            "Address": str(row.get("Address", "")).strip(),
            "Region": str(row.get("Region", "")).strip(),
            "Lat": row.get("Lat"),
            "Lng": row.get("Lng"),
            "Link do godzin": str(row.get("Link do godzin", "")).strip(),
            "Link do cennika": str(row.get("Link do cennika", "")).strip(),
            "Space": str(row.get("Space", "")).strip(),
            "Intensity": str(row.get("Intensity", "")).strip(),
            "weather_dependency": str(
                row.get("weather_dependency", "")
            ).strip(),
            "popularity_score": row.get("popularity_score"),
            "Must see score": row.get("Must see score"),
            "Peak hours": str(row.get("Peak hours", "")).strip(),
            "recommended_time_of_day": str(
                row.get("recommended_time_of_day", "")
            ).strip(),
            "City": str(row.get("City", "")).strip(),
            "Target group": str(row.get("Target group", "")).strip(),
            "Children's age": str(row.get("Children's age", "")).strip(),
            "Type of attraction": str(
                row.get("Type of attraction", "")
            ).strip(),
            "Activity_style": str(row.get("Activity_style", "")).strip(),
            "crowd_level": str(row.get("crowd_level", "")).strip(),
            "Budget type": str(row.get("Budget type", "")).strip(),
            "Seasonality of attractions": str(
                row.get("Seasonality of attractions", "")
            ).strip(),
            "Pro_tip": str(row.get("Pro_tip", "")).strip(),
            "parking_name": str(row.get("parking_name", "")).strip(),
            "parking_address": str(row.get("parking_address", "")).strip(),
            "parking_lat": row.get("parking_lat"),
            "parking_lng": row.get("parking_lng"),
            "parking_type": str(row.get("parking_type", "")).strip(),
            "parking_walk_time_min": row.get("parking_walk_time_min"),
            "priority_level": str(row.get("priority_level", "")).strip(),
            "kids_only": str(row.get("kids_only", "")).strip(),
            "Tags": str(row.get("Tags", "")).strip(),
        }

        pois.append(poi)

    print(f"ZAŁADOWANO POI: {len(pois)}")

    pois = normalize_pois(pois)

    return pois
