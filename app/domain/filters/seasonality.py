"""
Seasonality filtering module.

Hard filter: excludes POI completely if outside current season.
"""

from datetime import datetime


def derive_season(date):
    """
    Derive season from date.
    
    Args:
        date: datetime object or date object
    
    Returns:
        str: "winter", "spring", "summer", or "fall"
    """
    if isinstance(date, str):
        # Parse if string (format: YYYY-MM-DD)
        date = datetime.strptime(date, "%Y-%m-%d")
    
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
    
    filtered_pois = []
    
    for poi in pois:
        seasonality = poi.get("seasonality", [])
        
        # If no seasonality specified, POI is available all year
        if not seasonality:
            filtered_pois.append(poi)
            continue
        
        # Ensure seasonality is a list
        if isinstance(seasonality, str):
            seasonality = [seasonality]
        
        # Convert to lowercase for comparison
        seasonality = [s.lower() for s in seasonality]
        
        # Check if current season is in POI's seasons
        if current_season in seasonality:
            filtered_pois.append(poi)
        # Else: HARD FILTER - exclude this POI
    
    return filtered_pois
