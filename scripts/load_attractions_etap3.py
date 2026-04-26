"""
ETAP 3 - Attractions Loader

Load multi-city attractions from Excel (Planer - miasta atrakcje.xlsx) into POI repository.

Expected: 671 POI across 15 cities

OUTPUT: Excel cache (POI repository still Excel-backed in ETAP 3)
        NOT to database - attractions remain in poi_repository.py

USAGE:
    cd travel-planner-backend
    python scripts/load_attractions_etap3.py
"""

import sys
import os
from pathlib import Path
import pandas as pd
import uuid
import logging
import json

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root.parent))

from scripts.data_mappings import (
    map_priority_level,
    parse_opening_hours_seasonal,
    clean_string,
    validate_gps_poland,
    safe_float,
    safe_int,
    log_mapping_stats,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_uuid(name: str, city: str, lat: float) -> str:
    """
    Generate deterministic UUID for attraction.
    
    Uses: name + city + lat to ensure uniqueness.
    """
    namespace = uuid.NAMESPACE_DNS
    unique_str = f"{name.lower().strip()}_{city.lower().strip()}_{lat}"
    return str(uuid.uuid5(namespace, unique_str))


def parse_tags(value: str) -> list:
    """
    Parse comma-separated tags into list.
    
    Args:
        value: String from Excel (e.g., 'historic_building,museum')
    
    Returns:
        List of cleaned tags
    """
    if not value or str(value).lower() == 'nan':
        return []
    
    # Split by comma and clean
    tags = [clean_string(t) for t in str(value).split(',')]
    return [t for t in tags if t]  # Remove empty


def parse_target_group(value: str) -> list:
    """
    Parse comma-separated target groups into list.
    
    CRITICAL: Excel column name has TRAILING SPACE: "Target group "
    
    Args:
        value: String from Excel (e.g., 'solo,couples,friends')
    
    Returns:
        List of cleaned target groups
    """
    if not value or str(value).lower() == 'nan':
        return []
    
    # Split by comma and clean
    groups = [clean_string(g) for g in str(value).split(',')]
    return [g for g in groups if g]  # Remove empty


def parse_bool(value) -> bool:
    """
    Parse boolean from Excel.
    
    Args:
        value: Value from Excel
    
    Returns:
        Boolean
    """
    if isinstance(value, bool):
        return value
    
    s = str(value).strip().lower()
    
    if s in ('true', '1', 'yes', 'tak'):
        return True
    elif s in ('false', '0', 'no', 'nie', '-', 'nan'):
        return False
    else:
        return False


def convert_opening_hours_to_json(raw: str) -> dict:
    """
    Convert opening hours from Excel string to JSON dict.
    
    Example: 'mon:9:00-18:00,tue:9:00-18:00' → {'mon': '9:00-18:00', 'tue': '9:00-18:00'}
    
    Args:
        raw: String from Excel
    
    Returns:
        Dict or empty dict if parse fails
    """
    if not raw or str(raw).lower() == 'nan':
        return {}
    
    try:
        # Split by comma
        pairs = str(raw).split(',')
        result = {}
        
        for pair in pairs:
            if ':' not in pair:
                continue
            
            # Split day:hours
            day, hours = pair.split(':', 1)
            result[day.strip().lower()] = hours.strip()
        
        return result
    except Exception as e:
        logger.warning(f"Failed to parse opening_hours '{raw}': {e}")
        return {}


def load_attractions_etap3():
    """
    Load multi-city attractions from Excel into Excel cache (POI repository).
    
    Process:
    1. Read Excel file (15 sheets: 15 cities)
    2. For each sheet (city):
        a. Parse each attraction row
        b. Apply data mappings (priority_level, opening_hours_seasonal)
        c. Generate UUID
        d. Create POI dict with all 44 fields
    3. Save to Excel cache (poi_repository.py format)
    4. Log statistics
    
    Returns:
        Number of attractions loaded
    """
    # Excel path (relative to workspace root)
    workspace_root = project_root.parent
    excel_path = workspace_root / 'Planer' / 'Planer - miasta atrakcje.xlsx'
    
    if not excel_path.exists():
        logger.error(f"Excel file not found: {excel_path}")
        return 0
    
    logger.info(f"Loading attractions from: {excel_path}")
    
    # Read Excel
    xls = pd.ExcelFile(excel_path)
    logger.info(f"Found {len(xls.sheet_names)} cities: {xls.sheet_names}")
    
    all_pois = []
    loaded_count = 0
    
    # Process each city
    for sheet_name in xls.sheet_names:
        city = sheet_name  # Sheet name = city name
        df = pd.read_excel(xls, sheet_name=sheet_name)
        logger.info(f"\nProcessing city '{city}': {len(df)} attractions")
        
        for idx, row in df.iterrows():
            try:
                # Extract core fields
                name = clean_string(row['Name'])
                lat = safe_float(row['Lat'])
                lng = safe_float(row['Lng'])
                
                # Validate GPS
                validate_gps_poland(lat, lng, name)
                
                # Get ID (use existing ID if present, otherwise generate UUID)
                poi_id = clean_string(row.get('ID', ''))
                if not poi_id or poi_id == 'nan':
                    poi_id = generate_uuid(name, city, lat)
                
                # Apply mappings
                priority_raw = str(row.get('priority_level', 'optional'))
                priority = map_priority_level(priority_raw)  # core/secondary/optional → high/medium/low
                
                # Parse opening hours
                opening_hours_raw = str(row.get('Opening hours', ''))
                opening_hours = convert_opening_hours_to_json(opening_hours_raw)
                
                opening_hours_seasonal_raw = str(row.get('opening_hours_seasonal', ''))
                opening_hours_seasonal = parse_opening_hours_seasonal(opening_hours_seasonal_raw)
                
                # Parse tags and target groups
                tags = parse_tags(str(row.get('Tags', '')))
                
                # CRITICAL: Column name has TRAILING SPACE!
                target_group = parse_target_group(str(row.get('Target group ', '')))
                
                # Parse boolean
                kids_only = parse_bool(row.get('kids_only', False))
                
                # Clean text fields
                description_short = clean_string(row.get('Description_short', ''))
                description_long = clean_string(row.get('Description_long', ''))
                why_visit = clean_string(row.get('Why visit', ''))
                pro_tip = clean_string(row.get('Pro_tip', ''))
                
                # Parse numeric fields
                time_min = safe_int(row.get('time_min', 60), default=60)
                time_max = safe_int(row.get('time_max', 90), default=90)
                ticket_normal = safe_int(row.get('ticket_normal', 0), default=0)
                ticket_reduced = safe_int(row.get('ticket_reduced', 0), default=0)
                price = safe_float(row.get('Price', 0.0), default=0.0) or None
                
                # Scoring fields
                must_see_score = safe_float(row.get('Must see score', 0.0), default=0.0)
                popularity_score = safe_float(row.get('popularity_score', 0.0), default=0.0)
                
                # Categorization fields
                space = clean_string(row.get('Space', '')).lower()
                intensity = clean_string(row.get('Intensity', '')).lower()
                weather_dependency = clean_string(row.get('weather_dependency', '')).lower()
                crowd_level = clean_string(row.get('crowd_level', ''))
                peak_hours = clean_string(row.get('Peak hours', ''))
                recommended_time_of_day = clean_string(row.get('recommended_time_of_day', ''))
                
                # Children fields
                children_age = clean_string(row.get("Children's age ", ''))
                
                # Type/Style fields
                type_of_attraction = clean_string(row.get('Type of attraction', ''))
                activity_style = clean_string(row.get('Activity_style', ''))
                budget_type = clean_string(row.get('Budget type ', ''))
                seasonality = clean_string(row.get('Seasonality of attractions', ''))
                
                # Parking fields
                parking_name = clean_string(row.get('parking_name', ''))
                parking_address = clean_string(row.get('parking_address', ''))
                parking_lat = safe_float(row.get('parking_lat', 0.0)) or None
                parking_lng = safe_float(row.get('parking_lng', 0.0)) or None
                parking_type = clean_string(row.get('parking_type', '')) or None
                parking_walk_time = safe_int(row.get('parking_walk_time_min', 0)) or None
                
                # Location fields (use City column if exists, otherwise sheet name)
                city_from_excel = clean_string(row.get('City', ''))
                city_final = city_from_excel if city_from_excel else city
                
                address = clean_string(row.get('Address', ''))
                region = clean_string(row.get('Region', ''))
                
                # Links
                link_hours = clean_string(row.get('Link do godzin', ''))
                link_pricing = clean_string(row.get('Link do cennika', ''))
                
                # Image
                image_key = clean_string(row.get('image_key', ''))
                
                # Create POI dict (following load_zakopane.py pattern)
                poi = {
                    # ID and Name (dual keys for backward compat)
                    "id": poi_id,
                    "ID": poi_id,
                    "name": name,
                    "Name": name,
                    
                    # Descriptions
                    "Description_short": description_short,
                    "Description_long": description_long,
                    "Why visit": why_visit,
                    "Pro_tip": pro_tip,
                    
                    # Location
                    "Lat": lat,
                    "Lng": lng,
                    "Address": address,
                    "Region": region,
                    "City": city_final,  # DYNAMIC from sheet or column
                    
                    # Media
                    "image_key": image_key,
                    
                    # Opening hours
                    "Opening hours": opening_hours,  # JSON dict
                    "opening_hours_seasonal": opening_hours_seasonal,  # JSON list or None
                    "Link do godzin": link_hours,
                    
                    # Time
                    "time_min": time_min,
                    "time_max": time_max,
                    "recommended_time_of_day": recommended_time_of_day,
                    
                    # Pricing
                    "Price": price,
                    "ticket_normal": ticket_normal,
                    "ticket_reduced": ticket_reduced,
                    "Link do cennika": link_pricing,
                    
                    # Scoring (MAPPED)
                    "priority_level": priority,  # high/medium/low (MAPPED from core/secondary/optional)
                    "Must see score": must_see_score,
                    "popularity_score": popularity_score,
                    
                    # Characteristics
                    "Space": space,
                    "Intensity": intensity,
                    "weather_dependency": weather_dependency,
                    "crowd_level": crowd_level,
                    "Peak hours": peak_hours,
                    
                    # Target audience
                    "Target group": target_group,  # List (PARSED)
                    "Children's age": children_age,
                    "kids_only": "true" if kids_only else "false",
                    
                    # Categorization
                    "Type of attraction": type_of_attraction,
                    "Activity_style": activity_style,
                    "Budget type": budget_type,
                    "Seasonality of attractions": seasonality,
                    
                    # Tags
                    "Tags": tags,  # List (PARSED)
                    
                    # Parking
                    "parking_name": parking_name,
                    "parking_address": parking_address,
                    "parking_lat": parking_lat,
                    "parking_lng": parking_lng,
                    "parking_type": parking_type,
                    "parking_walk_time_min": parking_walk_time,
                }
                
                all_pois.append(poi)
                loaded_count += 1
                
                logger.debug(f"  ✓ Loaded: {name} (city={city_final}, priority={priority})")
                
            except Exception as e:
                logger.error(f"  ✗ Failed to load attraction at row {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        logger.info(f"City '{city}' complete: {loaded_count} attractions loaded so far")
    
    # Save to Excel cache (poi_repository.py format)
    output_path = project_root / 'data' / 'multi_city_attractions.xlsx'
    output_path.parent.mkdir(exist_ok=True)
    
    try:
        # Convert to DataFrame
        df_output = pd.DataFrame(all_pois)
        
        # Save to Excel
        df_output.to_excel(output_path, index=False, sheet_name='All Cities')
        logger.info(f"\n✅ SUCCESS: {loaded_count} attractions saved to {output_path}")
    except Exception as e:
        logger.error(f"\n❌ FAILED: Excel save error: {e}")
        raise
    
    # Log statistics
    log_mapping_stats(attractions_mapped=loaded_count)
    
    return loaded_count


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("ETAP 3 - ATTRACTION LOADER (Multi-City)")
    logger.info("=" * 60)
    
    try:
        count = load_attractions_etap3()
        logger.info(f"\n🎯 TOTAL: {count} attractions loaded successfully")
        logger.info(f"   Expected: 671 POI across 15 cities")
    except Exception as e:
        logger.error(f"\n💥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
