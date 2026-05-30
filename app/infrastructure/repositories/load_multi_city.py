"""
ETAP 3 PHASE 7: Multi-City POI Loader

Load POI from multiple cities in Excel cache (multi_city_attractions.xlsx).
Used for destination clusters like Trójmiasto, Kotlina Kłodzka, Karkonosze.

Usage:
    from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
    
    poi_list = load_multi_city_poi(
        excel_path='data/multi_city_attractions.xlsx',
        cities=['Gdańsk', 'Gdynia', 'Sopot']
    )
    # Returns list of POI dicts for all 3 cities combined
"""
import pandas as pd
from typing import List, Dict, Any
# FIX #110 (29.05.2026): Auto-validate Excel on load — detects tag mismatch, Polish values, etc.
from app.infrastructure.repositories.excel_validator import validate_excel

# FIX #38 (20.05.2026): Priority level mapping for multi_city Excel
# multi_city_attractions.xlsx uses 'high'/'medium'/'low' naming scheme
# Engine's calculate_priority_bonus() expects 'core'/'secondary'/'optional' strings
# normalize_priority('high') = 0 (BUG) → 'high' must map to 'core' string directly
_PRIORITY_LEVEL_MAP = {
    'high': 'core',       # +25 bonus in calculate_priority_bonus()
    'medium': 'secondary', # +10 bonus
    'low': 'optional',    # 0 bonus (filler)
    # Passthrough: Excel may already store engine-compatible values
    'core': 'core',
    'secondary': 'secondary',
    'optional': 'optional',
}

_CROWD_LEVEL_MAP = {
    'low': 1,
    'medium': 2,
    'high': 3,
}

def _map_priority_level(raw) -> str:
    """Map multi_city priority strings to engine-compatible strings."""
    s = str(raw).strip().lower() if raw else 'optional'
    return _PRIORITY_LEVEL_MAP.get(s, 'optional')

def _map_crowd_level(raw) -> int:
    """Map multi_city crowd strings to int (1=low, 2=medium, 3=high)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 1
    s = str(raw).strip().lower()
    return _CROWD_LEVEL_MAP.get(s, 1)

def _map_intensity_level(raw) -> int:
    """Map multi_city intensity strings to int."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 1
    s = str(raw).strip().lower()
    return {'low': 1, 'medium': 2, 'high': 3}.get(s, 1)


def _safe_str(val, default='') -> str:
    """Return val as string, or default if val is None/NaN."""
    if val is None:
        return default
    if isinstance(val, float) and pd.isna(val):
        return default
    return str(val).strip() if str(val).strip() else default

