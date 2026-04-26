"""
ETAP 3 - Restaurant Loader

Load restaurants from Excel (Planer - restauracje.xlsx) into restaurants table.

Expected: ~310 rows → ~250 imported (after filtering coffee-only places)

FILTERING LOGIC:
- meal_type='coffee' → SKIP (not a meal place)
- meal_type='lunch,dinner' → 'lunch' (priority)
- meal_type='dinner' → 'dinner'
- meal_type='coffee,dessert' → SKIP

USAGE:
    cd travel-planner-backend
    python scripts/load_restaurants.py
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

from app.infrastructure.database import RestaurantDB
from app.infrastructure.database.connection import SessionLocal
from scripts.data_mappings import (
    parse_meal_type,
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
    Generate deterministic UUID for restaurant.
    
    Uses: name + city + lat to ensure uniqueness.
    """
    namespace = uuid.NAMESPACE_DNS
    unique_str = f"{name.lower().strip()}_{city.lower().strip()}_{lat}"
    return str(uuid.uuid5(namespace, unique_str))


def parse_tags(value: str) -> list:
    """
    Parse comma-separated tags into list.
    
    Args:
        value: String from Excel (e.g., 'romantic,outdoor,family')
    
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
    
    Args:
        value: String from Excel (e.g., 'families,couples,solo')
    
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
    
    Excel has: "False", "True", False, True, 0, 1
    
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


def load_restaurants():
    """
    Load restaurants from Excel into restaurants table.
    
    Process:
    1. Read Excel file (15 sheets: 15 cities)
    2. For each sheet (city):
        a. Parse each restaurant row
        b. Filter by meal_type (skip coffee-only)
        c. Apply data mappings
        d. Generate UUID
        e. Create RestaurantDB object
        f. Merge to database
    3. Commit transaction
    4. Log statistics
    
    Returns:
        Tuple (loaded_count, skipped_count)
    """
    # Excel path (relative to workspace root)
    workspace_root = project_root.parent
    excel_path = workspace_root / 'Planer' / 'Planer - restauracje.xlsx'
    
    if not excel_path.exists():
        logger.error(f"Excel file not found: {excel_path}")
        return (0, 0)
    
    logger.info(f"Loading restaurants from: {excel_path}")
    
    # Read Excel
    xls = pd.ExcelFile(excel_path)
    logger.info(f"Found {len(xls.sheet_names)} cities: {xls.sheet_names}")
    
    # Get database session
    session = SessionLocal()
    loaded_count = 0
    skipped_count = 0
    
    # Process each city
    for sheet_name in xls.sheet_names:
        city = sheet_name  # Sheet name = city name
        df = pd.read_excel(xls, sheet_name=sheet_name)
        logger.info(f"\nProcessing city '{city}': {len(df)} restaurants")
        
        for idx, row in df.iterrows():
            try:
                # Extract core fields
                name = clean_string(row['Name'])
                lat = safe_float(row['Lat'])
                lng = safe_float(row['Lng'])
                
                # CRITICAL: Filter by meal_type
                meal_type_raw = str(row.get('meal_type', ''))
                meal_type = parse_meal_type(meal_type_raw)
                
                if meal_type is None:
                    skipped_count += 1
                    logger.debug(f"  ⊘ Skipping '{name}' (meal_type='{meal_type_raw}' → coffee/breakfast only)")
                    continue  # Skip coffee-only restaurants
                
                # Validate GPS
                validate_gps_poland(lat, lng, name)
                
                # Generate UUID
                restaurant_id = generate_uuid(name, city, lat)
                
                # Parse opening hours (NOTE: opening_hours_seasonal not parsed - complex JSON structure)
                # opening_hours = parse_opening_hours_seasonal(str(row.get('opening_hours_seasonal', '')))  # NOT USED
                
                # Parse tags and target groups
                tags = parse_tags(str(row.get('Tags', '')))
                target_group = parse_target_group(str(row.get('recommended_for', '')))
                
                # Clean text fields (NOTE: description_short, description_long, why_visit not in RestaurantDB)
                # description_short NOT IN MODEL
                # description_long NOT IN MODEL
                # why_visit NOT IN MODEL
                pro_tip = clean_string(row.get('pro_tip', ''))
                place_type = clean_string(row.get('place_type', ''))
                cuisine_type = clean_string(row.get('cuisine_type', ''))
                
                # Parse numeric fields
                visit_duration_min = safe_int(row.get('visit_duration_min', 60), default=60)
                visit_duration_max = safe_int(row.get('visit_duration_max', 90), default=90)
                price_level = safe_int(row.get('price_level', 2), default=2)
                
                # Parse boolean
                reservation_recommended = parse_bool(row.get('reservation_recommended', False))
                
                # Parse parking (NOTE: parking_address, parking_type not in RestaurantDB)
                parking_name = clean_string(row.get('parking_name', ''))
                # parking_address NOT IN MODEL
                parking_lat = safe_float(row.get('parking_lat', 0.0)) or None
                parking_lng = safe_float(row.get('parking_lng', 0.0)) or None
                # parking_type NOT IN MODEL
                parking_walk_time = safe_int(row.get('parking_walk_time_min', 0)) or 0
                
                # Create RestaurantDB object
                restaurant = RestaurantDB(
                    id=restaurant_id,
                    name=name,
                    city=city,  # From sheet name
                    
                    # Core type fields
                    meal_type=meal_type,  # FILTERED: 'lunch' or 'dinner'
                    cuisine_type=cuisine_type or None,
                    place_type=place_type or None,
                    
                    # Location
                    lat=lat,
                    lng=lng,
                    address=clean_string(row.get('Address', '')),
                    
                    # Timing
                    visit_duration_min=visit_duration_min,
                    visit_duration_max=visit_duration_max,
                    opening_hours=None,  # Not in Excel
                    opening_hours_seasonal=None,  # Not parsed (complex structure)
                    # peak_hours NOT IN MODEL
                    
                    # Pricing
                    price_level=price_level,
                    avg_meal_cost=50,  # NOT IN EXCEL - default (NOT NULL)
                    
                    # Atmosphere & features
                    atmosphere=None,  # Not in Excel
                    space=None,  # Not in Excel
                    # outdoor_seating NOT IN MODEL
                    children_friendly=True,  # NOT IN EXCEL - default (NOT NULL)
                    
                    # Target audience
                    target_group=target_group,
                    
                    # Descriptions (NOTE: ALL description fields not in RestaurantDB - only pro_tip)
                    # description_short NOT IN MODEL
                    # description_long NOT IN MODEL
                    # why_visit NOT IN MODEL
                    pro_tip=pro_tip or None,
                    # highlights NOT IN MODEL
                    
                    # Scoring
                    popularity_score=0.0,  # Not in Excel
                    rating=None,  # Not in Excel
                    must_try=False,  # Not in Excel
                    
                    # Reservations (FIELD NAME: reservations_required)
                    reservations_required=reservation_recommended,  # MAPPED FIELD NAME
                    # reservation_url NOT IN MODEL
                    
                    # Parking
                    parking_name=parking_name or None,
                    parking_lat=parking_lat,
                    parking_lng=parking_lng,
                    parking_walk_time_min=parking_walk_time,
                    
                    # Metadata (NOTE: tags not in RestaurantDB model)
                    image_key=clean_string(row.get('image_key', '')) or None,
                    # tags NOT IN MODEL
                )
                
                # Merge (insert or update)
                session.merge(restaurant)
                loaded_count += 1
                
                logger.debug(f"  ✓ Loaded: {name} (city={city}, meal_type={meal_type})")
                
            except Exception as e:
                logger.error(f"  ✗ Failed to load restaurant at row {idx}: {e}")
                continue
        
        logger.info(f"City '{city}' complete: {loaded_count} loaded, {skipped_count} skipped so far")
    
    # Commit transaction
    try:
        session.commit()
        logger.info(f"\n✅ SUCCESS: {loaded_count} restaurants committed to database")
    except Exception as e:
        session.rollback()
        logger.error(f"\n❌ FAILED: Database commit error: {e}")
        raise
    
    # Log statistics
    log_mapping_stats(
        restaurants_imported=loaded_count,
        restaurants_skipped=skipped_count
    )
    
    return (loaded_count, skipped_count)


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("ETAP 3 - RESTAURANT LOADER")
    logger.info("=" * 60)
    
    try:
        loaded, skipped = load_restaurants()
        logger.info(f"\n🎯 TOTAL: {loaded} restaurants loaded, {skipped} skipped (coffee-only)")
        logger.info(f"   Expected: ~250 loaded, ~60 skipped from 310 total rows")
    except Exception as e:
        logger.error(f"\n💥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
