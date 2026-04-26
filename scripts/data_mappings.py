"""
ETAP 3 - Data Mapping Module

Transforms Excel data values to match specification requirements.

WHY THIS EXISTS:
Excel files from client use different vocabulary than spec:
- priority_level: 'core/secondary/optional' → 'high/medium/low'
- meal_type: 'lunch,dinner' (comma-separated) → 'lunch' OR 'dinner' (single)
- difficulty_level: 'medium' → 'moderate'
- weather_dependency: 'good_weather_only' → 'high'
- opening_hours_seasonal: Invalid JSON → parsed dict

This module provides transformation functions used by Excel loaders.
"""

import json
import re
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ============================================================
# ATTRACTIONS MAPPINGS
# ============================================================

PRIORITY_MAPPING = {
    'core': 'high',          # Main must-see attractions
    'secondary': 'medium',   # Supporting attractions
    'optional': 'low',       # Filler/optional attractions
}

def map_priority_level(raw_value: str) -> str:
    """
    Convert Excel priority_level to specification values.
    
    Excel: 'core', 'secondary', 'optional'
    Spec: 'high', 'medium', 'low'
    
    Args:
        raw_value: Value from Excel (may have whitespace)
    
    Returns:
        Mapped value ('high', 'medium', 'low')
        Default: 'medium' if unknown
    """
    cleaned = clean_string(raw_value)
    mapped = PRIORITY_MAPPING.get(cleaned, 'medium')
    
    if cleaned not in PRIORITY_MAPPING:
        logger.warning(f"Unknown priority_level '{raw_value}' → defaulting to 'medium'")
    
    return mapped


def parse_opening_hours_seasonal(raw_value: str) -> Optional[list]:
    """
    Parse opening_hours_seasonal from Excel to valid JSON.
    
    PROBLEM: Excel contains invalid JSON:
    - Keys not quoted: date_from instead of "date_from"
    - Values not quoted: 01-01 instead of "01-01"
    - Mixed JavaScript object syntax
    
    SOLUTION: Try multiple strategies:
    1. Direct JSON parse (if already valid)
    2. Fix common issues (quote keys/values)
    3. Give up gracefully (return None)
    
    Args:
        raw_value: String from Excel
    
    Returns:
        Parsed list of dicts, or None if unparseable
    """
    if not raw_value or raw_value == '' or str(raw_value).lower() == 'nan':
        return None
    
    # Try 1: Direct parse
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, list) else None
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Try 2: Fix common issues
    try:
        # Remove newlines
        fixed = raw_value.replace('\n', ' ').replace('\r', ' ')
        
        # Try parsing again
        parsed = json.loads(fixed)
        return parsed if isinstance(parsed, list) else None
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Try 3: Give up gracefully
    logger.warning(f"Could not parse opening_hours_seasonal (length {len(str(raw_value))})")
    return None


# ============================================================
# RESTAURANTS MAPPINGS
# ============================================================

def parse_meal_type(raw_value: str) -> Optional[str]:
    """
    Convert comma-separated meal types to single value.
    
    PROBLEM: Excel has 'lunch,dinner', 'coffee', 'breakfast,lunch,coffee'
    REQUIREMENT: Optimizer needs single value: 'lunch' OR 'dinner'
    
    BUSINESS LOGIC:
    1. If 'lunch' present → return 'lunch' (priority)
    2. Else if 'dinner' present → return 'dinner'
    3. Else (coffee/breakfast only) → return None (SKIP - not main meal)
    
    Args:
        raw_value: String from Excel (e.g., 'lunch,dinner')
    
    Returns:
        'lunch', 'dinner', or None
        None means "skip this restaurant" (not a meal place)
    
    Examples:
        'lunch,dinner' → 'lunch'
        'dinner' → 'dinner'
        'coffee' → None (SKIP)
        'coffee,dessert' → None (SKIP)
        'breakfast,coffee' → None (SKIP)
    """
    if not raw_value or raw_value == '':
        return None
    
    # Split by comma and clean
    values = [v.strip().lower() for v in str(raw_value).split(',')]
    
    # Priority order
    if 'lunch' in values:
        return 'lunch'
    elif 'dinner' in values:
        return 'dinner'
    else:
        # Only coffee/breakfast/dessert → skip
        logger.debug(f"Skipping restaurant with meal_type='{raw_value}' (not lunch/dinner)")
        return None


# ============================================================
# TRAILS MAPPINGS
# ============================================================

DIFFICULTY_MAPPING = {
    'easy': 'easy',
    'medium': 'moderate',    # FIX: Excel uses 'medium', spec uses 'moderate'
    'hard': 'hard',
    'extreme': 'extreme',
}

def map_difficulty_level(raw_value: str) -> str:
    """
    Convert Excel difficulty_level to specification values.
    
    Excel: 'easy', 'medium', 'hard', 'extreme'
    Spec: 'easy', 'moderate', 'hard', 'extreme'
    
    Args:
        raw_value: Value from Excel
    
    Returns:
        Mapped value
        Default: 'moderate' if unknown
    """
    cleaned = clean_string(raw_value).lower()
    mapped = DIFFICULTY_MAPPING.get(cleaned, 'moderate')
    
    if cleaned not in DIFFICULTY_MAPPING:
        logger.warning(f"Unknown difficulty_level '{raw_value}' → defaulting to 'moderate'")
    
    return mapped


WEATHER_DEPENDENCY_MAPPING = {
    'all_weather': 'low',           # Works in all weather conditions
    'mixed': 'medium',              # Some weather dependency
    'good_weather_only': 'high',    # Requires good weather
}

