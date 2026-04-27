"""
ETAP 3 PHASE 7 - DESTINATION CLUSTERS CONFIGURATION

Definiuje 3 typy klastrów miast:
1. Urban Organism (Trójmiasto): Linked cities <30 km - single unified destination
2. Regional Cluster (Kotlina Kłodzka): Spa towns + cultural heritage - multi-day itineraries
3. Radius-based (Karkonosze): Mountain region <50 km - day trips to nearby attractions

Each cluster combines multiple cities' POI and restaurants into unified trip planning.
"""
from typing import Dict, List, Any
from enum import Enum


class ClusterType(Enum):
    """Types of destination clusters."""
    URBAN_ORGANISM = "urban_organism"       # Linked cities (e.g., Trójmiasto)
    REGIONAL_CLUSTER = "regional_cluster"   # Regional tourism area (e.g., Kotlina Kłodzka)
    RADIUS_BASED = "radius_based"           # Mountain/nature region (e.g., Karkonosze)


class DestinationClusters:
    """
    Configuration for all destination clusters in ETAP 3 Phase 7.
    
    Usage:
        >>> clusters = DestinationClusters()
        >>> config = clusters.get_cluster("Trójmiasto")
        >>> config["cities"]
        ['Gdańsk', 'Gdynia', 'Sopot']
    """
    
    # ================================================================
    # CLUSTER 1: TRÓJMIASTO (Urban Organism)
    # ================================================================
    TROJMIASTO = {
        "id": "trojmiasto",
        "name": "Trójmiasto",
        "display_name": "Trójmiasto (Gdańsk+Gdynia+Sopot)",
        "type": ClusterType.URBAN_ORGANISM,
        "cities": ["Gdańsk", "Gdynia", "Sopot"],
        
        # Statistics (from Phase 6 import)
        "total_attractions": 132,  # Gdańsk: 70, Gdynia: 33, Sopot: 29
        "total_restaurants": 62,   # Gdańsk: 21, Gdynia: 21, Sopot: 20
        
        # Cluster characteristics
        "max_distance_km": 30,  # Max distance between cities
        "primary_city": "Gdańsk",  # Main hub
        "region_type": "urban",
        
        # Trip planning behavior
        "unified_destination": True,  # Plan trips across all 3 cities as ONE destination
        "transit_between_cities": "public_transport",  # SKM (Szybka Kolej Miejska)
        "typical_days": [1, 2, 3],  # Suitable for 1-3 day trips
        
        # Scoring adjustments for engine
        "scoring_weights": {
            "location_diversity": 1.2,  # Bonus for visiting different cities
            "transit_penalty": 0.8,     # Lower penalty for cross-city transit (good public transport)
            "urban_accessibility": 1.1,  # Bonus for urban POI with good accessibility
        },
        
        # Tags & preferences
        "tags": ["urban", "sea", "culture", "nightlife", "beach", "history"],
        "recommended_preferences": ["culture", "architecture", "food", "shopping", "beach"],
        
        # Description
        "description": "Trójmiasto to zespół miejski na wybrzeżu Bałtyku składający się z Gdańska, Gdyni i Sopotu. "
                      "Miasta połączone są doskonałą komunikacją miejską (SKM), tworząc jednolitą destynację turystyczną. "
                      "Oferuje bogactwo zabytków, plażę, molo w Sopocie, stocznie i nowoczesne muzea."
    }
    
    # ================================================================
    # CLUSTER 2: KOTLINA KŁODZKA (Regional Cluster)
    # ================================================================
    KOTLINA_KLODZKA = {
        "id": "kotlina_klodzka",
        "name": "Kotlina Kłodzka",
        "display_name": "Kotlina Kłodzka (Kłodzko+Polanica+Kudowa)",
        "type": ClusterType.REGIONAL_CLUSTER,
        "cities": ["Kłodzko", "Polanica-Zdrój", "Kudowa-Zdrój"],
        
        # Statistics (from Phase 6 import)
        "total_attractions": 42,   # Kłodzko: 12, Polanica: 11, Kudowa: 19
        "total_restaurants": 34,   # Kłodzko: 11, Polanica: 9, Kudowa: 14
        
        # Cluster characteristics
        "max_distance_km": 25,  # Max distance between spa towns
        "primary_city": "Kłodzko",  # Historical hub
        "region_type": "spa_region",
        
        # Trip planning behavior
        "unified_destination": False,  # Plan multi-day itineraries combining towns
        "transit_between_cities": "car",  # Best by car (public transport limited)
        "typical_days": [2, 3, 4, 5],  # Suitable for 2-5 day trips (spa vacation)
        
        # Scoring adjustments for engine
        "scoring_weights": {
            "location_diversity": 1.3,  # Strong bonus for visiting multiple spa towns
            "transit_penalty": 1.2,     # Higher penalty for cross-town transit (car required)
            "spa_wellness": 1.4,        # Bonus for spa/wellness POI
            "slow_pace": 1.2,           # Bonus for relaxed pace (spa vacation)
        },
        
        # Tags & preferences
        "tags": ["spa", "wellness", "mountains", "nature", "relaxation", "culture", "history"],
        "recommended_preferences": ["wellness", "nature", "culture", "relaxation", "hiking"],
        
        # Description
        "description": "Kotlina Kłodzka to malowniczy region uzdrowiskowy w Sudetach, obejmujący Kłodzko (historyczne miasto), "
                      "Polanicę-Zdrój i Kudowę-Zdrój (uzdrowiska). Idealne miejsce na wielodniowy wypoczynek z połączeniem "
                      "spa, górskich spacerów i zwiedzania zabytków."
    }
    
    # ================================================================
    # CLUSTER 3: KARKONOSZE (Radius-based)
    # ================================================================
    KARKONOSZE = {
        "id": "karkonosze",
        "name": "Karkonosze",
        "display_name": "Karkonosze (Karpacz+Jelenia Góra+Szklarska)",
        "type": ClusterType.RADIUS_BASED,
        "cities": ["Karpacz", "Jelenia Góra", "Szklarska Poręba"],
        
        # Statistics (from Phase 6 import)
        "total_attractions": 56,   # Karpacz: 20, Jelenia Góra: 19, Szklarska: 17
        "total_restaurants": 40,   # Karpacz: 13, Jelenia Góra: 15, Szklarska: 12
        
        # Cluster characteristics
        "max_distance_km": 50,  # Max radius from center (mountain region)
        "primary_city": "Jelenia Góra",  # Regional hub
        "region_type": "mountain",
        
        # Trip planning behavior
        "unified_destination": False,  # Plan day trips to nearby attractions
        "transit_between_cities": "car",  # Car required (mountain roads)
        "typical_days": [2, 3, 4],  # Suitable for 2-4 day trips (mountain tourism)
        
        # Scoring adjustments for engine
        "scoring_weights": {
            "location_diversity": 1.1,  # Moderate bonus for visiting different mountain towns
            "transit_penalty": 1.3,     # Higher penalty for cross-town transit (mountain roads)
            "mountain_nature": 1.5,     # Strong bonus for mountain/nature POI
            "outdoor_activities": 1.4,  # Bonus for outdoor/hiking activities
            "scenic_views": 1.3,        # Bonus for scenic viewpoints
        },
        
        # Tags & preferences
        "tags": ["mountain", "hiking", "nature", "outdoor", "scenic_views", "winter_sports", "adventure"],
        "recommended_preferences": ["hiking", "nature", "outdoor", "scenic_views", "adventure"],
        
        # Description
        "description": "Karkonosze to najwyższe pasmo Sudetów, obejmujące Karpacz (pod Śnieżką), Jelenią Górą (brama Karkonoszy) "
                      "i Szklarską Porębę (zimowa stolica Polski). Region idealny dla miłośników górskich wędrówek, "
                      "wspinaczki i krajobrazów. Wielodniowe wycieczki pozwalają zwiedzić szlaki, wodospady i schroniska."
    }
    
    # ================================================================
    # CLUSTER REGISTRY
    # ================================================================
    ALL_CLUSTERS = {
        "Trójmiasto": TROJMIASTO,
        "Gdańsk+Gdynia+Sopot": TROJMIASTO,  # Alias
        "Kotlina Kłodzka": KOTLINA_KLODZKA,
        "Kłodzko+Polanica+Kudowa": KOTLINA_KLODZKA,  # Alias
        "Karkonosze": KARKONOSZE,
        "Karpacz+Jelenia Góra+Szklarska": KARKONOSZE,  # Alias
    }
    
    # ================================================================
    # CITY → CLUSTER MAPPING (Reverse lookup)
    # ================================================================
    CITY_TO_CLUSTER = {
        # Trójmiasto
        "Gdańsk": "trojmiasto",
        "Gdynia": "trojmiasto",
        "Sopot": "trojmiasto",
        
        # Kotlina Kłodzka
        "Kłodzko": "kotlina_klodzka",
        "Polanica-Zdrój": "kotlina_klodzka",
        "Kudowa-Zdrój": "kotlina_klodzka",
        
        # Karkonosze
        "Karpacz": "karkonosze",
        "Jelenia Góra": "karkonosze",
        "Szklarska Poręba": "karkonosze",
    }
    
    @classmethod
    def get_cluster(cls, cluster_name_or_city: str) -> Dict[str, Any]:
        """
        Get cluster configuration by cluster name or city name.
        
        Args:
            cluster_name_or_city: Cluster name (e.g., "Trójmiasto") or city name (e.g., "Gdańsk")
        
        Returns:
            Cluster config dict or None if not found
        
        Example:
            >>> DestinationClusters.get_cluster("Trójmiasto")
            {'id': 'trojmiasto', 'name': 'Trójmiasto', ...}
            
            >>> DestinationClusters.get_cluster("Gdańsk")
            {'id': 'trojmiasto', 'name': 'Trójmiasto', ...}  # Same result
        """
        # Try direct lookup
        if cluster_name_or_city in cls.ALL_CLUSTERS:
            return cls.ALL_CLUSTERS[cluster_name_or_city]
        
        # Try city → cluster mapping
        if cluster_name_or_city in cls.CITY_TO_CLUSTER:
            cluster_id = cls.CITY_TO_CLUSTER[cluster_name_or_city]
            # Find cluster by ID
            for cluster in [cls.TROJMIASTO, cls.KOTLINA_KLODZKA, cls.KARKONOSZE]:
                if cluster["id"] == cluster_id:
                    return cluster
        
        return None
    
    @classmethod
    def is_cluster_city(cls, city: str) -> bool:
        """
        Check if city belongs to any cluster.
        
        Args:
            city: City name
        
        Returns:
            True if city is part of cluster, False otherwise
        
        Example:
            >>> DestinationClusters.is_cluster_city("Gdańsk")
            True
            >>> DestinationClusters.is_cluster_city("Kraków")
            False
        """
        return city in cls.CITY_TO_CLUSTER
    
    @classmethod
    def get_cluster_cities(cls, cluster_name: str) -> List[str]:
        """
        Get list of cities in cluster.
        
        Args:
            cluster_name: Cluster name or alias
        
        Returns:
            List of city names or empty list if cluster not found
        
        Example:
            >>> DestinationClusters.get_cluster_cities("Trójmiasto")
            ['Gdańsk', 'Gdynia', 'Sopot']
        """
        cluster = cls.get_cluster(cluster_name)
        return cluster["cities"] if cluster else []
    
    @classmethod
    def get_all_cluster_names(cls) -> List[str]:
        """
        Get list of all cluster primary names.
        
        Returns:
            List of cluster names
        
        Example:
            >>> DestinationClusters.get_all_cluster_names()
            ['Trójmiasto', 'Kotlina Kłodzka', 'Karkonosze']
        """
        return ["Trójmiasto", "Kotlina Kłodzka", "Karkonosze"]
    
    @classmethod
    def get_cluster_summary(cls) -> Dict[str, Any]:
        """
        Get summary statistics for all clusters.
        
        Returns:
            Dict with cluster stats
        
        Example:
            >>> summary = DestinationClusters.get_cluster_summary()
            >>> summary["total_clusters"]
            3
            >>> summary["total_cities"]
            9
        """
        total_clusters = 3
        total_cities = 9
        total_attractions = (
            cls.TROJMIASTO["total_attractions"] +
            cls.KOTLINA_KLODZKA["total_attractions"] +
            cls.KARKONOSZE["total_attractions"]
        )
        total_restaurants = (
            cls.TROJMIASTO["total_restaurants"] +
            cls.KOTLINA_KLODZKA["total_restaurants"] +
            cls.KARKONOSZE["total_restaurants"]
        )
        
        return {
            "total_clusters": total_clusters,
            "total_cities": total_cities,
            "total_attractions": total_attractions,
            "total_restaurants": total_restaurants,
            "clusters": {
                "Trójmiasto": {
                    "cities": cls.TROJMIASTO["cities"],
                    "attractions": cls.TROJMIASTO["total_attractions"],
                    "restaurants": cls.TROJMIASTO["total_restaurants"],
                },
                "Kotlina Kłodzka": {
                    "cities": cls.KOTLINA_KLODZKA["cities"],
                    "attractions": cls.KOTLINA_KLODZKA["total_attractions"],
                    "restaurants": cls.KOTLINA_KLODZKA["total_restaurants"],
                },
                "Karkonosze": {
                    "cities": cls.KARKONOSZE["cities"],
                    "attractions": cls.KARKONOSZE["total_attractions"],
                    "restaurants": cls.KARKONOSZE["total_restaurants"],
                },
            }
        }
