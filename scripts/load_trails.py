"""
ETAP 3 - Trail Loader

Load mountain trails from Excel (Planer - szlaki górskie.xlsx) into trails table.

Expected: 37 trails across 3 regions (Tatry, Kotlina Kłodzka, Karkonosze)

USAGE:
    cd travel-planner-backend
    python scripts/load_trails.py
"""

import sys
import os
from pathlib import Path
import pandas as pd
import uuid
import logging

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root.parent))

from app.infrastructure.database import TrailDB
from app.infrastructure.database.connection import SessionLocal
from scripts.data_mappings import (
    map_difficulty_level,
    map_weather_dependency,
    map_exposure_level,
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


def generate_uuid(trail_name: str, region: str, start_lat: float) -> str:
    """
    Generate deterministic UUID for trail.
    
    Uses: trail_name + region + start_lat to ensure uniqueness.
    """
    namespace = uuid.NAMESPACE_DNS
    unique_str = f"{trail_name.lower().strip()}_{region.lower().strip()}_{start_lat}"
    return str(uuid.uuid5(namespace, unique_str))


def parse_popularity(value: str) -> float:
    """
    Convert Excel popularity string to numeric score.
    
    Maps:
        'high' → 0.9
        'medium' → 0.5
        'low' → 0.1
    
    Args:
        value: String from Excel (may have '\n' prefix)
    
    Returns:
        Float score (0.0 - 1.0)
    """
    cleaned = clean_string(value).lower()
    
    mapping = {
        'high': 0.9,
        'medium': 0.5,
        'low': 0.1,
    }
    
    return mapping.get(cleaned, 0.0)


def parse_elevation(value: str) -> int:
    """
    Parse elevation from Excel format.
    
    Excel has: "1 894" (space separator)
    Need: 1894 (integer)
    
    Args:
        value: String from Excel
    
    Returns:
        Integer elevation in meters
    """
    if not value or str(value).lower() == 'nan':
        return 0
    
    # Remove spaces
    cleaned = str(value).replace(' ', '').replace(',', '').strip()
    
    return safe_int(cleaned, default=0)


def parse_bool(value) -> bool:
    """
    Parse boolean from Excel.
    
    Excel has: "False", "True", False, True, 0, 1
    
    Args:
        value: Value from Excel
    
    Returns:
        Boolean
    """
    if isinstance(value, bool):
        return value
    
    s = str(value).strip().lower()
    
    if s in ('true', '1', 'yes'):
        return True
    elif s in ('false', '0', 'no', '-'):
        return False
    else:
        return False


def load_trails():
    """
    Load trails from Excel into trails table.
    
    Process:
    1. Read Excel file (3 sheets: Tatry, Kotlina Kłodzka, Karkonosze)
    2. For each sheet (region):
        a. Parse each trail row
        b. Apply data mappings
        c. Generate UUID
        d. Create TrailDB object
        e. Merge to database
    3. Commit transaction
    4. Log statistics
    
    Returns:
        Number of trails loaded
    """
    # Excel path (relative to workspace root)
    workspace_root = project_root.parent
    excel_path = workspace_root / 'Planer' / 'Planer - szlaki górskie.xlsx'
    
    if not excel_path.exists():
        logger.error(f"Excel file not found: {excel_path}")
        return 0
    
    logger.info(f"Loading trails from: {excel_path}")
    
    # Read Excel
    xls = pd.ExcelFile(excel_path)
    logger.info(f"Found {len(xls.sheet_names)} regions: {xls.sheet_names}")
    
    # Get database session
    session = SessionLocal()
    loaded_count = 0
    
    # Process each region
    for sheet_name in xls.sheet_names:
        region = sheet_name  # Sheet name = region name
        df = pd.read_excel(xls, sheet_name=sheet_name)
        logger.info(f"\nProcessing region '{region}': {len(df)} trails")
        
        for idx, row in df.iterrows():
            try:
                # Extract core fields
                trail_name = clean_string(row['trail_name'])
                peak_name = clean_string(row.get('peak_name', '')) or None
                start_lat = safe_float(row['start_lat'])
                start_lng = safe_float(row['start_lng'])
                
                # Validate GPS
                validate_gps_poland(start_lat, start_lng, trail_name)
                
                # Generate UUID
                trail_id = generate_uuid(trail_name, region, start_lat)
                
                # Apply mappings
                difficulty = map_difficulty_level(str(row.get('difficulty_level', 'moderate')))
                weather = map_weather_dependency(str(row.get('weather_dependency', 'medium')))
                exposure = map_exposure_level(str(row.get('exposure_level', 'low')))
                
                # Parse complex fields (NOTE: opening_hours_seasonal not in TrailDB - skip parsing)
                family_friendly = parse_bool(row.get('family_friendly', False))
                # opening_hours = parse_opening_hours_seasonal(str(row.get('opening_hours_seasonal', '')))  # NOT IN MODEL
                popularity = parse_popularity(str(row.get('popularity', 'low')))
                
                # Parse elevations (NOTE: peak_elevation_m not in TrailDB - skip)
                # peak_elevation = parse_elevation(str(row.get('peak_elevation_m', 0)))
                elevation_gain = safe_int(row.get('elevation_gain_m', 0))
                
                # Clean text fields (NOTE: trail_type not in TrailDB - skip)
                description_short = clean_string(row.get('Description_short', ''))
                description_long = clean_string(row.get('Description_long', ''))
                best_season = clean_string(row.get('seasonality', 'summer')).lower()
                trail_color = clean_string(row.get('trail_color', ''))
                # trail_type = clean_string(row.get('trail_type', 'loop')).lower()  # NOT IN MODEL
                
                # Parse children age
                children_age = clean_string(row.get("Children's age", ''))
                children_min_age = safe_int(children_age) if children_age and children_age != '-' else None
                
                # Parse parking (NOTE: parking_address not in TrailDB)
                parking_name = clean_string(row.get('parking_name', ''))
                # parking_address = clean_string(row.get('parking_address', ''))  # NOT IN MODEL
                parking_lat = safe_float(row.get('parking_lat', 0.0)) or None
                parking_lng = safe_float(row.get('parking_lng', 0.0)) or None
                parking_type = clean_string(row.get('parking_type', '')) or None
                parking_walk_time = safe_int(row.get('parking_walk_time_min', 0)) or None
                
                # Create TrailDB object
                trail = TrailDB(
                    id=trail_id,
                    trail_name=trail_name,
                    peak_name=peak_name,
                    region=region,  # From sheet name
                    
                    # Characteristics
                    trail_color=trail_color or None,
                    difficulty_level=difficulty,  # MAPPED
                    family_friendly=family_friendly,
                    exposure_level=exposure,  # MAPPED
                    weather_dependency=weather,  # MAPPED
                    technical_difficulty=None,  # Not in Excel
                    
                    # Location
                    start_point_name=clean_string(row.get('start_point_name', '')),
                    start_lat=start_lat,
                    start_lng=start_lng,
                    start_elevation_m=0,  # NOT IN EXCEL - default to 0 (NOT NULL constraint)
                    end_lat=None,  # Not in Excel
                    end_lng=None,  # Not in Excel
                    # peak_elevation_m=peak_elevation,  # NOT IN TrailDB MODEL
                    elevation_gain_m=elevation_gain,
                    
                    # Distance and time
                    length_km=safe_float(row.get('length_km', 0.0)),
                    time_min=safe_int(row.get('time_min', 0)),
                    time_max=safe_int(row.get('time_max', 0)),
                    
                    # Seasonality (NOTE: opening_hours_seasonal not in TrailDB model)
                    best_season=best_season,
                    # opening_hours_seasonal NOT SUPPORTED
                    
                    # Target audience
                    target_group=[],  # Not in Excel
                    children_min_age=children_min_age or 0,  # NOT NULL - default to 0
                    
                    # Parking (NOTE: parking_address not in model)
                    parking_name=parking_name or None,
                    # parking_address NOT SUPPORTED
                    parking_lat=parking_lat,
                    parking_lng=parking_lng,
                    parking_walk_time_min=parking_walk_time,
                    parking_type=parking_type,
                    parking_cost=0,  # NOT IN EXCEL - default to 0 (NOT NULL)
                    
                    # Descriptions
                    description_short=description_short,
                    description_long=description_long,
                    highlights=None,  # Not in Excel
                    pro_tip=None,  # Not in Excel
                    
                    # Scoring (NOTE: crowd_level not in TrailDB model)
                    popularity_score=popularity,  # PARSED
                    scenic_score=0.0,  # Not in Excel
                    must_do=False,  # Not in Excel
                    # crowd_level NOT SUPPORTED
                    
                    # Metadata
                    image_key=clean_string(row.get('image_key', '')) or None,
                )
                
                # Merge (insert or update)
                session.merge(trail)
                loaded_count += 1
                
                logger.debug(f"  ✓ Loaded: {trail_name} (region={region}, difficulty={difficulty})")
                
            except Exception as e:
                logger.error(f"  ✗ Failed to load trail at row {idx}: {e}")
                continue
        
        logger.info(f"Region '{region}' complete: {loaded_count} trails loaded so far")
    
    # Commit transaction
    try:
        session.commit()
        logger.info(f"\n✅ SUCCESS: {loaded_count} trails committed to database")
    except Exception as e:
        session.rollback()
        logger.error(f"\n❌ FAILED: Database commit error: {e}")
        raise
    
    # Log statistics
    log_mapping_stats(trails_mapped=loaded_count)
    
    return loaded_count


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("ETAP 3 - TRAIL LOADER")
    logger.info("=" * 60)
    
    try:
        count = load_trails()
        logger.info(f"\n🎯 TOTAL: {count} trails loaded successfully")
    except Exception as e:
        logger.error(f"\n💥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
