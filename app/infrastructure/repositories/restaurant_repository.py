"""
Restaurant Repository - PostgreSQL access for dining places (ETAP 3).
Queries RestaurantDB table loaded in Phase 1.
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.infrastructure.database import RestaurantDB
from app.infrastructure.database.connection import SessionLocal


class RestaurantRepository:
    """
    Repository for RestaurantDB - dining places across 15 cities.
    
    Usage:
        repo = RestaurantRepository()
        lunch_spots = repo.get_by_meal_type("lunch", city="Kraków")
        family_restaurants = repo.get_family_friendly("Warszawa")
    """
    
    def __init__(self, session: Optional[Session] = None):
        """
        Initialize repository.
        
        Args:
            session: Optional SQLAlchemy session. If None, creates new session.
        """
        self.session = session or SessionLocal()
        self._owns_session = session is None
    
    def __del__(self):
        """Close session if we created it."""
        if self._owns_session and self.session:
            self.session.close()
    
    def get_all(self) -> List[RestaurantDB]:
        """Get all restaurants (249 total)."""
        return self.session.query(RestaurantDB).all()
    
    def get_by_id(self, restaurant_id: str) -> Optional[RestaurantDB]:
        """Get restaurant by ID."""
        return self.session.query(RestaurantDB).filter(RestaurantDB.id == restaurant_id).first()
    
    def get_by_city(self, city: str) -> List[RestaurantDB]:
        """
        Get all restaurants in a city.
        
        Args:
            city: City name (e.g., 'Kraków', 'Warszawa', 'Wrocław')
        
        Returns:
            List of restaurants in city
        """
        return self.session.query(RestaurantDB).filter(RestaurantDB.city == city).all()
    
    def get_by_meal_type(self, meal_type: str, city: Optional[str] = None) -> List[RestaurantDB]:
        """
        Get restaurants by meal type (CRITICAL for meal optimizer).
        
        Args:
            meal_type: 'lunch' or 'dinner'
            city: Optional city filter
        
        Returns:
            List of restaurants matching meal_type
        
        Example:
            # Get lunch spots in Kraków
            lunch_spots = repo.get_by_meal_type("lunch", city="Kraków")
        """
        query = self.session.query(RestaurantDB).filter(RestaurantDB.meal_type == meal_type)
        
        if city:
            query = query.filter(RestaurantDB.city == city)
        
        return query.all()
    
    def get_family_friendly(self, city: Optional[str] = None) -> List[RestaurantDB]:
        """
        Get family-friendly restaurants (children_friendly=True).
        
        Args:
            city: Optional city filter
        
        Returns:
            List of family-friendly restaurants
        """
        query = self.session.query(RestaurantDB).filter(RestaurantDB.children_friendly == True)
        
        if city:
            query = query.filter(RestaurantDB.city == city)
        
        return query.all()
    
    def get_by_price_level(self, max_price_level: int, city: Optional[str] = None) -> List[RestaurantDB]:
        """
        Get restaurants within budget.
        
        Args:
            max_price_level: Maximum price level (1-4)
            city: Optional city filter
        
        Returns:
            List of restaurants with price_level <= max_price_level
        """
        query = self.session.query(RestaurantDB).filter(RestaurantDB.price_level <= max_price_level)
        
        if city:
            query = query.filter(RestaurantDB.city == city)
        
        return query.all()
    
    def get_nearby(
        self,
        lat: float,
        lng: float,
        radius_km: float = 2.0,
        meal_type: Optional[str] = None
    ) -> List[RestaurantDB]:
        """
        Get restaurants near a location (for meal optimizer routing).
        
        Uses bounding box approximation for performance.
        1 degree lat ≈ 111 km, 1 degree lng ≈ 70 km (Poland)
        
        Args:
            lat: Latitude of current location
            lng: Longitude of current location
            radius_km: Search radius in kilometers (default 2km)
            meal_type: Optional meal_type filter ('lunch' or 'dinner')
        
        Returns:
            List of nearby restaurants
        
        Example:
            # Find lunch spots within 2km of current POI
            nearby = repo.get_nearby(49.2969, 19.9489, radius_km=2.0, meal_type="lunch")
        """
        # Bounding box approximation
        lat_delta = radius_km / 111.0  # 1 degree lat ≈ 111 km
        lng_delta = radius_km / 70.0   # 1 degree lng ≈ 70 km (Poland)
        
        query = self.session.query(RestaurantDB).filter(
            RestaurantDB.lat.between(lat - lat_delta, lat + lat_delta),
            RestaurantDB.lng.between(lng - lng_delta, lng + lng_delta)
        )
        
        if meal_type:
            query = query.filter(RestaurantDB.meal_type == meal_type)
        
        return query.all()
    
    def search(
        self,
        city: Optional[str] = None,
        meal_type: Optional[str] = None,
        cuisine_type: Optional[str] = None,
        max_price_level: Optional[int] = None,
        children_friendly: Optional[bool] = None,
        must_try: Optional[bool] = None
    ) -> List[RestaurantDB]:
        """
        Advanced search with multiple filters.
        
        Args:
            city: Filter by city
            meal_type: Filter by meal_type ('lunch' or 'dinner')
            cuisine_type: Filter by cuisine_type
            max_price_level: Filter by max price_level (1-4)
            children_friendly: Filter by children_friendly flag
            must_try: Filter by must_try flag
        
        Returns:
            List of restaurants matching ALL filters
        
        Example:
            # Get family-friendly lunch spots in Kraków, budget-friendly
            restaurants = repo.search(
                city="Kraków",
                meal_type="lunch",
                max_price_level=2,
                children_friendly=True
            )
        """
        query = self.session.query(RestaurantDB)
        
        if city:
            query = query.filter(RestaurantDB.city == city)
        
        if meal_type:
            query = query.filter(RestaurantDB.meal_type == meal_type)
        
        if cuisine_type:
            query = query.filter(RestaurantDB.cuisine_type == cuisine_type)
        
        if max_price_level:
            query = query.filter(RestaurantDB.price_level <= max_price_level)
        
        if children_friendly is not None:
            query = query.filter(RestaurantDB.children_friendly == children_friendly)
        
        if must_try is not None:
            query = query.filter(RestaurantDB.must_try == must_try)
        
        return query.all()
    
    def to_dict(self, restaurant: RestaurantDB) -> dict:
        """
        Convert RestaurantDB model to dict format compatible with engine.py.
        
        Engine expects POI-like dict structure with specific field names.
        This method maps RestaurantDB fields to engine-compatible format.
        
        Args:
            restaurant: RestaurantDB SQLAlchemy model
        
        Returns:
            Dict with engine-compatible structure
        """
        return {
            "id": restaurant.id,
            "type": "restaurant",  # NEW: distinguish from POI/trail
            "name": restaurant.name,
            "city": restaurant.city,
            "region": restaurant.region,
            
            # Location (engine uses lat/lng for routing)
            "lat": float(restaurant.lat) if restaurant.lat else 0.0,
            "lng": float(restaurant.lng) if restaurant.lng else 0.0,
            "address": restaurant.address,
            
            # CRITICAL: meal type for optimizer
            "meal_type": restaurant.meal_type,  # 'lunch' or 'dinner'
            "cuisine_type": restaurant.cuisine_type,
            "place_type": restaurant.place_type,
            
            # Timing (engine uses duration_min/max)
            "duration_min": restaurant.visit_duration_min,
            "duration_max": restaurant.visit_duration_max,
            "opening_hours": restaurant.opening_hours,
            "opening_hours_seasonal": restaurant.opening_hours_seasonal,
            
            # Pricing (engine uses for budget scoring)
            "price_level": restaurant.price_level,
            "avg_meal_cost": restaurant.avg_meal_cost,
            
            # Characteristics
            "atmosphere": restaurant.atmosphere,
            "space": restaurant.space,
            "reservations_required": restaurant.reservations_required,
            
            # Target group (JSON array)
            "target_groups": restaurant.target_group or [],
            "children_friendly": restaurant.children_friendly,
            
            # Quality signals (engine uses popularity_score for ranking)
            "popularity_score": float(restaurant.popularity_score) if restaurant.popularity_score else 0.0,
            "rating": float(restaurant.rating) if restaurant.rating else None,
            "must_try": restaurant.must_try,
            
            # Parking (engine uses parking_* fields)
            "parking_name": restaurant.parking_name,
            "parking_lat": float(restaurant.parking_lat) if restaurant.parking_lat else None,
            "parking_lng": float(restaurant.parking_lng) if restaurant.parking_lng else None,
            "parking_walk_time_min": restaurant.parking_walk_time_min,
            
            # Metadata
            "pro_tip": restaurant.pro_tip,
            "image_key": restaurant.image_key,
            "link_website": restaurant.link_website,
            "link_menu": restaurant.link_menu,
        }
    
    def get_all_as_dicts(self) -> List[dict]:
        """
        Get all restaurants as engine-compatible dicts.
        
        Convenience method for engine integration.
        
        Returns:
            List of restaurant dicts ready for engine.py
        """
        restaurants = self.get_all()
        return [self.to_dict(restaurant) for restaurant in restaurants]
