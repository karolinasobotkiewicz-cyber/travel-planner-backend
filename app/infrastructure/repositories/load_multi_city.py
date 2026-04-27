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
from app.infrastructure.repositories.normalizer import normalize_priority


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
        poi_dict = {
            # Identity
            "id": str(row.get('ID', f"poi_{idx}")),
            "type": "poi",  # Discriminator for engine
            "name": row.get('Name', ''),
            "city": row.get('City', ''),
            
            # Location
            "lat": float(row.get('Lat', 0.0)),
            "lng": float(row.get('Lng', 0.0)),
            "address": row.get('Address', ''),
            
            # Description
            "description_short": row.get('Description_Short', ''),
            "description_long": row.get('Description_Long', ''),
            
            # Timing
            "duration_min": int(row.get('Duration_Min', 30)),
            "duration_max": int(row.get('Duration_Max', 60)),
            "best_time": row.get('Best_Time', 'any'),
            
            # Opening hours
            "opening_hours": row.get('Opening_Hours', ''),
            "opening_days": row.get('Opening_Days', 'Mon-Sun'),
            
            # Popularity & scoring
            "popularity_score": float(row.get('Popularity_Score', 0.5)),
            "priority_level": normalize_priority(row.get('Priority_Level', 'medium')),
            
            # Categorization
            "category": row.get('Category', 'attraction'),
            "subcategory": row.get('Subcategory', ''),
            "tags": str(row.get('Tags', '')).split(',') if pd.notna(row.get('Tags')) else [],
            
            # Target groups
            "target_group": str(row.get('Target_Group', 'all')).split(',') if pd.notna(row.get('Target_Group')) else ['all'],
            "family_friendly": _parse_bool(row.get('Family_Friendly', True)),
            "child_age_min": int(row.get('Child_Age_Min', 0)) if pd.notna(row.get('Child_Age_Min')) else None,
            
            # Accessibility
            "wheelchair_accessible": _parse_bool(row.get('Wheelchair_Accessible', False)),
            "dog_friendly": _parse_bool(row.get('Dog_Friendly', False)),
            
            # Costs
            "cost_level": int(row.get('Cost_Level', 1)),
            "ticket_price": float(row.get('Ticket_Price', 0.0)) if pd.notna(row.get('Ticket_Price')) else None,
            "ticket_required": _parse_bool(row.get('Ticket_Required', False)),
            "free_admission": _parse_bool(row.get('Free_Admission', False)),
            
            # Weather & season
            "indoor": _parse_bool(row.get('Indoor', False)),
            "outdoor": _parse_bool(row.get('Outdoor', True)),
            "season": row.get('Season', 'all'),
            "weather_dependent": _parse_bool(row.get('Weather_Dependent', False)),
            
            # Intensity & crowd
            "intensity_level": int(row.get('Intensity_Level', 1)),
            "crowd_level": int(row.get('Crowd_Level', 1)),
            "quiet": _parse_bool(row.get('Quiet', False)),
            
            # Parking & transport
            "parking_available": _parse_bool(row.get('Parking_Available', True)),
            "parking_free": _parse_bool(row.get('Parking_Free', False)),
            "parking_cost": float(row.get('Parking_Cost', 0.0)) if pd.notna(row.get('Parking_Cost')) else None,
            "public_transport": _parse_bool(row.get('Public_Transport', True)),
            
            # Photos & media
            "photo_url": row.get('Photo_URL', ''),
            "website": row.get('Website', ''),
            
            # Tips & warnings
            "pro_tip": row.get('Pro_Tip', ''),
            "warning": row.get('Warning', ''),
            
            # Nearby services
            "restaurant_nearby": _parse_bool(row.get('Restaurant_Nearby', False)),
            "cafe_nearby": _parse_bool(row.get('Cafe_Nearby', False)),
            "wc_nearby": _parse_bool(row.get('WC_Nearby', False)),
            
            # Energy impact (Etap 2 - multi-day planning)
            "energy_cost": int(row.get('Intensity_Level', 1)),  # Map intensity to energy cost
            
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
