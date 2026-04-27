"""
Trip Type Router - Intelligent detection of trip characteristics (ETAP 3 Phase 2 + Phase 7).

Analyzes TripInput to determine:
1. Trip category: city_tourism, mountain_hiking, mixed, cluster
2. Data sources needed: POI, TrailDB, RestaurantDB
3. Engine configuration: routing priorities, scoring weights

**PHASE 7 (27.04.2026): Destination Clusters Support**
- Detects multi-city clusters (Trójmiasto, Kotlina Kłodzka, Karkonosze)
- Returns config with all cities in cluster for data loading
- Applies cluster-specific scoring weights

**Decision Logic:**
- **Cluster flag set** → cluster (multi-city data loading)
- **Mountain region + outdoor preferences** → mountain_hiking (TrailDB primary)
- **City region + cultural preferences** → city_tourism (POI primary)
- **Mixed signals** → mixed (both data sources)
"""
from typing import Dict, Any, List
from app.domain.models.trip_input import TripInput
from app.domain.config import DestinationClusters  # PHASE 7


class TripType:
    """Trip category constants."""
    CITY_TOURISM = "city_tourism"      # POI + RestaurantDB
    MOUNTAIN_HIKING = "mountain_hiking"  # TrailDB + RestaurantDB
    MIXED = "mixed"                     # POI + TrailDB + RestaurantDB
    CLUSTER = "cluster"                 # PHASE 7: Multi-city cluster (all data sources)