def _safe_child_age(raw):
    """Safely parse child age from Excel - returns None if not a valid int."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, pd.Timestamp):
        return None
    s = str(raw).strip()
    if not s or s == '-':
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _safe_float(raw, default=None):
    """Safely parse float from Excel - returns default if value is not a valid number (e.g. '-', '', NaN)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    s = str(raw).strip()
    if not s or s == '-':
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def load_multi_city_poi(excel_path: str, cities: List[str]) -> List[Dict[str, Any]]:
    """
    Load POI from multiple cities in Excel cache.
    
    Args:
        excel_path: Path to multi_city_attractions.xlsx
        cities: List of city names to load (e.g., ['Gdańsk', 'Gdynia', 'Sopot'])
    
    Returns:
        List of POI dicts compatible with engine.py
    
    Example:
        >>> poi = load_multi_city_poi('data/multi_city_attractions.xlsx', ['Gdańsk', 'Gdynia'])
        >>> len(poi)
        103  # Gdańsk (70) + Gdynia (33)
    
    Raises:
        FileNotFoundError: If Excel file not found
        ValueError: If no cities found in Excel
    """
    # Read Excel (single sheet "All Cities" in Phase 6)
    try:
        df = pd.read_excel(excel_path, sheet_name='All Cities')
    except FileNotFoundError:
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    except Exception as e:
        raise ValueError(f"Failed to read Excel file {excel_path}: {e}")

    # FIX #110 (29.05.2026): Validate Excel data quality before processing.
    # Runs once per load — prints warnings/errors to console without blocking.
    _city_label = ", ".join(cities) if cities else ""
    _val_report = validate_excel(
        excel_path=excel_path,
        city_name=_city_label,
        sheet_name='All Cities',
    )
    if _val_report.has_errors or _val_report.warnings:
        _val_report.print_summary()

    # Filter by cities
    if 'City' not in df.columns:
        raise ValueError(f"Excel file missing 'City' column: {excel_path}")
    
    # Case-insensitive city matching
    cities_lower = [city.lower() for city in cities]
    df_filtered = df[df['City'].str.lower().isin(cities_lower)]
    
    if len(df_filtered) == 0:
        print(f"[WARNING] No POI found for cities: {cities}")
        return []
    
    print(f"[load_multi_city_poi] Filtering {len(df)} rows → {len(df_filtered)} rows (cities: {cities})")
    
    # Convert to list of dicts compatible with engine.py
    poi_list = []
    
    for idx, row in df_filtered.iterrows():
        # Skip rows with missing critical data
        if pd.isna(row.get('Name')) or pd.isna(row.get('Lat')) or pd.isna(row.get('Lng')):
            continue
        
        # Build POI dict (same format as load_zakopane.py)
        _tmin = int(row.get('time_min', 30)) if pd.notna(row.get('time_min')) else 30
        _tmax = int(row.get('time_max', 60)) if pd.notna(row.get('time_max')) else 60
        _priority_str = _map_priority_level(row.get('priority_level', 'medium'))
        _category = row.get('Type of attraction', row.get('Category', 'attraction'))
        _pop_score = float(row.get('popularity_score', 0.5)) if pd.notna(row.get('popularity_score')) else 0.5
        _name = row.get('Name', '')
        # FIX #75: opening_hours = '{}' is a truthy string → engine treats POI as closed.
        # Clear it so is_open() sees both oh=None and oh_seasonal=None → returns True (always open).
        _oh_raw = row.get('Opening hours', None)
        _oh = str(_oh_raw).strip() if _oh_raw is not None and pd.notna(_oh_raw) else None
        _oh = None if not _oh or _oh in ('{}', '[]', 'None', 'nan', '') else _oh

        _raw_id = row.get('ID')
        _id = str(_raw_id) if _raw_id is not None and pd.notna(_raw_id) and str(_raw_id).strip() not in ('', 'nan') else f"poi_{idx}"

        poi_dict = {
            # Identity
            "id": _id,
            "type": "poi",  # Discriminator for engine
            "name": _name,
            "Name": _name,  # FIX #75: engine uses p.get("Name", "UNKNOWN") in several places
            "city": row.get('City', ''),
            
            # Location
            "lat": float(row.get('Lat', 0.0)),
            "lng": float(row.get('Lng', 0.0)),
            "address": _safe_str(row.get('Address')),
            
            # Description
            "description_short": _safe_str(row.get('Description_short')),
            "description_long": _safe_str(row.get('Description_long')),
            
            # Timing  # FIX #75: add time_min/time_max (engine uses these; duration_min/max kept for compat)
            "duration_min": _tmin,
            "duration_max": _tmax,
            "time_min": _tmin,
            "time_max": _tmax,
            "best_time": _safe_str(row.get('recommended_time_of_day'), 'any'),
            
            # Opening hours  # FIX #75: '{}' → None so all multi_city POIs pass is_open() check
            "opening_hours": _oh,
            "opening_days": _safe_str(row.get('opening_days'), 'Mon-Sun'),
            
            # Popularity & scoring  # FIX #75: add "popularity" alias used by classify_poi()
            "popularity_score": _pop_score,
            "popularity": _pop_score,
            "priority_level": _priority_str,
            "priority": _priority_str,  # FIX #75: classify_poi() reads p.get("priority", "optional")
            
            # Categorization  # FIX #75: add type_of_attraction aliases used by engine scoring
            "category": _category,
            "type_of_attraction": _category,
            "Type of attraction": _category,
            "subcategory": _safe_str(row.get('Activity_style', row.get('Subcategory'))),
            "tags": str(row.get('Tags', '')).split(',') if pd.notna(row.get('Tags')) else [],
            
            # Target groups  # FIX #38: Excel uses 'Target group' (with space)
            "target_group": str(row.get('Target group', 'all')).split(',') if pd.notna(row.get('Target group')) else ['all'],
            "family_friendly": _parse_bool(row.get('Family_Friendly', True)),
            "child_age_min": _safe_child_age(row.get("Children's age")),
            
            # Accessibility
            "wheelchair_accessible": _parse_bool(row.get('Wheelchair_Accessible', False)),
            "dog_friendly": _parse_bool(row.get('Dog_Friendly', False)),
            
            # Costs  # FIX #38: Excel uses ticket_normal/ticket_reduced, not Ticket_Price
            # FIX #68/#71 (03.06.2026): Add ticket_normal/ticket_reduced/free_entry keys
            # so engine.py calculate_group_cost() and plan_service._estimate_cost() can
            # distinguish genuinely-free POIs (ticket=0) from no-data POIs (ticket=None).
            # Previously only 'ticket_price' key was set → both functions saw None → 50 PLN fallback.
            "cost_level": int(row.get('Cost_Level', 1)) if pd.notna(row.get('Cost_Level')) else 1,
            "ticket_price": _safe_float(row.get('ticket_normal')),
            "ticket_normal": _safe_float(row.get('ticket_normal')),
            "ticket_reduced": _safe_float(row.get('ticket_reduced')),
            "ticket_required": _parse_bool(row.get('Ticket_Required', False)),
            "free_admission": _parse_bool(row.get('Free_Admission', False)),
            "free_entry": _parse_bool(row.get('Free_Admission', False)),  # FIX #68/#71: alias for engine.py
            
            # Weather & season  # FIX #38: Excel uses 'weather_dependency', 'Seasonality of attractions'
            "indoor": str(row.get('Space', '')).strip().lower() == 'indoor',
            "outdoor": str(row.get('Space', '')).strip().lower() in ('outdoor', 'mixed', ''),
            "season": _safe_str(row.get('Seasonality of attractions', row.get('Season')), 'all'),
            "weather_dependent": str(row.get('weather_dependency', 'all_weather')).strip().lower() not in ('all_weather', 'all weather', ''),
            
            # Intensity & crowd  # FIX #38: Excel uses string values for crowd_level and Intensity
            "intensity_level": _map_intensity_level(row.get('Intensity', row.get('Intensity_Level'))),
            "crowd_level": _map_crowd_level(row.get('crowd_level')),
            "quiet": _parse_bool(row.get('Quiet', False)),
            
            # Parking & transport
            "parking_available": _parse_bool(row.get('Parking_Available', True)),
            "parking_free": _parse_bool(row.get('Parking_Free', False)),
            "parking_cost": float(row.get('Parking_Cost', 0.0)) if pd.notna(row.get('Parking_Cost')) else None,
            "public_transport": _parse_bool(row.get('Public_Transport', True)),
            
            # Photos & media
            "photo_url": _safe_str(row.get('Photo_URL')),
            "website": _safe_str(row.get('Website')),
            
            # Tips & warnings  # FIX #38: Excel uses 'Pro_tip' (not Pro_Tip)
            "pro_tip": _safe_str(row.get('Pro_tip')),
            "warning": _safe_str(row.get('Warning')),
            
            # Nearby services
            "restaurant_nearby": _parse_bool(row.get('Restaurant_Nearby', False)),
            "cafe_nearby": _parse_bool(row.get('Cafe_Nearby', False)),
            "wc_nearby": _parse_bool(row.get('WC_Nearby', False)),
            
            # Energy impact (Etap 2 - multi-day planning)
            "energy_cost": _map_intensity_level(row.get('Intensity', row.get('Intensity_Level', 1))),
            
            # Booking
            "booking_required": _parse_bool(row.get('Booking_Required', False)),
            "booking_url": row.get('Booking_URL', ''),
        }
        
        poi_list.append(poi_dict)
    
    print(f"[load_multi_city_poi] Loaded {len(poi_list)} POI from cities: {cities}")
    print(f"  City breakdown:")
    for city in cities:
        city_count = len([p for p in poi_list if p['city'].lower() == city.lower()])
        print(f"    - {city}: {city_count} POI")
    
    return poi_list


def _parse_bool(value: Any) -> bool:
    """Parse boolean from Excel (handles True, False, 1, 0, 'Yes', 'No')."""
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ['true', 'yes', '1', 'tak']
    return False
