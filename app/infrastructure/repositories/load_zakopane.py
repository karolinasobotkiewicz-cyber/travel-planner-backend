# type: ignore
# Oryginalny load_zakopane.py - refaktoryzacja type hints w ETAP 3
import pandas as pd
import re
import ast
from typing import Optional, Dict, List
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
    DEPRECATED - kept for backward compatibility.
    Use _parse_seasonal_list() for new format.
    
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


def _parse_seasonal_list(seasonal_str: str) -> Optional[List[Dict[str, str]]]:
    """
    Parse new multi-season format (06.02.2026).
    
    Handles pseudo-JSON list format:
    [
      {
        date_from: 01-01,
        date_to: 03-30,
        mon: 08:00-16:00,
        tue: 08:00-16:00,
        ...
      }
    ]
    
    Features:
    - No quotes around keys
    - Missing commas between key:value pairs
    - Single time (14:00) vs range (08:00-16:00)
    - "closed" values
    
    Returns:
    [
      {
        "date_from": "01-01",
        "date_to": "03-30",
        "mon": "08:00-16:00",
        ...
      }
    ]
    """
    if not seasonal_str or not seasonal_str.strip():
        return None
    
    seasonal_str = seasonal_str.strip()
    
    # Check if it's a list format (starts with '[')
    if not seasonal_str.startswith('['):
        return None
    
    seasons = []
    
    # Extract individual season objects (split by '},{')
    # Pattern: Find content between { and }
    season_pattern = r'\{([^{}]+)\}'
    season_matches = re.findall(season_pattern, seasonal_str, re.DOTALL)
    
    for season_content in season_matches:
        season_dict = {}
        
        # Extract key:value pairs
        # Pattern: key: value with newline or comma as separator
        # Simpler approach: match any key:value where value ends at newline or comma
        # This handles:
        # - mon:08:00-16:00\ntue:08:00-16:00 (no comma, newline separator)
        # - date_from: 01-01, (comma separator)
        # - leading spaces:    mon:08:00-16:00
        # - time colons: 08:00-16:00 (value contains ':')
        pair_pattern = r'([a-z_]+)\s*:\s*([^\n,]+)'
        
        for match in re.finditer(pair_pattern, season_content, re.IGNORECASE):
            key = match.group(1).strip()
            value = match.group(2).strip().rstrip(',')
            
            # Clean up value
            if value and value != 'nan':
                season_dict[key] = value
        
        if season_dict:
            seasons.append(season_dict)
    
    return seasons if seasons else None


def load_zakopane_poi(path: str):
    df = pd.read_excel(path)

    print("KOLUMNY:", list(df.columns))

    # CLIENT DATA UPDATE (05.02.2026): Handle zakopane2.xlsx structure
    # Column 1 (index 1) is Name but labeled as numeric 0
    name_col = df.columns[1] if len(df.columns) > 1 else "Name"

    pois = []

    for idx, row in df.iterrows():
        # CLIENT DATA UPDATE (05.02.2026): Generate ID if missing (all NaN in new file)
        poi_id = str(row.get("ID", "")).strip()
        if not poi_id or poi_id == "nan":
            poi_id = f"poi_{int(idx) + 1}"  # poi_1, poi_2, ... poi_36 (1-indexed)
        
        # CLIENT DATA UPDATE (05.02.2026): Get name from column 1
        poi_name = str(row.get(name_col, "")).strip()
        
        # CLIENT DATA UPDATE (05.02.2026): Parse Tags (comma-separated string)
        tags_str = str(row.get("Tags", "")).strip()
        tags_list = []
        if tags_str and tags_str != "nan":
            # Split by comma, strip whitespace, filter empty strings
            tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        
        # CLIENT DATA UPDATE (05.02.2026): Parse Target group to list
        target_group_raw = str(row.get("Target group", "")).strip()
        target_groups_list = []
        if target_group_raw and target_group_raw != "nan":
            # Split by comma, strip whitespace
            target_groups_list = [
                t.strip() 
                for t in target_group_raw.split(",") 
                if t.strip() and t.strip() != "nan"
            ]
        
        # Convert opening_hours from string to JSON dict
        opening_hours_raw = str(row.get("Opening hours", "")).strip()
        opening_hours_json = _convert_opening_hours_to_json(opening_hours_raw)
        
        # CLIENT DATA UPDATE (06.02.2026): Parse opening_hours_seasonal 
        # Try new list format first, fallback to old dict format
        seasonal_raw = str(row.get("opening_hours_seasonal", "")).strip()
        seasonal_json = _parse_seasonal_list(seasonal_raw)  # New format (list)
        
        if seasonal_json is None:
            # Backward compatibility - try old format (single dict)
            old_format = _convert_seasonal_to_json(seasonal_raw)
            if old_format:
                seasonal_json = [old_format]  # Convert dict to list for consistency
        
        # CLIENT DATA UPDATE (05.02.2026): Normalize priority_level (handle "\nsecondary\n" variants)
        priority_raw = str(row.get("priority_level", "optional")).strip().lower()
        priority_level = priority_raw if priority_raw else "optional"
        
        poi = {
            "id": poi_id,  # Lowercase for consistency
            "ID": poi_id,  # Keep uppercase for backward compat
            "name": poi_name,  # Lowercase for consistency
            "Name": poi_name,  # Keep uppercase for backward compat
            "tags": tags_list,  # CLIENT DATA UPDATE: New field - list of tags
            "Description_short": str(row.get("Description_short", "")).strip(),
            "Description_long": str(row.get("Description_long", "")).strip(),
            "Why visit": str(row.get("Why visit", "")).strip(),
            "Opening hours": opening_hours_json,  # Now JSON dict
            "opening_hours_seasonal": seasonal_json,  # Now JSON dict
            "time_min": row.get("time_min"),
            "time_max": row.get("time_max"),
            "Price": row.get("Price"),
            "ticket_price": row.get("ticket_normal"),  # CLIENT DATA UPDATE: For budget scoring
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
            "Target group": target_groups_list,  # CLIENT DATA UPDATE: Now list
            "target_groups": target_groups_list,  # Normalized key - list
            "Children's age": str(row.get("Children's age", "")).strip(),
            "Type of attraction": str(
                row.get("Type of attraction", "")
            ).strip(),
            "type_of_attraction": str(row.get("Type of attraction", "")).strip(),  # Normalized
            "Activity_style": str(row.get("Activity_style", "")).strip(),
            "crowd_level": str(row.get("crowd_level", "")).strip(),
            "Budget type": str(row.get("Budget type", "")).strip(),
            "budget_level": str(row.get("Budget type", "")).strip(),  # For scoring
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
            "priority_level": priority_level,  # CLIENT DATA UPDATE: Normalized
            "kids_only": str(row.get("kids_only", "")).strip(),
            "Tags": tags_str,  # Original string for backward compat
        }

        pois.append(poi)

    print(f"ZALADOWANO POI: {len(pois)}")

    pois = normalize_pois(pois)

    return pois