class TripTypeRouter:
    """
    Intelligent router that analyzes TripInput and determines trip category.
    
    Usage:
        router = TripTypeRouter()
        config = router.detect_trip_type(trip_input)
        
        if config["trip_type"] == TripType.MOUNTAIN_HIKING:
            # Use TrailDB primarily
            trails = trail_repo.get_by_region(region)
        elif config["trip_type"] == TripType.CITY_TOURISM:
            # Use POI primarily
            pois = poi_repo.get_all()
    """
    
    # Mountain regions with trail data
    MOUNTAIN_REGIONS = {
        "Tatry",
        "Kotlina Kłodzka",
        "Karkonosze",
        "Zakopane",  # Maps to Tatry
    }
    
    # City regions with POI data
    CITY_REGIONS = {
        "Kraków",
        "Warszawa",
        "Wrocław",
        "Gdańsk",
        "Katowice",
        "Poznań",
        "Szczecin",
        "Lublin",
        "Bydgoszcz",
        "Białystok",
        "Łódź",
        "Rzeszów",
        "Toruń",
        "Kielce",
        "Olsztyn",
    }
    
    # Outdoor preferences that signal hiking intent
    OUTDOOR_PREFERENCES = {
        "outdoor",
        "hiking",
        "nature",
        "mountain",
        "adventure",
        "trekking",
        "scenic_views",
    }
    
    # Cultural preferences that signal city tourism
    CULTURAL_PREFERENCES = {
        "culture",
        "museums",
        "history",
        "architecture",
        "shopping",
        "nightlife",
        "food",
        "restaurants",
    }
    
    def detect_trip_type(self, trip_input: TripInput) -> Dict[str, Any]:
        """
        Analyze TripInput and return trip configuration.
        
        Args:
            trip_input: User's trip request
        
        Returns:
            Dict with keys:
                - trip_type: TripType constant
                - use_trails: bool (query TrailDB)
                - use_pois: bool (query POI Excel)
                - use_restaurants: bool (query RestaurantDB)
                - primary_source: 'trails' or 'pois'
                - region: str (normalized region name)
                - scoring_weights: dict (custom weights for engine)
                - confidence: float (0.0-1.0, how confident we are)
        
        Example:
            >>> router = TripTypeRouter()
            >>> trip_input = TripInput(location=LocationInput(city="Zakopane"), preferences=["hiking", "outdoor"])
            >>> config = router.detect_trip_type(trip_input)
            >>> config["trip_type"]
            'mountain_hiking'
            >>> config["use_trails"]
            True
        """
        # Extract signals from TripInput
        location = trip_input.location.city or trip_input.location.country
        region_type = trip_input.location.region_type or "city"
        preferences = trip_input.preferences or []
        travel_style = trip_input.travel_style or "balanced"
        group_type = trip_input.group.type  # 'solo', 'couples', 'friends', 'family_kids', 'seniors'
        is_cluster = trip_input.location.is_cluster  # PHASE 7: Multi-city cluster
        
        # ================================================================
        # PHASE 7: CLUSTER DETECTION (Priority over single-city logic)
        # ================================================================
        if is_cluster:
            cluster_config = DestinationClusters.get_cluster(location)
            
            if not cluster_config:
                # Should not happen (LocationInput validator catches this)
                # But handle gracefully
                print(f"[ROUTER] WARNING: is_cluster=True but cluster '{location}' not found. Falling back to single-city.")
            else:
                # Return cluster configuration
                print(f"[ROUTER] CLUSTER DETECTED: {cluster_config['name']}")
                print(f"  - Cities: {cluster_config['cities']}")
                print(f"  - Type: {cluster_config['type'].value}")
                print(f"  - Total attractions: {cluster_config['total_attractions']}")
                print(f"  - Total restaurants: {cluster_config['total_restaurants']}")
                
                return {
                    "trip_type": TripType.CLUSTER,
                    "use_trails": cluster_config["region_type"] == "mountain",  # Only for Karkonosze
                    "use_pois": True,  # Always use POI for clusters
                    "use_restaurants": True,  # Always use restaurants
                    "primary_source": "pois",
                    "region": cluster_config["name"],  # Cluster name (for logging)
                    "cities": cluster_config["cities"],  # PHASE 7: List of cities to load data from
                    "cluster_config": cluster_config,  # Full cluster config for PlanService
                    "scoring_weights": cluster_config["scoring_weights"],  # Cluster-specific weights
                    "confidence": 1.0,  # Perfect confidence (explicit cluster flag)
                    "signals": {
                        "cluster_type": cluster_config["type"].value,
                        "cluster_name": cluster_config["name"],
                        "cluster_cities": cluster_config["cities"],
                    }
                }
        
        # ================================================================
        # SINGLE-CITY DETECTION (Original Phase 2 logic)
        # ================================================================
        
        # Score signals
        mountain_score = 0.0
        city_score = 0.0
        
        # Signal 1: Location (strongest signal)
        if location in self.MOUNTAIN_REGIONS:
            mountain_score += 3.0
        elif location in self.CITY_REGIONS:
            city_score += 3.0
        
        # Signal 2: Region type
        if region_type == "mountain":
            mountain_score += 2.0
        elif region_type == "city":
            city_score += 2.0
        
        # Signal 3: Preferences
        outdoor_prefs = set(preferences) & self.OUTDOOR_PREFERENCES
        cultural_prefs = set(preferences) & self.CULTURAL_PREFERENCES
        
        mountain_score += len(outdoor_prefs) * 0.5
        city_score += len(cultural_prefs) * 0.5
        
        # Signal 4: Travel style
        if travel_style in ["adventure", "nature"]:
            mountain_score += 1.0
        elif travel_style in ["cultural", "urban"]:
            city_score += 1.0
        
        # Signal 5: Group type (families with kids prefer easier activities)
        if group_type == "family_kids":
            # Families can do both, but easier trails
            pass
        elif group_type == "adventure_seekers":
            mountain_score += 1.0
        
        # Determine trip type
        total_score = mountain_score + city_score
        confidence = max(mountain_score, city_score) / total_score if total_score > 0 else 0.5
        
        if mountain_score > city_score and mountain_score >= 2.0:
            trip_type = TripType.MOUNTAIN_HIKING
            use_trails = True
            use_pois = False  # Don't mix unless explicitly needed
            primary_source = "trails"
        elif city_score > mountain_score and city_score >= 2.0:
            trip_type = TripType.CITY_TOURISM
            use_trails = False
            use_pois = True
            primary_source = "pois"
        else:
            # Mixed or unclear signals
            trip_type = TripType.MIXED
            use_trails = True
            use_pois = True
            primary_source = "pois" if city_score >= mountain_score else "trails"
        
        # Map location to normalized region
        region = self._normalize_region(location)
        
        # Scoring weights (customize engine behavior)
        scoring_weights = self._get_scoring_weights(trip_type, group_type)
        
        return {
            "trip_type": trip_type,
            "use_trails": use_trails,
            "use_pois": use_pois,
            "use_restaurants": True,  # Always use restaurants for meals
            "primary_source": primary_source,
            "region": region,
            "scoring_weights": scoring_weights,
            "confidence": confidence,
            "signals": {
                "mountain_score": mountain_score,
                "city_score": city_score,
                "outdoor_prefs": list(outdoor_prefs),
                "cultural_prefs": list(cultural_prefs),
            }
        }
    
    def _normalize_region(self, location: str) -> str:
        """
        Normalize location string to canonical region name.
        
        Maps city names to their regions:
        - Zakopane → Tatry
        - Karpacz → Karkonosze
        - Etc.
        
        Args:
            location: City or region name from TripInput
        
        Returns:
            Canonical region name for database queries
        """
        # Mountain region mappings
        if location in ["Zakopane", "Tatry"]:
            return "Tatry"
        elif location in ["Kotlina Kłodzka", "Kłodzko"]:
            return "Kotlina Kłodzka"
        elif location in ["Karkonosze", "Karpacz", "Szklarska Poręba"]:
            return "Karkonosze"
        else:
            # City regions - return as-is
            return location
    
    def _get_scoring_weights(self, trip_type: str, group_type: str) -> Dict[str, float]:
        """
        Get custom scoring weights for engine based on trip type.
        
        Different trip types prioritize different POI characteristics:
        - Mountain hiking: elevation_gain, scenic_score, duration
        - City tourism: popularity_score, cultural_value, convenience
        
        Args:
            trip_type: TripType constant
            group_type: User's target_group
        
        Returns:
            Dict of scoring weight multipliers for engine.py
        """
        base_weights = {
            "popularity_bonus": 1.0,
            "must_see_bonus": 1.0,
            "preference_match": 1.0,
            "budget_penalty": 1.0,
            "family_bonus": 1.0,
        }
        
        if trip_type == TripType.MOUNTAIN_HIKING:
            # Boost scenic/adventure scoring
            base_weights["scenic_bonus"] = 1.5
            base_weights["elevation_bonus"] = 1.2
            base_weights["duration_bonus"] = 1.0
            
            # Family safety considerations
            if group_type == "family_kids":
                base_weights["family_safety"] = 2.0  # Strongly prioritize family_friendly trails
                base_weights["exposure_penalty"] = 2.0  # Penalize high exposure
        
        elif trip_type == TripType.CITY_TOURISM:
            # Boost cultural/popular POI
            base_weights["cultural_bonus"] = 1.5
            base_weights["convenience_bonus"] = 1.2
            base_weights["must_see_bonus"] = 1.5
        
        else:  # MIXED
            # Balanced weights
            pass
        
        return base_weights


# Convenience function for quick detection
def detect_trip_type(trip_input: TripInput) -> Dict[str, Any]:
    """
    Quick trip type detection (convenience wrapper).
    
    Args:
        trip_input: User's trip request
    
    Returns:
        Trip configuration dict
    
    Example:
        >>> from app.domain.router import detect_trip_type
        >>> config = detect_trip_type(trip_input)
        >>> if config["use_trails"]:
        >>>     trails = trail_repo.get_by_region(config["region"])
    """
    router = TripTypeRouter()
    return router.detect_trip_type(trip_input)