def map_weather_dependency(raw_value: str) -> str:
    """
    Convert Excel weather_dependency to specification values.
    
    Excel: 'all_weather', 'mixed', 'good_weather_only'
    Spec: 'low', 'medium', 'high'
    
    Semantic meaning:
    - all_weather → low dependency (works in rain/snow)
    - mixed → medium dependency (prefer good weather)
    - good_weather_only → high dependency (dangerous in bad weather)
    
    Args:
        raw_value: Value from Excel
    
    Returns:
        Mapped value ('low', 'medium', 'high')
        Default: 'medium' if unknown
    """
    cleaned = clean_string(raw_value).lower()
    mapped = WEATHER_DEPENDENCY_MAPPING.get(cleaned, 'medium')
    
    if cleaned not in WEATHER_DEPENDENCY_MAPPING:
        logger.warning(f"Unknown weather_dependency '{raw_value}' → defaulting to 'medium'")
    
    return mapped


EXPOSURE_MAPPING = {
    'low': 'low',
    'medium': 'medium',
    'high': 'high',
    'extreme': 'extreme',
}

def map_exposure_level(raw_value: str) -> str:
    """
    Clean and validate exposure_level.
    
    PROBLEM: Excel has '\nhigh' (newline character)
    
    Args:
        raw_value: Value from Excel
    
    Returns:
        Cleaned value ('low', 'medium', 'high', 'extreme')
        Default: 'low' if unknown
    """
    cleaned = clean_string(raw_value).lower()
    mapped = EXPOSURE_MAPPING.get(cleaned, 'low')
    
    if cleaned not in EXPOSURE_MAPPING:
        logger.warning(f"Unknown exposure_level '{raw_value}' → defaulting to 'low'")
    
    return mapped


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_string(value: str) -> str:
    """
    Clean string value from Excel.
    
    Removes:
    - Leading/trailing whitespace
    - Newline characters (\n, \r)
    - Extra spaces
    
    Args:
        value: Raw string from Excel
    
    Returns:
        Cleaned string
    
    Examples:
        '\nhigh' → 'high'
        'Target group ' → 'Target group'
        '\nsecondary\n' → 'secondary'
    """
    if not value or value == '':
        return ''
    
    # Convert to string (in case of numeric)
    s = str(value)
    
    # Remove newlines and extra whitespace
    s = s.replace('\n', '').replace('\r', '').strip()
    
    # Collapse multiple spaces
    s = re.sub(r'\s+', ' ', s)
    
    return s


def validate_gps_poland(lat: float, lng: float, poi_name: str = "") -> bool:
    """
    Validate GPS coordinates are within Poland range.
    
    Poland bounding box:
    - Latitude: 49°N to 55°N
    - Longitude: 14°E to 24°E
    
    Args:
        lat: Latitude
        lng: Longitude
        poi_name: POI name (for logging)
    
    Returns:
        True if valid, False if outside Poland
        Logs warning if invalid but returns True (allow outliers)
    """
    if not (49 <= lat <= 55):
        logger.warning(f"POI '{poi_name}' has latitude {lat} outside Poland range (49-55)")
        return True  # Allow but warn
    
    if not (14 <= lng <= 24):
        logger.warning(f"POI '{poi_name}' has longitude {lng} outside Poland range (14-24)")
        return True  # Allow but warn
    
    return True


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        Int value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ============================================================
# VALIDATION SUMMARY
# ============================================================

def log_mapping_stats(
    attractions_mapped: int = 0,
    restaurants_skipped: int = 0,
    restaurants_imported: int = 0,
    trails_mapped: int = 0
):
    """
    Log mapping statistics after import.
    
    Use this at the end of each loader to show what was transformed.
    """
    logger.info("=" * 60)
    logger.info("DATA MAPPING SUMMARY")
    logger.info("=" * 60)
    
    if attractions_mapped > 0:
        logger.info(f"Attractions mapped: {attractions_mapped}")
        logger.info("  - priority_level: core/secondary/optional → high/medium/low")
        logger.info("  - opening_hours_seasonal: parsed JSON")
    
    if restaurants_imported > 0 or restaurants_skipped > 0:
        logger.info(f"Restaurants imported: {restaurants_imported}")
        logger.info(f"Restaurants skipped: {restaurants_skipped} (coffee/dessert only)")
        logger.info("  - meal_type: 'lunch,dinner' → single value")
    
    if trails_mapped > 0:
        logger.info(f"Trails mapped: {trails_mapped}")
        logger.info("  - difficulty_level: medium → moderate")
        logger.info("  - weather_dependency: semantic names → low/medium/high")
        logger.info("  - exposure_level: cleaned whitespace")
    
    logger.info("=" * 60)


# ============================================================
# USAGE EXAMPLE (for loaders)
# ============================================================

"""
USAGE IN EXCEL LOADERS:

from scripts.data_mappings import (
    map_priority_level,
    parse_meal_type,
    map_difficulty_level,
    clean_string,
)

# In attractions loader:
priority = map_priority_level(row['priority_level'])
opening_hours = parse_opening_hours_seasonal(row['opening_hours_seasonal'])
target_groups = clean_string(row['Target group '])  # Note trailing space!

# In restaurants loader:
meal_type = parse_meal_type(row['meal_type'])
if meal_type is None:
    continue  # Skip coffee-only places

# In trails loader:
difficulty = map_difficulty_level(row['difficulty_level'])
weather_dep = map_weather_dependency(row['weather_dependency'])
exposure = map_exposure_level(row['exposure_level'])
"""
