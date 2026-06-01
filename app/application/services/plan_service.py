"""
Plan Service - generowanie planów podróży.
Łączy: TripInput → engine → PlanResponse
"""
import uuid
from typing import List, Dict, Any

from app.domain.models.trip_input import TripInput
from app.domain.models.plan import (
    PlanResponse,
    DayPlan,
    DayStartItem,
    DayEndItem,
    ParkingItem,
    TransitItem,
    AttractionItem,
    LunchBreakItem,
    DinnerBreakItem,
    FreeTimeItem,
    TicketInfo,
    ParkingInfo,
    ItemType,
    TransitMode,
    ParkingType,  # Dodano dla parking_type
)
from app.application.services.trip_mapper import trip_input_to_engine_params
from app.domain.planner.engine import build_day, plan_multiple_days, travel_time_minutes, is_open, haversine_distance
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.infrastructure.repositories import POIRepository, TrailRepository, RestaurantRepository  # ETAP 3 Phase 2
from app.infrastructure.storage import build_poi_image_url  # 11.03.2026 - Supabase Storage
from app.domain.router import detect_trip_type, TripType  # ETAP 3 Phase 2

# ETAP 2 Day 5: Quality + Explainability
from app.domain.planner.quality_checker import validate_day_quality, check_poi_quality
from app.domain.planner.explainability import explain_poi_selection


def _generate_day_title(day_items: list, day_num: int) -> str:
    """Generate a short descriptive title for a day based on its attractions.

    Rules:
    - 0 attractions  → "Dzień {day_num}"
    - 1 attraction   → name of that attraction
    - 2 attractions  → "Name1 i Name2"
    - 3+ attractions → "Name1, Name2 i więcej"
    """
    names = [
        item.name
        for item in day_items
        if hasattr(item, "type") and item.type == ItemType.ATTRACTION
    ]
    if not names:
        return f"Dzień {day_num}"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} i {names[1]}"
    return f"{names[0]}, {names[1]} i więcej"

# UAT Round 3 - FIX #1 (20.02.2026): Timeline Integrity Validator
# Validates all items form non-overlapping sequential timeline
# Detects overlaps: parking↔attraction, lunch↔attraction, free_time↔attraction
# Client feedback: ALL 10 tests had parking overlaps, walk_time ignored
from app.domain.validators import validate_and_heal_timeline


class PlanService:
    """
    Service dla generowania planów.
    
    ETAP 1: Używa oryginalnego engine.py + nowe funkcje biznesowe.
    ETAP 2: Rozbudowa o bardziej zaawansowaną logikę.
    """

    def __init__(self, poi_repository: POIRepository):
        self.poi_repo = poi_repository

    def generate_plan(self, trip_input: TripInput) -> PlanResponse:
        """
        Główna metoda generująca pełny plan podróży.
        
        Flow:
        1. TripInput → engine params (context, user, dates)
        2. Dla każdego dnia: build_day() z engine
        3. Konwersja engine output → PlanResponse items
        4. Dodanie parking logic (4.10)
        5. Dodanie cost estimation (4.11)
        6. Generowanie wszystkich item types (4.12)
        """
        
        print("\n" + "🔴"*50, flush=True)
        print("🔴 TEST #Problem11: generate_plan() CALLED", flush=True)
        print("🔴"*50 + "\n", flush=True)
        
        # Konwersja TripInput → engine params
        params = trip_input_to_engine_params(trip_input)
        
        context = params["context"]
        user = params["user"]
        dates = params["dates"]
        day_start = params["day_start"]
        day_end = params["day_end"]
        
        # ============================================================
        # ETAP 3 PHASE 2 + PHASE 7: INTELLIGENT TRIP TYPE ROUTING
        # ============================================================
        # Detect trip type and determine data sources
        router_config = detect_trip_type(trip_input)
        
        print(f"\n[ROUTER] Trip Type Detection:")
        print(f"  - Type: {router_config['trip_type']}")
        print(f"  - Primary Source: {router_config['primary_source']}")
        print(f"  - Use Trails: {router_config['use_trails']}")
        print(f"  - Use POIs: {router_config['use_pois']}")
        print(f"  - Use Restaurants: {router_config['use_restaurants']}")
        print(f"  - Region: {router_config['region']}")
        print(f"  - Confidence: {router_config['confidence']:.2f}")
        print(f"  - Signals: {router_config['signals']}\n")
        
        # PHASE 7: Check if cluster
        is_cluster = router_config['trip_type'] == 'cluster'
        cities_to_load = router_config.get('cities', [trip_input.location.city])  # Multi-city or single
        
        if is_cluster:
            print(f"[PHASE 7] CLUSTER MODE ACTIVE")
            print(f"  - Cluster: {router_config['region']}")
            print(f"  - Cities to load: {cities_to_load}")
            print(f"  - Cluster type: {router_config['cluster_config']['type'].value}\n")
        
        # Load data from appropriate sources
        all_pois_dict = []
        
        # Source 1: TrailDB (mountain hiking or mountain clusters like Karkonosze)
        if router_config["use_trails"]:
            try:
                trail_repo = TrailRepository()
                
                if is_cluster:
                    # PHASE 7: Load trails from all cluster cities
                    for city in cities_to_load:
                        region_name = self._normalize_region_for_trails(city)
                        trails_db = trail_repo.get_by_region(region_name)
                        trails_dict = [trail_repo.to_dict(trail) for trail in trails_db]
                        
                        # FIX #19.1 (03.05.2026): Map duration_min/max → time_min/max for engine compatibility
                        # Engine's choose_duration() reads time_min/time_max (POI field names)
                        # TrailDB uses duration_min/duration_max → must map before engine sees trails
                        for trail in trails_dict:
                            if "duration_min" in trail:
                                trail["time_min"] = trail["duration_min"]
                            if "duration_max" in trail:
                                trail["time_max"] = trail["duration_max"]
                            # FIX #25 (17.05.2026): Add city field for trail items (was empty in output)
                            if not trail.get("city"):
                                trail["city"] = city
                            # FIX #27 (17.05.2026): Add tags to trails so adventure/preference scoring works
                            # trail_repository.to_dict() has no 'tags' → adventure boost/penalty never applied
                            if not trail.get("tags"):
                                trail["tags"] = ["hiking", "mountain_trails", "active_sport", "outdoor", "alpine_activities"]
                        
                        all_pois_dict.extend(trails_dict)
                        print(f"[ROUTER] Loaded {len(trails_dict)} trails from TrailDB (city: {city}, region: {region_name})")
                else:
                    # Single-city mode
                    trails_db = trail_repo.get_by_region(router_config["region"])
                    trails_dict = [trail_repo.to_dict(trail) for trail in trails_db]
                    
                    # FIX #19.1 (03.05.2026): Map duration_min/max → time_min/max for engine compatibility
                    # Engine's choose_duration() reads time_min/time_max (POI field names)
                    # TrailDB uses duration_min/duration_max → must map before engine sees trails
                    for trail in trails_dict:
                        if "duration_min" in trail:
                            trail["time_min"] = trail["duration_min"]
                        if "duration_max" in trail:
                            trail["time_max"] = trail["duration_max"]
                        # FIX #25 (17.05.2026): Add city field for trail items (was empty in output)
                        if not trail.get("city"):
                            trail["city"] = trip_input.location.city
                        # FIX #27 (17.05.2026): Add tags to trails so adventure/preference scoring works
                        if not trail.get("tags"):
                            trail["tags"] = ["hiking", "mountain_trails", "active_sport", "outdoor", "alpine_activities"]
                    
                    all_pois_dict.extend(trails_dict)
                    print(f"[ROUTER] Loaded {len(trails_dict)} trails from TrailDB (region: {router_config['region']})")
            except Exception as e:
                print(f"[ROUTER] WARNING: Failed to load trails: {e}")
        
        # Source 2: POI Excel (city tourism or all clusters)
        if router_config["use_pois"]:
            try:
                if is_cluster:
                    # PHASE 7: Load POI from all cluster cities (multi_city_attractions.xlsx)
                    import os
                    from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
                    multi_city_excel_path = os.path.join("data", "multi_city_attractions.xlsx")
                    pois_excel = load_multi_city_poi(multi_city_excel_path, cities_to_load)
                    all_pois_dict.extend(pois_excel)
                    print(f"[ROUTER] Loaded {len(pois_excel)} POIs from Excel (CLUSTER: {cities_to_load})")
                else:
                    # Single-city mode
                    # FIX: Cross-city POI contamination (15.05.2026)
                    # Pass trip_input.location.city to filter POIs by City column
                    import os
                    from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
                    from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
                    requested_city = trip_input.location.city
                    pois_excel = load_zakopane_poi(self.poi_repo.excel_path, city_filter=requested_city)
                    if len(pois_excel) == 0:
                        # FIX: Fallback to multi_city_attractions.xlsx for cities not in zakopane.xlsx
                        # Supports: Kraków, Warszawa, Gdańsk, Wrocław, Poznań, etc.
                        multi_city_excel_path = os.path.join("data", "multi_city_attractions.xlsx")
                        pois_excel = load_multi_city_poi(multi_city_excel_path, [requested_city])
                        # FIX #68 (03.06.2026): Defensive guard against cross-city POI contamination.
                        # load_multi_city_poi filters by City column, but if Excel data has wrong City
                        # assignments (e.g., Wrocław POI tagged as Warszawa), this catches it.
                        # FIX #126: Use diacritic-insensitive comparison so 'Krakow'=='Kraków', etc.
                        import unicodedata as _ud
                        def _norm(s: str) -> str:
                            nfkd = _ud.normalize('NFKD', s.lower())
                            return ''.join(c for c in nfkd if not _ud.combining(c))
                        _city_norm = _norm(requested_city)
                        pois_excel = [
                            p for p in pois_excel
                            if _norm(p.get("city", "")) == _city_norm
                        ]
                        print(f"[ROUTER] Loaded {len(pois_excel)} POIs from multi_city Excel (city: {requested_city})")
                    else:
                        print(f"[ROUTER] Loaded {len(pois_excel)} POIs from Excel (city: {requested_city})")
                    all_pois_dict.extend(pois_excel)
            except Exception as e:
                print(f"[ROUTER] WARNING: Failed to load POIs: {e}")
        
        # Source 3: RestaurantDB (meals for all trip types)
        # NOTE: Restaurants loaded separately for meal optimizer, not mixed with attractions
        
        import sys
        
        # FIX #18.5: Map region to city for restaurant lookups
        # TrailDB uses regions ("Tatry"), RestaurantDB uses cities ("Zakopane")
        region_to_city_map = {
            "Tatry": "Zakopane",
            "Karkonosze": "Karpacz",
            "Kotlina Kłodzka": "Kłodzko"
        }
        restaurant_city = region_to_city_map.get(router_config["region"], router_config["region"])
        
        if router_config["use_restaurants"]:
            try:
                restaurant_repo = RestaurantRepository()
                
                if is_cluster:
                    # PHASE 7: Load restaurants from all cluster cities
                    all_restaurants = []
                    for city in cities_to_load:
                        restaurants_db = restaurant_repo.get_by_city(city)
                        all_restaurants.extend([restaurant_repo.to_dict(r) for r in restaurants_db])
                        print(f"[ROUTER] Loaded {len(restaurants_db)} restaurants from RestaurantDB (city: {city})", flush=True)
                    context["restaurants_available"] = all_restaurants
                    print(f"[ROUTER] TOTAL restaurants for cluster: {len(all_restaurants)}", flush=True)
                else:
                    # Single-city mode
                    restaurants_db = restaurant_repo.get_by_city(restaurant_city)
                    context["restaurants_available"] = [restaurant_repo.to_dict(r) for r in restaurants_db]
                    print(f"[ROUTER] Loaded {len(restaurants_db)} restaurants from RestaurantDB (city: {restaurant_city})", flush=True)
            except Exception as e:
                import traceback
                print(f"[ROUTER] ERROR: Failed to load restaurants: {e}", flush=True)
                print(f"[ROUTER] Traceback: {traceback.format_exc()}", flush=True)
                context["restaurants_available"] = []
        else:
            context["restaurants_available"] = []
        
        # Store router config in context for engine customization
        context["trip_type"] = router_config["trip_type"]
        context["scoring_weights"] = router_config["scoring_weights"]
        # FIX #111 (06.06.2026): Pass cluster signals so engine uses correct road speeds + drive limits
        context["signals"] = router_config.get("signals", {})
        
        # Fallback: If no data loaded, return empty plan
        if not all_pois_dict:
            print("[ROUTER] ERROR: No data sources available - returning empty plan")
            return PlanResponse(
                plan_id=str(uuid.uuid4()),
                version=1,
                days=[]
            )
        
        print(f"[ROUTER] TOTAL attractions/trails loaded: {len(all_pois_dict)}\n")
        # ============================================================
        
        # ============================================================
        # FIX #116 (29.05.2026): Generic preference availability validation
        # ============================================================
        # Problem (original FIX #Problem7): Underground preference check was hardcoded —
        #   only checked "underground" preference, city name was hardcoded as "Zakopane".
        # Fix: Check ALL location-specific (rare) preferences against loaded POI tags.
        #   Use actual city/region name. Apply fallback substitutions where defined.
        # ============================================================
        
        plan_warnings = []  # Collect warnings to add to PlanResponse
        user_preferences = user.get("preferences", [])
        # Build city label now (used in preference warnings AND later in poi_shortage warning)
        _pref_location_label = router_config.get("region", trip_input.location.city)
        
        # Rare/location-specific preferences: mapping to relevant POI tags and optional fallback
        # Add entries here when a preference is known to be location-dependent (not universally available)
        _RARE_PREFERENCE_CONFIG = {
            "underground": {
                "tags": ["underground", "cave", "mine", "podziemi", "jaskini"],
                "fallback": "history_mystery",
                "fallback_action": "Preferencja 'underground' zastąpiona przez 'history_mystery'",
            },
            "winter_sports": {
                "tags": ["skiing", "sledging", "snowboard", "narciarstwo", "ski", "winter_sport", "stok"],
                "fallback": None,
            },
            "water_park": {
                "tags": ["water_park", "aquapark", "waterslide", "aqua"],
                "fallback": "water_attractions",
                "fallback_action": "Preferencja 'water_park' zastąpiona przez 'water_attractions'",
            },
        }
        
        print(f"[PREFERENCE VALIDATION] Checking {len(user_preferences)} user preferences in {_pref_location_label}...")
        for _pref in list(user_preferences):  # iterate copy — loop may modify user["preferences"]
            _pref_cfg = _RARE_PREFERENCE_CONFIG.get(_pref)
            if not _pref_cfg:
                continue  # Common preference (cultural, relax, etc.) — always available
            
            _tags = _pref_cfg["tags"]
            _has_poi = any(
                any(tag in str(poi.get("tags", "")).lower() for tag in _tags)
                for poi in all_pois_dict
            )
            
            if _has_poi:
                print(f"[PREFERENCE VALIDATION] ✓ '{_pref}' available in {_pref_location_label}")
                continue
            
            # No matching POI — build warning
            _fallback = _pref_cfg.get("fallback")
            _action = _pref_cfg.get("fallback_action", f"Preferencja '{_pref}' niedostępna w {_pref_location_label}")
            _warning = {
                "type": "preference_not_available",
                "preference": _pref,
                "message": f"Brak atrakcji pasujących do preferencji '{_pref}' w {_pref_location_label}",
                "fallback": _fallback,
                "action_taken": _action,
            }
            plan_warnings.append(_warning)
            print(f"[PREFERENCE VALIDATION] ⚠️ '{_pref}' unavailable in {_pref_location_label} — {_action}")
            
            # Apply fallback substitution in user preferences
            if _fallback:
                user["preferences"] = [
                    _fallback if p == _pref else p
                    for p in user["preferences"]
                ]
                user_preferences = user["preferences"]
                print(f"[PREFERENCE VALIDATION] Updated preferences: {user['preferences']}")
        # ============================================================
        # END FIX #116
        # ============================================================
        
        # ETAP 2 - DAY 3 (15.02.2026): Multi-day routing
        # Route to appropriate planner based on trip length
        num_days = trip_input.trip_length.days
        
        # DEBUG: Check POI types BEFORE FIX #24 - WRITE TO FILE
        
        # Track POIs across all days (for multi-day)
        global_used_pois = set()
        
        if num_days > 1:
            # Multi-day plan: Use plan_multiple_days with cross-day tracking
            print(f"[PLAN SERVICE] Multi-day plan requested: {num_days} days")
            
            # ================================================================
            # FIX #24.5: POI SUFFICIENCY CHECK - Reduce days if insufficient quality POI
            # ================================================================
            print("="*80, flush=True)
            print(f"[FIX #24.5] POI SUFFICIENCY CHECK", flush=True)
            print(f"[FIX #24.5] Requested num_days: {num_days}", flush=True)
            
            # Count QUALITY POI (core or optional priority)
            # Note: all_pois_dict is a LIST of dicts, not a dict with keys
            # FIX #24.5: Use priority_level >= 6 (core=12, optional=6), excludes filler (2)
            # Excel zakopane.xlsx has: 3 core (priority=12), 0 secondary, 12 optional (priority=6), 16 filler (priority=2)
            # Result: 15 quality POI / 4.5 per day = 3 days max (very conservative to guarantee no empty days)
            # FIX #24.5.1 (08.05.2026): Increased from 2.5 to 3.5 → still Day 4 empty
            # FIX #24.5.2 (08.05.2026): Increased from 3.5 to 4.5 for maximum safety
            # Reason: Engine filters by opening_hours, target_group, budget, used_pois → actual usable < count
            # Testing showed: 15 POI → Days 1-3 use 11 POI, Day 4 has 0 (remaining 4 don't match criteria)
            quality_pois = [
                poi for poi in all_pois_dict  # Fixed: was all_pois_dict.values()
                if (
                    poi.get("type") == "poi"  # ONLY POI, not trails/restaurants
                    and (
                        # Priority: TEXT format "core"/"secondary"/"optional" OR NUMERIC >= 6 (core=12, optional=6)
                        (isinstance(poi.get("priority_level"), str) and poi.get("priority_level", "").strip().lower() in ["core", "secondary", "optional"])
                        or (isinstance(poi.get("priority_level"), (int, float)) and poi.get("priority_level", 0) >= 6)
                    )
                )
            ]
            
            recommended_poi_per_day = 4.5
            max_sustainable_days = int(len(quality_pois) / recommended_poi_per_day)
            
            print(f"[FIX #24.5] Quality POI count: {len(quality_pois)}", flush=True)
            print(f"[FIX #24.5] Recommended POI/day: {recommended_poi_per_day}", flush=True)
            print(f"[FIX #24.5] Max sustainable days (informational): {max_sustainable_days}", flush=True)
            
            # FIX #24.5 DISABLED: Day reduction was too aggressive.
            # Zakopane has only 11 quality POIs → max_sustainable_days=2 even for 3-7 day plans.
            # Engine handles low-quality POI counts by using filler POIs (priority=2) for later days.
            # Only block plan generation if there are literally zero POIs at all.
            if len(all_pois_dict) == 0:
                raise ValueError("No POIs available for the requested destination.")
            
            print(f"[FIX #24.5] ✓ No day adjustment - engine will handle POI distribution", flush=True)
            
            print("="*80, flush=True)
            # ================================================================
            # END FIX #24.5
            # ================================================================

            # ================================================================
            # FIX #112 (07.06.2026): POI SHORTAGE CHECK — small cluster cities
            # ================================================================
            # Problem: Small cities (Polanica-Zdrój=11, Kłodzko=12, Szklarska=17 POI) may
            # produce 1-2 meaningful days instead of 3-4 requested, because the engine
            # exhausts attractions by Day 3 → Days 3-4 contain only free_time blocks.
            #
            # FIX #24.5 (DISABLED) used quality-only POI count (4.5/day) — too aggressive:
            #   Zakopane had only 11 quality POI → max=2 days even for 7-day trips.
            # FIX #112: uses ALL attractions (POI + trails) with MIN 3/day threshold.
            #   Zakopane (59 total): 59//3 = 19 → no reduction ✓
            #   Polanica-Zdrój (11): 11//3 = 3 → reduces 4-day → 3-day ✓
            #   Kotlina cluster (42): 42//3 = 14 → no reduction ✓
            # ================================================================
            MIN_ATTRACTIONS_PER_DAY = 3  # Minimum attractions per day for a meaningful plan
            # FIX #113 (07.06.2026): With zones, count the smallest zone pool (worst case per day)
            _check_zones = sorted(set(
                p.get('zone', '').strip() for p in all_pois_dict if p.get('zone', '').strip()
            ))
            if _check_zones:
                _pois_no_zone_count = sum(1 for p in all_pois_dict if not p.get('zone', '').strip())
                _min_zone_count = min(
                    sum(1 for p in all_pois_dict if p.get('zone', '').strip() == z)
                    for z in _check_zones
                )
                _effective_pool = _pois_no_zone_count + _min_zone_count
            else:
                _effective_pool = len(all_pois_dict)
            max_feasible_days = max(1, _effective_pool // MIN_ATTRACTIONS_PER_DAY)

            print(f"[FIX #112] POI shortage check: {_effective_pool} effective attractions/day, {num_days} requested days", flush=True)
            print(f"[FIX #112] Max feasible days (@ {MIN_ATTRACTIONS_PER_DAY} attractions/day): {max_feasible_days}", flush=True)

            if max_feasible_days < num_days:
                location_label = _pref_location_label  # FIX #116: reuse label already computed above
                shortage_warning = {
                    "type": "poi_shortage",
                    "requested_days": num_days,
                    "feasible_days": max_feasible_days,
                    "attractions_available": len(all_pois_dict),
                    "message": (
                        f"Ograniczona baza atrakcji w {location_label} "
                        f"({len(all_pois_dict)} atrakcji). "
                        f"Plan zredukowany do {max_feasible_days} dni zamiast {num_days}, "
                        f"aby zapewnić pełne i sensowne dni wycieczki."
                    ),
                    "action_taken": f"Liczba dni zmniejszona z {num_days} do {max_feasible_days} (minimum {MIN_ATTRACTIONS_PER_DAY} atrakcje/dzień)"
                }
                plan_warnings.append(shortage_warning)
                print(f"[FIX #112] ⚠️ SHORTAGE: reducing {num_days} days → {max_feasible_days} days for {location_label}", flush=True)
                num_days = max_feasible_days
            else:
                print(f"[FIX #112] ✓ Sufficient attractions ({len(all_pois_dict)}) for {num_days} days", flush=True)
            # ================================================================
            # END FIX #112
            # ================================================================

            # Create contexts list (one per day)
            contexts = []
            for day_num in range(num_days):
                day_context = context.copy()
                day_context["date"] = dates[day_num]
                contexts.append(day_context)

            # ================================================================
            # FIX #113 (07.06.2026): ZONE SELECTOR — per-day POI pool based on zone
            # ================================================================
            # POIs have an optional 'zone' field (A/B/C) set by client in Excel.
            # Zone A = centre/most accessible, B = mid-range, C = far/outlier.
            # Multi-day trips rotate through available zones so each day visits
            # a coherent geographic area: Day 1→A, Day 2→B, Day 3→C, Day 4→A, …
            # POIs without a zone (zone='') are always included every day (backward compat).
            # Cities without any zoned POIs (Poznań, Gdańsk, etc.) are unaffected.
            # ================================================================
            def _build_zone_pools(all_pois, num_days):
                """Return list[list] of per-day POI pools respecting zone rotation."""
                # POIs without zone → always included
                pois_no_zone = [p for p in all_pois if not p.get('zone', '').strip()]
                # Collect sorted unique zones
                zones_present = sorted(set(
                    p['zone'].strip() for p in all_pois
                    if p.get('zone', '').strip()
                ))
                if not zones_present:
                    # No zone data at all → return same pool every day (no regression)
                    return None  # signals plan_multiple_days to use pois as-is
                # Group POIs by zone
                zone_buckets = {}
                for z in zones_present:
                    zone_buckets[z] = [p for p in all_pois if p.get('zone', '').strip() == z]
                print(f"[FIX #113] Zone selector: {len(zones_present)} zones {zones_present}, "
                      f"{len(pois_no_zone)} unzoned POIs always available")
                for z in zones_present:
                    print(f"[FIX #113]   Zone {z}: {len(zone_buckets[z])} POIs")
                # Build per-day pools
                pools = []
                for d in range(num_days):
                    zone = zones_present[d % len(zones_present)]
                    day_pool = pois_no_zone + zone_buckets[zone]
                    print(f"[FIX #113]   Day {d+1} → Zone {zone} ({len(day_pool)} POIs total)")
                    pools.append(day_pool)

                # FIX #140 (31.05.2026): Zone overflow — absorb adjacent zone when pool is too small.
                # Prevents empty/sparse days when a zone has very few POIs after filtering.
                _MIN_ZONE_POOL = 4
                _ZONE_OVERFLOW_MAP = {"C": "B", "B": "A"}  # C→B→A fallback chain
                for d in range(num_days):
                    pool = pools[d]
                    if len(pool) < _MIN_ZONE_POOL:
                        zone_this_day = zones_present[d % len(zones_present)]
                        overflow_zone = _ZONE_OVERFLOW_MAP.get(zone_this_day)
                        if overflow_zone and overflow_zone in zone_buckets:
                            extra = [p for p in zone_buckets[overflow_zone] if p not in pool]
                            pool = pool + extra
                            print(f"[FIX #140]   Day {d+1} Zone {zone_this_day} had only {len(pools[d])} POIs → merged Zone {overflow_zone} ({len(extra)} extra POIs)")
                        # Also merge in a second adjacent zone if still too small
                        if len(pool) < _MIN_ZONE_POOL and overflow_zone:
                            overflow_zone2 = _ZONE_OVERFLOW_MAP.get(overflow_zone)
                            if overflow_zone2 and overflow_zone2 in zone_buckets:
                                extra2 = [p for p in zone_buckets[overflow_zone2] if p not in pool]
                                pool = pool + extra2
                                print(f"[FIX #140]   Day {d+1} still sparse → also merged Zone {overflow_zone2} ({len(extra2)} extra POIs)")
                        # Deduplicate by id
                        _seen140 = set()
                        _deduped140 = []
                        for _p140 in pool:
                            _pid140 = _p140.get("id") or id(_p140)
                            if _pid140 not in _seen140:
                                _seen140.add(_pid140)
                                _deduped140.append(_p140)
                        pools[d] = _deduped140

                return pools

            _zone_pools = _build_zone_pools(all_pois_dict, num_days)
            # ================================================================
            # END FIX #113
            # ================================================================

            # Call multi-day planner
            _engine_warnings: list = []  # FIX #130
            engine_results = plan_multiple_days(
                pois=all_pois_dict,
                user=user,
                contexts=contexts,
                day_start=day_start,
                day_end=day_end,
                warnings_out=_engine_warnings,  # FIX #130
                pois_per_day=_zone_pools,  # FIX #113: per-day pools (None = use all pois)
            )
            plan_warnings.extend(_engine_warnings)  # FIX #130
            
        else:
            # Single-day plan: Use original build_day (Etap 1 behavior)
            print(f"[PLAN SERVICE] Single-day plan requested")
            context["date"] = dates[0]

            # FIX #113 (07.06.2026): Single-day zone selection — use Zone A (or only available zone)
            _zones_single = sorted(set(
                p.get('zone', '').strip() for p in all_pois_dict
                if p.get('zone', '').strip()
            ))
            if _zones_single:
                _zone_for_day = _zones_single[0]  # First zone (A) for single-day trips
                _pois_for_single_day = [
                    p for p in all_pois_dict
                    if not p.get('zone', '').strip() or p.get('zone', '').strip() == _zone_for_day
                ]
                print(f"[FIX #113] Single-day: using Zone {_zone_for_day} ({len(_pois_for_single_day)} POIs)")
            else:
                _pois_for_single_day = all_pois_dict

            _engine_warnings: list = []  # FIX #130
            engine_result = build_day(
                _pois_for_single_day,
                user,
                context,
                day_start,
                day_end,
                warnings_out=_engine_warnings  # FIX #130
            )
            plan_warnings.extend(_engine_warnings)  # FIX #130
            
            # Wrap in list for uniform processing
            engine_results = [engine_result]
        
        # Process each day's engine result
        days = []
        
        print(f"[GENERATE_PLAN] Processing {len(engine_results)} engine results")
        
        for day_num, engine_result in enumerate(engine_results):
            # HOTFIX #10.5: Debug logging - track POI IDs from engine
            engine_poi_ids = []
            for item in engine_result:
                if item.get("type") == "attraction" and item.get("poi"):
                    poi = item.get("poi", {})
                    engine_poi_ids.append(poi.get("id", "UNKNOWN"))
            print(f"[ENGINE OUTPUT] Day {day_num + 1} - POI IDs from engine: {engine_poi_ids}")
            
            # Update context for this day (for conversion step)
            day_context = context.copy()
            day_context["date"] = dates[day_num]
            # FIX #4 (15.02.2026): Add day_start and day_end to context for end-of-day logic
            day_context["day_start"] = day_start
            day_context["day_end"] = day_end
            
            # Konwersja engine result → PlanResponse items
            day_items = self._convert_engine_result_to_items(
                engine_result,
                day_start,
                day_end,
                day_context,  # Use day-specific context
                user,
                trip_input
            )
            
            # FIX #32 (19.05.2026): Add engine-placed POIs to global_used_pois BEFORE gap filling
            # Without this, gap filling for day N+1 could re-use POIs placed by the engine in day N.
            # Only gap-filling POIs were being tracked; engine POIs were invisible to plan_service's tracker.
            for item in day_items:
                if hasattr(item, 'poi_id') and item.poi_id:
                    global_used_pois.add(item.poi_id)
            
            # CRITICAL: Fill gaps >20 min AFTER transit times are calculated
            # This must run here because:
            # 1. Parking shifts first attraction time
            # 2. Transit start/end times are calculated in _convert_engine_result_to_items
            # 3. Gaps only appear after these adjustments
            # ETAP 2 - DAY 3: Pass global_used for cross-day tracking
            day_items = self._fill_gaps_in_items(
                day_items,
                all_pois_dict,
                day_context,  # Use day-specific context
                user,
                global_used_pois  # Pass global set for cross-day tracking
            )
            
            # ETAP 2 - DAY 3: Update global_used with POIs added by gap filling
            for item in day_items:
                if hasattr(item, 'poi_id') and item.poi_id:
                    global_used_pois.add(item.poi_id)
            
            # HOTFIX #10.5: Debug logging - track POI IDs after gap filling
            after_gap_filling_poi_ids = []
            for item in day_items:
                if hasattr(item, 'poi_id') and item.poi_id:
                    after_gap_filling_poi_ids.append(item.poi_id)
            print(f"[AFTER GAP FILLING] Day {day_num + 1} - POI IDs in result: {after_gap_filling_poi_ids}")
            
            # FIX #101 (29.05.2026): _update_transit_destinations moved to AFTER healing + removal.
            # Previously ran here (before healing), causing stale destinations after cascade shifts
            # and after POI removals in _remove_timeline_overlaps. Moved below.
            
            # ETAP 2 Day 5: Calculate day quality badges
            # Convert day_items to simple dict structure for validate_day_quality
            day_items_dict = []
            for item in day_items:
                if hasattr(item, 'model_dump'):
                    day_items_dict.append(item.model_dump())
                elif isinstance(item, dict):
                    day_items_dict.append(item)
            
            day_plan_for_validation = {"items": day_items_dict}
            day_quality_badges = validate_day_quality(day_plan_for_validation, all_pois_dict)
            
            # FIX #1 (20.02.2026 - UAT Round 3): Timeline Integrity Validation
            # PROBLEM: All 10 client tests had overlaps (parking↔attraction, lunch↔attraction)
            # SOLUTION: Validate + heal timeline before creating DayPlan
            # - Detects ALL overlap types (parking, transit, attraction, meals, free_time)
            # - Enforces walk_time gap: attraction.start >= parking.end + walk_time
            # - Auto-heals overlaps by cascading items forward
            healed_items, validation_warnings = validate_and_heal_timeline(
                day_items,
                day_number=day_num + 1,
                raise_on_failure=False  # Log warnings but don't block plan generation
            )
            
            # Use healed timeline (overlaps fixed)
            day_items = healed_items
            
            # Log validation warnings if any
            # FIX #100 (29.05.2026): timeline_overlap_fixed warnings are internal only.
            # FIX #92 forwarded them to frontend — client says they should NOT appear.
            # Now: only print to console, never added to plan_warnings.
            if validation_warnings:
                print(f"[TIMELINE VALIDATOR] Day {day_num + 1}:")
                for warning in validation_warnings:
                    print(f"  {warning}")
            
            # FIX #3 FAIL-SAFE (22.02.2026): Remove/truncate items that exceed day_end
            # Even if engine or gap filling creates items past day_end, this ensures compliance
            from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
            day_end_min = time_to_minutes(day_end)
            cleaned_items = []
            
            print(f"[DAY {day_num + 1} PROCESSING] Starting with {len(day_items)} items")
            
            for item in day_items:
                # Get dict using model_dump() or dict()
                if hasattr(item, 'model_dump'):
                    item_dict = item.model_dump()
                elif hasattr(item, 'dict'):
                    item_dict = item.dict()
                else:
                    cleaned_items.append(item)
                    continue
                
                item_type = item_dict.get('type')
                
                # Skip day_start (no end_time)
                if item_type == 'day_start':
                    cleaned_items.append(item)
                    continue
                
                # Check if item has end_time
                end_time_str = item_dict.get('end_time')
                if not end_time_str:
                    cleaned_items.append(item)
                    continue
                
                item_end_min = time_to_minutes(end_time_str)
                
                # If item ends before or at day_end, keep it
                if item_end_min <= day_end_min:
                    cleaned_items.append(item)
                else:
                    # Item exceeds day_end - truncate or skip
                    start_time_str = item_dict.get('start_time')
                    if start_time_str:
                        item_start_min = time_to_minutes(start_time_str)
                        
                        # If item starts before day_end, truncate it
                        if item_start_min < day_end_min:
                            new_duration = day_end_min - item_start_min
                            if new_duration >= 5:  # Keep only if >= 5 min remaining
                                # Clone item with truncated end_time
                                truncated_dict = item_dict.copy()
                                truncated_dict['end_time'] = day_end
                                truncated_dict['duration_min'] = new_duration
                                
                                # Recreate item with same type
                                ItemClass = type(item)
                                try:
                                    truncated_item = ItemClass(**truncated_dict)
                                    cleaned_items.append(truncated_item)
                                    print(f"[DAY_END ENFORCER] Day {day_num + 1}: Truncated {item_type} from {end_time_str} to {day_end} (was {item_end_min - day_end_min} min over)")
                                except Exception as e:
                                    print(f"[DAY_END ENFORCER] Day {day_num + 1}: Failed to truncate {item_type}: {e}")
                                    # Keep original if truncation fails
                                    cleaned_items.append(item)
                            else:
                                print(f"[DAY_END ENFORCER] Day {day_num + 1}: Removed {item_type} {start_time_str}-{end_time_str} (starts too close to day_end)")
                        else:
                            # Item starts after day_end - remove completely
                            print(f"[DAY_END ENFORCER] Day {day_num + 1}: Removed {item_type} {start_time_str}-{end_time_str} (starts after day_end {day_end})")
            
            day_items = cleaned_items
            
            # FIX #21 (03.05.2026 - CLIENT FEEDBACK Round 2 - Problem #1): Sort items by start_time
            # Root cause: Items are added by engine/validation/gap_filling in different orders
            # This creates chronological chaos where items appear out of order in response
            # Example: free_time 17:08-18:08 appears BEFORE attraction 17:20-17:55
            # Solution: Sort all items by start_time BEFORE consolidation
            
            day_items = self._sort_items_by_time(day_items)
            
            # FIX #Problem9 (14.05.2026): Remove timeline overlaps after sorting
            # Root cause: Gap filling can add both POI and free_time independently, creating overlaps
            # Solution: After sorting, remove overlapping items (prefer non-free_time items)
            day_items = self._remove_timeline_overlaps(day_items, day_num + 1)
            
            # FIX #71 (23.05.2026): Remove orphaned trailing transit items
            # Root cause: Engine occasionally outputs a transfer at end of day (after last attraction)
            # with no following attraction. FIX #62 in engine handles the overlap case, but
            # the trailing case (day-end break before POI is added) can still slip through.
            # Solution: strip any transit/transfer/parking items at the very end of the day list.
            TRANSIT_TYPES = {ItemType.TRANSIT, "transfer", "parking_walk", "buffer", "tickets_queue"}
            while day_items:
                last = day_items[-1]
                item_type_check = getattr(last, "type", None) or (last.get("type") if isinstance(last, dict) else None)
                if item_type_check in TRANSIT_TYPES:
                    day_items.pop()
                    print(f"[FIX #71] Removed orphaned trailing {item_type_check} at end of day {day_num + 1}")
                else:
                    break
            
            # FIX #101 (29.05.2026): Update transit destinations AFTER all healing + removal steps.
            # Previously ran BEFORE healing, so transit "to"/"from" could reference POIs that were
            # subsequently removed by day-end enforcement or _remove_timeline_overlaps.
            # Also removes orphaned transits (no following attraction) — see _update_transit_destinations.
            day_items = self._update_transit_destinations(day_items)
            
            # FIX #18 (03.05.2026 - CLIENT FEEDBACK MAY 3): Consolidate consecutive free_time blocks
            # Apply BEFORE adding day_end to ensure day_end stays last
            day_items = self._consolidate_consecutive_free_time_blocks(day_items)
            
            # FIX #35 (18.05.2026): Remove remaining technical buffers from final output
            # After consolidation, any still-marked is_technical_buffer items are tiny padding
            # blocks that look unnatural to users (e.g. "16 min", "17 min", "18 min").
            # Merged blocks get is_technical_buffer=False so they are kept.
            before_filter = len(day_items)
            day_items = [item for item in day_items if not getattr(item, "is_technical_buffer", False)]
            removed = before_filter - len(day_items)
            if removed:
                print(f"[FIX #35] Day {day_num + 1}: removed {removed} technical buffer item(s) from output")

            # FIX #119 (29.05.2026): Suppress micro free_time blocks (<30 min) from output.
            # After consolidation, very small free_time blocks (e.g. 8-28 min) can still remain —
            # they look like planning noise to users ("Czas wolny: 12 min") and add no value.
            # Threshold: anything under MIN_FREE_TIME_DISPLAY minutes is silently dropped.
            MIN_FREE_TIME_DISPLAY = 30
            before_ft_filter = len(day_items)
            day_items = [
                item for item in day_items
                if not (
                    hasattr(item, "type")
                    and item.type == ItemType.FREE_TIME
                    and getattr(item, "duration_min", 999) < MIN_FREE_TIME_DISPLAY
                )
            ]
            removed_ft = before_ft_filter - len(day_items)
            if removed_ft:
                print(f"[FIX #119] Day {day_num + 1}: removed {removed_ft} micro free_time block(s) (<{MIN_FREE_TIME_DISPLAY} min)")

            # FIX #4 (22.02.2026): Add day_end LAST - after ALL operations
            # This ensures day_end is always the last item in timeline
            # Previous bug: day_end was added in _convert_engine_result_to_items,
            # but gap filling could insert items after it
            day_items.append(DayEndItem(time=day_end))
            
            day_plan = DayPlan(
                day=day_num + 1,
                title=_generate_day_title(day_items, day_num + 1),
                items=day_items,  # Use healed items with no overlaps + day_end at end
                quality_badges=day_quality_badges  # ETAP 2 Day 5
            )
            
            days.append(day_plan)
        
        # Generuj plan_id
        plan_id = str(uuid.uuid4())
        
        # FIX #Problem8 (13.05.2026 - Round 2): Budget overflow warning
        # Check if any day's cost exceeds or approaches daily_limit
        daily_limit = None
        budget_dict = user.get("budget", {})
        if isinstance(budget_dict, dict):
            daily_limit = budget_dict.get("daily_limit")
        
        if daily_limit is not None and daily_limit > 0:
            print(f"[BUDGET WARNING CHECK] Daily limit: {daily_limit} PLN")
            
            for day_plan in days:
                day_num = day_plan.day
                day_cost = 0
                expensive_items = []  # Track items that cost >70% of daily limit
                
                # Sum up all costs in this day
                for item in day_plan.items:
                    item_cost = 0
                    if hasattr(item, 'cost_estimate') and item.cost_estimate:
                        item_cost = item.cost_estimate
                    elif hasattr(item, 'total_cost') and item.total_cost:
                        item_cost = item.total_cost
                    
                    if item_cost > 0:
                        day_cost += item_cost
                        
                        # Check if single item consumes >70% of budget
                        cost_ratio = item_cost / daily_limit
                        if cost_ratio > 0.70:
                            item_name = getattr(item, 'name', None) or getattr(item, 'poi_name', 'Unknown')
                            expensive_items.append({
                                "name": item_name,
                                "cost": item_cost,
                                "percentage": int(cost_ratio * 100)
                            })
                
                print(f"[BUDGET WARNING CHECK] Day {day_num}: {day_cost:.0f} PLN / {daily_limit} PLN ({day_cost/daily_limit*100:.0f}%)")
                
                # Add warning if day cost exceeds daily limit
                if day_cost > daily_limit:
                    warning = {
                        "type": "budget_exceeded",
                        "day": day_num,
                        "daily_limit": daily_limit,
                        "actual_cost": int(day_cost),
                        "overage": int(day_cost - daily_limit),
                        "message": f"Dzień {day_num}: Koszt przekracza dzienny limit o {int(day_cost - daily_limit)} PLN"
                    }
                    plan_warnings.append(warning)
                    print(f"[BUDGET WARNING] ⚠️ Day {day_num} exceeds budget: {day_cost:.0f} > {daily_limit} PLN")
                
                # Add warning if single item consumes >70% of daily budget
                if expensive_items:
                    for item_info in expensive_items:
                        warning = {
                            "type": "budget_constraint_active",
                            "day": day_num,
                            "daily_limit": daily_limit,
                            "expensive_item": item_info["name"],
                            "item_cost": item_info["cost"],
                            "percentage_of_budget": item_info["percentage"],
                            "message": f"Dzień {day_num}: '{item_info['name']}' pochłania {item_info['percentage']}% dziennego budżetu ({item_info['cost']} PLN z {daily_limit} PLN limitu)"
                        }
                        plan_warnings.append(warning)
                        print(f"[BUDGET WARNING] ⚠️ Day {day_num}: Expensive item '{item_info['name']}' = {item_info['percentage']}% of budget")
        
        # FIX #92 (28.05.2026): Add informational warnings for common trip scenarios.
        # These give users/clients useful context about plan characteristics.
        num_days_built = len(days)
        if num_days_built > 5:
            plan_warnings.append({
                "type": "long_trip_variety",
                "days": num_days_built,
                "message": (
                    f"Plan {num_days_built}-dniowy w Zakopanem: po dniu 4-5 różnorodność może być "
                    f"mniejsza ze względu na ograniczoną liczbę unikalnych atrakcji w bazie. "
                    f"Zalecamy łączenie z wycieczkami poza Zakopane (Nowy Targ, Czorsztyn, Bukowina)."
                ),
                "severity": "info",
            })

        # Travel style informational warning
        travel_style = user.get("travel_style", "")
        if travel_style == "adventure":
            plan_warnings.append({
                "type": "adventure_profile_info",
                "message": "Profil adventure: plan skupia się na aktywnych atrakcjach (górskie szlaki, sporty). Muzea i atrakcje pasywne są ograniczone do minimum.",
                "severity": "info",
            })

        return PlanResponse(
            plan_id=plan_id,
            version=1,
            days=days,
            warnings=plan_warnings  # FIX #Problem7: Include preference validation warnings
        )

    def _convert_engine_result_to_items(
        self,
        engine_result: List[Dict[str, Any]],  # Lista z engine.build_day()
        day_start: str,
        day_end: str,
        context: Dict[str, Any],
        user: Dict[str, Any],
        trip_input: TripInput
    ) -> List[Any]:
        """
        Konwertuje output z engine.build_day() na PlanResponse items.
        
        Engine zwraca listę dict z typami:
        - accommodation_start/end
        - lunch_break
        - attraction
        - transfer
        
        Konwertujemy na 7 typów items (4.12):
        - day_start
        - parking (4.10 - 1 na start, 15 min, z pierwszej atrakcji, tylko car)
        - transit
        - attraction (4.11 - z cost estimation)
        - lunch_break
        - free_time
        - day_end
        """
        items = []
        
        # FIX #120 (29.05.2026): Track reasons used so far this day to avoid repetition
        day_used_reasons: set = set()
        
        # 1. DAY_START
        items.append(DayStartItem(time=day_start))
        
        # 2. PARKING (4.10 - tylko dla car transport)
        has_car = "car" in (trip_input.transport_modes or [])
        
        # Znajdź pierwszą atrakcję
        first_attraction = None
        for item in engine_result:
            if item.get("type") == "attraction":
                first_attraction = item
                break
        
        # FIX #Problem11 (14.05.2026 - CLIENT FEEDBACK Round 2): Transit to first attraction
        # Problem: Brak transitu od hotelu/bazy do pierwszej atrakcji na start dnia
        # Solution: Jeśli pierwsza atrakcja jest poza Zakopane (>10 min dojazdu), dodaj transit
        # FIX #37 (19.05.2026): Gate this Zakopane-specific logic only for Zakopane city.
        # Bug: For Kraków, the first POI is ~90km from Zakopane centrum, so is_outside_zakopane=True
        # and a spurious transit "Zakopane (Hotel) → Wawel" was generated.
        # FIX #69 (03.06.2026): Gate strictly to Zakopane only — NOT all mountain cities.
        # Bug: region_type=="mountain" triggered this for Karpacz, Szklarska Poręba etc.
        # and hotel_location was hardcoded to Zakopane centrum (49.2992, 19.9496).
        # Result: Karpacz plans showed "Zakopane (Hotel) → [Karpacz attraction]" as transit.
        # Fix: Only apply for Zakopane city (hotel_location coords match Zakopane centrum).
        _is_zakopane_trip = (trip_input.location.city or "").lower() in ("zakopane",)
        if has_car and first_attraction and _is_zakopane_trip:
            from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
            from app.domain.planner.engine import travel_time_minutes
            
            first_poi = first_attraction.get("poi", {})
            first_address = first_poi.get("address", "")
            
            # Zakopane centrum (hotel default location) - GPS coordinates
            hotel_location = {
                "lat": 49.2992,  # Zakopane centrum (Krupówki)
                "lng": 19.9496
            }
            
            # Check if first attraction is outside Zakopane
            # Criteria: Address contains towns outside Zakopane (Białka, Bukowina, Chochołów, etc.)
            outside_town_keywords = ["Białka", "Bukowina", "Chochołów", "Witów", "Murzasichle"]
            is_outside_zakopane = any(keyword in first_address for keyword in outside_town_keywords)
            
            # Or calculate distance from Zakopane centrum
            first_lat = first_poi.get("lat")  # lowercase! POI from engine has lowercase keys
            first_lng = first_poi.get("lng")  # lowercase! POI from engine has lowercase keys
            
            if not is_outside_zakopane and first_lat and first_lng:
                from app.domain.planner.engine import haversine_distance
                distance_km = haversine_distance(hotel_location["lat"], hotel_location["lng"], first_lat, first_lng)
                # Consider outside if distance > 5 km from centrum
                is_outside_zakopane = distance_km > 5.0
            
            # Calculate transit time if outside
            if is_outside_zakopane and first_lat and first_lng:
                first_poi_location = {"lat": first_lat, "lng": first_lng}
                context_for_transit = {
                    "has_car": True,
                    "transport": "car"
                }
                transit_time_min = travel_time_minutes(hotel_location, first_poi_location, context_for_transit)
                
                # Add transit only if > 10 minutes (per requirement)
                if transit_time_min > 10:
                    day_start_min = time_to_minutes(day_start)
                    transit_start_min = day_start_min
                    transit_end_min = day_start_min + transit_time_min
                    
                    transit_to_first = TransitItem(
                        type=ItemType.TRANSIT,
                        start_time=minutes_to_time(transit_start_min),
                        end_time=minutes_to_time(transit_end_min),
                        duration_min=transit_time_min,
                        mode=TransitMode.CAR,
                        from_location="Zakopane (Hotel)",
                        to_location=first_poi.get("Name", "First Attraction")
                    )
                    items.append(transit_to_first)
        
        # PHASE 8 Feature #1: PARKING AS INFO ONLY (not separate waypoint)
        # REMOVED: ParkingItem creation at day start
        # Parking info is now embedded in AttractionItem (ParkingInfo object)
        # Backend uses parking data technically for walk_time calculations
        # Frontend displays parking as info, not as separate timeline item
        # 
        # OLD CODE (pre-Phase 8):
        # if has_car and first_attraction:
        #     first_poi = first_attraction.get("poi", {})
        #     parking_item = self._generate_parking_item(
        #         first_poi, day_start, first_attr_start
        #     )
        #     items.append(parking_item)
        
        # 3. KONWERTUJ ITEMS Z ENGINE
        lunch_added = False  # Track czy engine dodał lunch
        first_attraction_index = 0  # Track first attraction for timing correction
        last_transit_was_car = False  # Track if previous transit was by car (UAT Problem #9)
        last_parking_name = None  # Track last parking to avoid duplicates
        # FIX #3 (20.02.2026 - UAT Round 3): Track location changes instead of transit mode
        last_attraction_location = None  # (lat, lng) of previous attraction
        
        for item in engine_result:
            item_type = item.get("type")
            
            if item_type == "accommodation_start":
                # Już mamy day_start
                continue
            
            elif item_type == "accommodation_end":
                # Będzie day_end na końcu
                continue
            
            elif item_type == "lunch_break":
                # 4. LUNCH_BREAK (4.12) - z engine
                lunch_start = item.get("start_time", "12:00")
                lunch_end = item.get("end_time", "13:30")
                lunch_duration = item.get("duration_min", 90)
                
                # FIX #23 (03.05.2026 - CLIENT FEEDBACK Round 2 - Problem #1 - Timeline Overlap):
                # ROOT CAUSE: PHASE 8 FEATURE #4 moved lunch start_time BACKWARD by 10 min, creating overlaps
                # BEFORE: Engine lunch 13:28-14:08, plan_service moved to 13:18-14:08 → overlaps with attraction ending 13:25
                # SOLUTION: Keep engine's start_time (respects timeline continuity), don't shift backward
                # Meal buffer concept can be communicated in suggestions/description instead
                
                lunch_item = LunchBreakItem(
                    type=ItemType.LUNCH_BREAK,
                    start_time=lunch_start,  # FIX #23: Use engine's start_time (don't move backward!)
                    end_time=lunch_end,
                    duration_min=lunch_duration,
                    suggestions=item.get("suggestions", [
                        "Restauracja w centrum",
                        "Food court",
                        "Piknik w parku"
                    ])
                )
                items.append(lunch_item)
                lunch_added = True
            
            elif item_type == "dinner_break":
                # UAT Problem #11: DINNER_BREAK - z engine
                dinner_item = DinnerBreakItem(
                    type=ItemType.DINNER_BREAK,
                    start_time=item.get("start_time", "18:00"),
                    end_time=item.get("end_time", "19:30"),
                    duration_min=item.get("duration_min", 90),
                    suggestions=item.get("suggestions", [
                        "Regionalna restauracja",
                        "Bacówka",
                        "Karcma góralska"
                    ])
                )
                items.append(dinner_item)
            
            elif item_type == "attraction":
                # BUGFIX (18.02.2026 - UAT Problem #9): Add parking before attraction if needed
                # FIX #3 (20.02.2026 - UAT Round 3): Use location change detection
                # FIX #3.1 (20.02.2026 - UAT Round 3 Test-01): Remove parking_name requirement
                # Generate parking item BEFORE attraction if:
                # 1. User has car
                # 2. This is NOT the first attraction (already has parking at day start)
                # 3. Location changed from previous attraction (distance > 50m)
                # Note: Even if POI lacks parking_name, we create parking with fallback name
                
                poi = item.get("poi", {})
                current_parking_name = poi.get("parking_name", "")
                # FIX #3.2: POI dict has capitalized keys from Excel ("Lat", "Lng")
                current_lat = poi.get("Lat")
                current_lng = poi.get("Lng")
                
                # Check if location changed from previous attraction
                location_changed = False
                if last_attraction_location and current_lat and current_lng:
                    prev_lat, prev_lng = last_attraction_location
                    # Calculate distance in km
                    distance_km = haversine_distance(prev_lat, prev_lng, current_lat, current_lng)
                    # Location changed if distance > 0.05 km (50 meters)
                    location_changed = distance_km > 0.05
                    # DEBUG: print(f"[PARKING DEBUG] {poi.get('Name')}: distance={distance_km:.3f}km, location_changed={location_changed}")
                elif first_attraction_index > 0:
                    # No previous location to compare, but not first attraction
                    # Assume location changed (safe default - create parking)
                    location_changed = True
                    # DEBUG: print(f"[PARKING DEBUG] {poi.get('Name')}: no prev location, assuming changed=True")
                
                # PHASE 8 Feature #1: Parking timing adjustment (no waypoint creation)
                # Backend uses parking data for walk_time calculation
                # But ParkingItem is NOT created as separate timeline waypoint
                attr_start_time = item.get("start_time")  # Default: use engine time
                
                if (has_car and 
                    first_attraction_index > 0 and 
                    location_changed):
                    
                    # Calculate adjusted attraction start time (accounting for parking + walk)
                    # This ensures timeline realism even without ParkingItem waypoint
                    attr_start_time_orig = item.get("start_time")
                    
                    from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                    
                    parking_duration = 15  # Backend assumption
                    walk_time_raw = poi.get("parking_walk_time_min")
                    walk_time = int(walk_time_raw) if walk_time_raw and walk_time_raw > 0 else 5
                    
                    # FIX #74 (26.05.2026): Always anchor parking to transit_end, ignore engine's timing offset
                    # Root cause: Engine uses preferred_duration (tmin + 70%*(tmax-tmin)) but plan_service
                    # uses time_min directly → durations diverge significantly (e.g. 102 vs 35 min for a park)
                    # → engine's now advances much further → engine places next attraction much later
                    # → plan_service inherits that late start → creates large gap after transit end
                    # Fix: When last item is transit, always start parking immediately at transit_end.
                    attr_start_min = time_to_minutes(attr_start_time_orig)
                    parking_start_min = attr_start_min - parking_duration - walk_time
                    
                    if items:
                        last_item = items[-1]
                        if last_item.type == ItemType.TRANSIT:
                            # FIX #74: Always anchor to transit_end (not engine's possibly-late start_time)
                            transit_end_min = time_to_minutes(last_item.end_time)
                            parking_start_min = transit_end_min
                        elif parking_start_min < 0:
                            parking_start_min = 0
                    
                    # CASCADE UPDATE: Recalculate attraction start from actual parking times
                    parking_end_min = parking_start_min + parking_duration
                    attr_start_min = parking_end_min + walk_time
                    attr_start_time = minutes_to_time(attr_start_min)  # Corrected start time
                    
                    last_parking_name = current_parking_name
                
                # 5. ATTRACTION (4.11 - z cost estimation)
                
                # CLIENT FEEDBACK (30.01.2026 - Requirement #4): Parking timing fix
                # BUGFIX: Correct first attraction timing if parking exists
                # FIX #2: Only adjust if this is first attraction
                # FIX #4 (30.04.2026): Use current item (not first_attraction variable) for walk_time
                if first_attraction_index == 0 and has_car and first_attraction:
                    # First attraction with parking - adjust start time
                    from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                    from app.domain.planner.engine import is_open as engine_is_open
                    
                    parking_duration = 15
                    # FIX #4: Use current item's walk_time (not first_attraction found before loop)
                    walk_time_raw = item.get("poi", {}).get("parking_walk_time_min")
                    walk_time = int(walk_time_raw) if walk_time_raw and walk_time_raw > 0 else 5
                    
                    # Calculate corrected start time: day_start + parking + walk
                    # Example: 09:00 + 15min parking + 5min walk = 09:20
                    corrected_start_min = time_to_minutes(day_start) + parking_duration + walk_time
                    
                    # FIX #41 (Issue E): Check if POI is actually open at forced start time.
                    # Problem: Engine correctly schedules late-opening POIs (e.g. Kulig at 15:40),
                    # but this block forces first attraction to day_start+20min regardless.
                    # Solution: Only use corrected start if POI is open then; else keep engine time.
                    poi_for_check = item.get("poi", {})
                    poi_duration_for_check = poi_for_check.get("time_min", 60)
                    corrected_is_open = engine_is_open(
                        poi_for_check,
                        corrected_start_min,
                        poi_duration_for_check,
                        context.get("season", "all"),
                        context
                    )
                    if corrected_is_open:
                        attr_start_time = minutes_to_time(corrected_start_min)
                        print(f"[CLIENT_FEEDBACK #4] First attraction timing corrected: {day_start} + {parking_duration}min parking + {walk_time}min walk = {attr_start_time}")
                    else:
                        # Keep engine's scheduled time (POI not open at day start)
                        print(f"[FIX #41] First attraction NOT open at {minutes_to_time(corrected_start_min)} - keeping engine time {attr_start_time}")
                    
                    # Track first parking name
                    last_parking_name = item.get("poi", {}).get("parking_name", "")
                
                first_attraction_index += 1
                
                attraction_item = self._generate_attraction_item(
                    item.get("poi"),
                    attr_start_time,
                    user,
                    trip_input.group.type,
                    context,  # ETAP 2 Day 5: Pass context for explainability
                    day_used_reasons  # FIX #120: pass set for reason deduplication
                )
                items.append(attraction_item)
                
                # FIX #3 (20.02.2026): Track attraction location for next iteration
                if current_lat and current_lng:
                    last_attraction_location = (current_lat, current_lng)
                
                # Reset transit flag after attraction
                last_transit_was_car = False
            
            elif item_type == "transfer":
                # 6. TRANSIT
                # Engine doesn't provide start_time/end_time for transfers
                # Calculate from duration_min
                duration = item.get("duration_min", 10)

                # FIX #77 (27.05.2026): Close POIs (< 500m) get a short walk — skip full car transit + 15-min buffer
                # FIX #83 (27.05.2026): Increased walkable threshold from 0.5km to 1.0km.
                # Zakopane central POIs are typically 0.5–1.0 km apart, so 0.5 was too conservative.
                _transit_dist_km = item.get("distance_km", 999.0)
                WALKABLE_THRESHOLD_KM = 1.0  # FIX #83: was 0.5km
                if 0 < _transit_dist_km < WALKABLE_THRESHOLD_KM:
                    # Very close POIs: compute realistic walk time (walking ~4 km/h = 15 min/km), min 5 min
                    walk_min = max(5, int(_transit_dist_km * 15))
                    print(f"[FIX #77/#83] Close POIs {_transit_dist_km:.3f}km → short walk {walk_min}min (was {duration}min car transit + 15min buffer)")
                    duration = walk_min
                    # Use previous item's end_time as start, or default to 09:00
                    if items:
                        start_time = items[-1].end_time if hasattr(items[-1], 'end_time') else "09:00"
                    else:
                        start_time = "09:00"
                    from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                    start_minutes = time_to_minutes(start_time)
                    end_time = minutes_to_time(start_minutes + duration)
                    transit_item = TransitItem(
                        type=ItemType.TRANSIT,
                        start_time=start_time,
                        end_time=end_time,
                        duration_min=duration,
                        mode=TransitMode.WALK,
                        from_location=item.get("from", ""),
                        to_location=item.get("to", ""),
                    )
                    items.append(transit_item)
                    last_transit_was_car = False
                    continue

                # FIX #83 (27.05.2026): Duration-based fallback for POIs without GPS data.
                # POIs without coordinates have distance_km=999.0 (default). If the engine
                # estimated ≤10 min drive, the POIs are almost certainly walkable in Zakopane.
                elif _transit_dist_km >= 999.0 and duration <= 10:
                    walk_min = max(5, duration)
                    print(f"[FIX #83] Unknown dist + {duration}min drive → treating as short walk {walk_min}min")
                    if items:
                        start_time = items[-1].end_time if hasattr(items[-1], 'end_time') else "09:00"
                    else:
                        start_time = "09:00"
                    from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                    start_minutes = time_to_minutes(start_time)
                    end_time = minutes_to_time(start_minutes + walk_min)
                    transit_item = TransitItem(
                        type=ItemType.TRANSIT,
                        start_time=start_time,
                        end_time=end_time,
                        duration_min=walk_min,
                        mode=TransitMode.WALK,
                        from_location=item.get("from", ""),
                        to_location=item.get("to", ""),
                    )
                    items.append(transit_item)
                    last_transit_was_car = False
                    continue

                # FIX #103 (29.05.2026): Context-aware transit buffer instead of flat +15min.
                # Previously: always +15min regardless of distance (made 10→25, 20→35 look like placeholders).
                # Now: +5min for short trips (<5km), +10min for medium/long trips.
                # Rationale: Short urban walks need less buffer (parking/maps overhead is minimal).
                _buffer_min = 5 if _transit_dist_km < 5.0 else 10
                duration += _buffer_min
                print(f"[TIMING BUFFERS] Transit {_transit_dist_km:.1f}km: +{_buffer_min}min buffer (total: {duration}min)")
                
                # Use previous item's end_time as start, or default to 09:00
                if items:
                    prev_item = items[-1]
                    # Calculate start based on previous end
                    start_time = prev_item.end_time if hasattr(prev_item, 'end_time') else "09:00"
                else:
                    start_time = "09:00"
                
                # Calculate end_time from start + duration
                from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                start_minutes = time_to_minutes(start_time)
                end_minutes = start_minutes + duration
                end_time = minutes_to_time(end_minutes)
                
                # BUGFIX (31.01.2026 - Problem #5): Determine transit mode based on duration
                # Walk only for <10 min, car for ≥10 min (when user has car)
                # FIX #75 (26.05.2026): For city region_type prefer walk/public_transport over car
                has_car = "car" in (trip_input.transport_modes or [])
                region_type = context.get("region_type", "")
                
                if has_car and duration >= 10:
                    if region_type == "city":
                        # FIX #75: In cities, short transfers are walkable; medium → public transport
                        if duration <= 25:
                            mode = TransitMode.WALK
                        else:
                            mode = TransitMode.PUBLIC_TRANSPORT
                        last_transit_was_car = False
                    else:
                        mode = TransitMode.CAR
                        last_transit_was_car = True  # UAT Problem #9: Track car transit
                elif has_car and duration < 10:
                    mode = TransitMode.WALK
                    last_transit_was_car = False
                else:
                    # No car - use context transport or walk
                    transport = context.get('transport', 'walk')
                    mode_map = {
                        'walk': TransitMode.WALK,
                        'car': TransitMode.CAR,
                        'bus': TransitMode.PUBLIC_TRANSPORT,
                        'public_transport': TransitMode.PUBLIC_TRANSPORT,
                    }
                    mode = mode_map.get(transport, TransitMode.WALK)
                    last_transit_was_car = (mode == TransitMode.CAR)
                
                transit_item = TransitItem(
                    type=ItemType.TRANSIT,
                    start_time=start_time,
                    end_time=end_time,
                    duration_min=duration,
                    mode=mode,
                    from_location=item.get("from"),
                    to_location=item.get("to")
                )
                items.append(transit_item)
            
            elif item_type == "free_time":
                # 7. FREE_TIME - from engine fallback for gaps >20 min
                duration_min = item.get("duration_min", 30)
                # FIX #78 (27.05.2026): Add rotating suggestions and time-aware label for engine free_time items
                from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                _ft78e_start_min = time_to_minutes(item.get("start_time", "12:00"))
                _FT78_SETS_E = [
                    ["Spacer po centrum", "Kawa/herbata w kawiarni", "Czas na zdjęcia i relaks"],
                    ["Odpoczynek na ławce", "Zwiedzanie na własną rękę", "Zakupy pamiątek"],
                    ["Lody lub deser w kawiarni", "Zdjęcia panoramiczne", "Krótki spacer na świeżym powietrzu"],
                    ["Wizyta w lokalnym sklepiku", "Relaks przy kawie lub herbacie", "Spacer po okolicy"],
                    ["Fotografia podróżnicza", "Widokówki i pamiątki dla bliskich", "Chwila wytchnienia"],
                ]
                _ft78e_sugg = _FT78_SETS_E[(_ft78e_start_min // 30) % len(_FT78_SETS_E)]
                _ft78e_desc = item.get("description", "")
                if _ft78e_desc and _ft78e_desc not in ("Czas wolny", "free_time"):
                    _ft78e_label = _ft78e_desc
                elif _ft78e_start_min < time_to_minutes("11:00"):
                    _ft78e_label = "Poranny spacer i kawa" if duration_min >= 20 else "Chwila przed następną atrakcją"
                elif _ft78e_start_min < time_to_minutes("14:00"):
                    _ft78e_label = "Przerwa południowa" if duration_min >= 30 else "Krótka przerwa"
                elif _ft78e_start_min < time_to_minutes("17:00"):
                    _ft78e_label = "Popołudniowy relaks" if duration_min >= 30 else "Chwila odpoczynku"
                elif _ft78e_start_min < time_to_minutes("20:00"):
                    # FIX EXTRA4 (01.06.2026): Client approved 24.05.2026 — evening = Kolacja i Krupówki
                    _ft78e_label = "Kolacja i Krupówki: restauracja, spacer po Krupówkach" if duration_min >= 30 else "Czas przed kolacją"
                else:
                    _ft78e_label = "Wieczór: relaks i podsumowanie dnia" if duration_min >= 30 else "Chwila na dobranoc"
                free_time_item = FreeTimeItem(
                    type=ItemType.FREE_TIME,
                    start_time=item.get("start_time", "12:00"),
                    end_time=item.get("end_time", "12:30"),
                    duration_min=duration_min,
                    label=_ft78e_label,
                    suggestions=_ft78e_sugg[:3],
                    is_technical_buffer=(duration_min < 5)  # FIX #39: Only filter truly tiny (<5min) artifacts
                )
                items.append(free_time_item)
        
        # KRYTYCZNE (klientka 26.01): Lunch ZAWSZE musi być obecny!
        # Jeśli engine nie dodał, dodajemy ręcznie 12:00-13:30
        if not lunch_added:
            lunch_item = LunchBreakItem(
                type=ItemType.LUNCH_BREAK,
                start_time="12:00",
                end_time="13:30",
                duration_min=90,  # 1h 30min
                suggestions=[
                    "Restauracja lokalna",
                    "Bistro",
                    "Lunch na wynos"
                ]
            )
            # Wstaw lunch między items (ideally między atrakcjami)
            # TODO: lepsze pozycjonowanie - wstaw przed item który zaczyna się po 12:00
            items.append(lunch_item)
        
        # 7. FREE_TIME - gaps detection
        # TODO: Implementuj free_time gdy są luki w schedulu (ETAP 2)
        
        # 8. DAY_END - MOVED TO generate_plan() to ensure it's always last
        # FIX #4 (22.02.2026): day_end must be added AFTER gap filling and validation
        # items.append(DayEndItem(time=day_end))
        
        return items

    def _normalize_region_for_trails(self, city: str) -> str:
        """
        PHASE 7: Map city name to trail region name.
        
        Args:
            city: City name from cluster
        
        Returns:
            Region name for TrailRepository.get_by_region()
        
        Example:
            >>> self._normalize_region_for_trails("Karpacz")
            'Karkonosze'
            >>> self._normalize_region_for_trails("Zakopane")
            'Tatry'
        """
        # Mountain region mappings
        if city in ["Zakopane"]:
            return "Tatry"
        elif city in ["Kłodzko", "Polanica-Zdrój", "Kudowa-Zdrój"]:
            return "Kotlina Kłodzka"
        elif city in ["Karpacz", "Jelenia Góra", "Szklarska Poręba"]:
            return "Karkonosze"
        else:
            # Return as-is if no mapping found
            return city
    
    def _generate_parking_item(
        self,
        poi_dict: Dict[str, Any],  # POI jako dict z engine
        parking_start: str,
        attraction_start: str  # First attraction start time
    ) -> ParkingItem:
        """
        DEPRECATED (PHASE 8 Feature #1): Parking as info only, not waypoint.
        
        This function is no longer used in production code (Phase 8+).
        ParkingInfo is now embedded in AttractionItem.
        Kept for backward compatibility and testing.
        
        --- OLD DOCSTRING (pre-Phase 8) ---
        
        4.10: Parking logic - 1 parking na start dnia.
        
        BUGFIX (31.01.2026 - Problem #2): Use POI parking data or fallback to POI location
        - parking_address: Use POI parking_address or fallback to POI address
        - parking_lat/lng: Use POI parking_lat/lng or fallback to POI lat/lng
        
        BUGFIX: Parking timing corrected:
        - parking_start to parking_end: 15 min parking time
        - parking_end to attraction_start: walk_time
        - attraction starts AFTER parking + walk
        
        Example:
        - parking: 09:00-09:15 (15 min)
        - walk: 09:15-09:20 (5 min)
        - attraction: 09:20-... (starts AFTER walk)
        """
        from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
        
        # Fixed parking duration: 15 minutes
        PARKING_DURATION = 15
        
        # BUGFIX (02.02.2026): Walk time from POI data - use actual value if exists
        walk_time_raw = poi_dict.get("parking_walk_time_min")
        walk_time = int(walk_time_raw) if walk_time_raw and walk_time_raw > 0 else 5
        
        # Calculate parking end: start + 15 min
        parking_start_min = time_to_minutes(parking_start)
        parking_end_min = parking_start_min + PARKING_DURATION
        parking_end = minutes_to_time(parking_end_min)
        
        # Verify: attraction should start at parking_end + walk_time
        # If not, log warning (but don't block - engine controls timing)
        expected_attr_start = minutes_to_time(parking_end_min + walk_time)
        if expected_attr_start != attraction_start:
            # This is expected if engine scheduled attraction differently
            # We still create parking item but timing may look odd
            pass
        
        # BUGFIX (31.01.2026 - Problem #2): Proper fallback for parking location
        # Use parking_address or fallback to POI address
        parking_address = poi_dict.get("parking_address", "") or poi_dict.get("address", "")
        
        # Use parking_lat/lng or fallback to POI lat/lng
        # NOTE: parking_lat can be 0.0 (valid), use None check
        # FIX #3.2: POI dict has capitalized keys from Excel ("Lat", "Lng")
        parking_lat = poi_dict.get("parking_lat")
        if parking_lat is None or parking_lat == 0.0:
            parking_lat = poi_dict.get("Lat", 0.0)
        
        parking_lng = poi_dict.get("parking_lng")
        if parking_lng is None or parking_lng == 0.0:
            parking_lng = poi_dict.get("Lng", 0.0)
        
        # FIX #107 (28.05.2026): Read parking_type from POI data (was hardcoded PAID).
        # Excel has "paid"/"free" values — map to ParkingType enum. Default to PAID if missing.
        _pt107_raw = str(poi_dict.get("parking_type", "paid") or "paid").lower().strip()
        return ParkingItem(
            type=ItemType.PARKING,
            start_time=parking_start,
            end_time=parking_end,
            name=poi_dict.get("parking_name") or "Parking",
            address=parking_address,
            lat=parking_lat,
            lng=parking_lng,
            parking_type=ParkingType.PAID if _pt107_raw == "paid" else ParkingType.FREE,
            walk_time_min=walk_time
        )

    def _generate_attraction_item(
        self,
        poi_dict: Dict[str, Any],  # POI jako dict z engine
        start_time: str,
        user: Dict[str, Any],
        group_type: str,
        context: Dict[str, Any] = None,  # ETAP 2 Day 5: Add context for explainability
        day_used_reasons: set = None  # FIX #120: set of reasons already used this day (dedup)
    ) -> AttractionItem:
        """
        Generuje AttractionItem z cost estimation (4.11).
        
        ETAP 2 Day 5: Dodano explainability (why_selected) i quality badges.
        
        PHASE 8 FEATURE #4 (27.04.2026): Realistic timing buffers
        - Entry queue: +5 min for popular POI (popularity > 0.8)
        - Trail prep: +15 min for trail type (equipment, parking, start)
        
        Cost estimation (4.11):
        - ticket_normal jako baseline
        - family_kids: (2×normal + 2×reduced)
        - free_entry: 0
        """
        # FIX #19 (03.05.2026 - CLIENT FEEDBACK Problem #2): Use trail-specific duration fields
        # Problem: Trails show 60min (fallback) instead of real duration (4-13h for 86% of Tatry trails)
        # Root cause: POI have "time_min" field, Trails have "duration_min" and "duration_max" fields
        # Solution: Check poi_type and use appropriate duration field
        # FIX #19.1: duration_min/max → time_min/max mapping done during trail loading (lines ~118-130)
        poi_type = poi_dict.get("type", "poi")
        
        if poi_type == "trail":
            # Trails: Use duration_max for realistic planning (most people need max time, not minimum)
            # TrailDB stores time_min/time_max → to_dict() converts to duration_min/duration_max
            # FIX #19.1 also maps duration_min/max → time_min/max during loading for engine compatibility
            # FIX #69 (23.05.2026): Excel trails (Morskie Oko etc.) use time_max/time_min keys,
            # NOT duration_max/duration_min. Without this fallback → 60min default → 75min total (WRONG).
            visit_min = (
                poi_dict.get("duration_max") or
                poi_dict.get("time_max") or   # Excel trail fallback
                poi_dict.get("duration_min") or
                poi_dict.get("time_min") or   # Excel trail fallback
                60
            )
        else:
            # POI: Use time_min field from Excel
            visit_min = poi_dict.get("time_min", 60)
        
        # PHASE 8 FEATURE #4: Apply timing buffers
        popularity = poi_dict.get("popularity", 0.0)
        
        buffers_applied = []
        
        # Buffer 1: Entry queue for popular POI
        if poi_type != "trail" and popularity > 0.8:
            visit_min += 5
            buffers_applied.append("queue +5min")
        
        # Buffer 2: Trail prep (equipment, parking, start)
        if poi_type == "trail":
            visit_min += 15
            buffers_applied.append("trail prep +15min")
        
        if buffers_applied:
            print(f"[TIMING BUFFERS] {poi_dict.get('name', 'Unknown')}: {', '.join(buffers_applied)}")
        
        end_time = self._add_minutes(start_time, visit_min)
        
        # 4.11: Cost estimation (for entire group)
        estimated_cost = self._estimate_cost(poi_dict, user)
        
        # HOTFIX #10.5: Debug logging - track POI ID in attraction item creation
        poi_id_from_dict = poi_dict.get("id", "")
        print(f"[ATTRACTION ITEM] Creating item: poi_id={poi_id_from_dict}")
        
        # FIX #3.2: Extract lat/lng with fallback (same pattern as parking)
        lat_value = poi_dict.get("Lat")
        if lat_value is None or lat_value == 0.0:
            lat_value = poi_dict.get("lat", 0.0)
        
        lng_value = poi_dict.get("Lng")
        if lng_value is None or lng_value == 0.0:
            lng_value = poi_dict.get("lng", 0.0)
        
        # CLIENT FEEDBACK (30.01.2026 - Requirement #5): Ticket prices mapping
        # Extract ticket_normal/ticket_reduced with fallback (same pattern as lat/lng)
        # POI dict may have capitalized OR lowercase keys from different data sources
        ticket_normal_value = poi_dict.get("ticket_normal")
        if ticket_normal_value is None or ticket_normal_value == 0:
            ticket_normal_value = poi_dict.get("Ticket_normal", 0)
        if ticket_normal_value is None:
            ticket_normal_value = 0
        ticket_normal_value = float(ticket_normal_value) if ticket_normal_value else 0.0
        
        ticket_reduced_value = poi_dict.get("ticket_reduced")
        if ticket_reduced_value is None or ticket_reduced_value == 0:
            ticket_reduced_value = poi_dict.get("Ticket_reduced", 0)
        if ticket_reduced_value is None:
            ticket_reduced_value = 0
        ticket_reduced_value = float(ticket_reduced_value) if ticket_reduced_value else 0.0
        
        # ETAP 2 Day 5: Generate explainability and quality badges
        if context is None:
            context = {}  # Fallback to empty context if not provided
        
        # Calculate time_of_day from start_time
        hour = int(start_time.split(":")[0])
        if hour < 12:
            time_of_day = "morning"
        elif hour < 17:
            time_of_day = "afternoon"
        else:
            time_of_day = "evening"
        
        enriched_context = {
            **context,
            "time_of_day": time_of_day,
            "current_time": start_time
        }
        
        # Generate why_selected (top 3 reasons)
        why_selected = explain_poi_selection(
            poi=poi_dict,
            context=enriched_context,
            user=user
        )
        
        # FIX #120 (29.05.2026): Deduplicate reasons within the same day.
        # Problem: All 5 POIs in a cultural-preference day all said "Matches your cultural preference".
        # Solution: Filter out reasons already used earlier in the day; keep best remaining reasons.
        # day_used_reasons is None → skip (e.g. gap-fill context where set is not tracked).
        if day_used_reasons is not None:
            fresh_reasons = [r for r in why_selected if r not in day_used_reasons]
            if fresh_reasons:
                why_selected = fresh_reasons[:3]
            # If all reasons already used, keep original (better than empty list)
            day_used_reasons.update(why_selected)
        
        # Generate quality badges for this POI
        quality_badges = check_poi_quality(
            poi=poi_dict,
            context=enriched_context,
            user=user
        )
        
        # BUGFIX (19.02.2026 - UAT Round 2, Issue #7): Cost note for clarity
        # Client requirement: Make it explicit that cost_estimate is for entire group
        # Generate cost_note: "Total for your group of X people"
        group_size = user.get("group_size", 1)
        if group_size > 1:
            cost_note = f"Total for your group of {group_size} people"
        elif group_size == 1:
            cost_note = "For 1 person"
        else:
            cost_note = None  # Shouldn't happen, but handle gracefully
        
        # FIX #18.2 (03.05.2026 - CLIENT FEEDBACK Problem #5): Set cost_estimate=0 for free trails
        # FIX #109 (28.05.2026): Extend to ALL POI types with ticket=0, not just trails
        # Problem: cost_estimate includes parking/equipment even when base activity is free.
        # Solution: Override estimated_cost=0 when ticket_normal=0 AND ticket_reduced=0.
        # Optional extra costs (parking, equipment) explained in cost_breakdown_note.
        cost_breakdown_note = None
        if ticket_normal_value == 0 and ticket_reduced_value == 0:
            estimated_cost = 0
            if poi_type == "trail":
                cost_breakdown_note = "Wstęp na szlak darmowy. Opcjonalne koszty: parking (~20 PLN/dzień), prowiant."
            else:
                cost_breakdown_note = "Wstęp wolny. Opcjonalne koszty: parking (~10-20 PLN/dzień)."
        
        # FIX #26 (17.05.2026): parking cost 0 → null (unknown cost, not "free")
        _raw_parking_cost = poi_dict.get("parking_cost")
        # FIX #72 (03.06.2026): Parking name "Brak parkingu" + parking_type=free inconsistency.
        # Root cause: parking_name="" → "Brak parkingu", parking_type="" → defaults to FREE.
        # Frontend shows contradictory: "No parking" AND "parking_type: free".
        # Fix: Distinguish "no parking data" from "parking exists but is free/paid".
        _pname = poi_dict.get("parking_name") or ""
        _ptype_raw = str(poi_dict.get("parking_type", "") or "").lower().strip()
        if _ptype_raw == "paid":
            _parking_type_enum = ParkingType.PAID
        else:
            _parking_type_enum = ParkingType.FREE
        # When no parking data at all → show neutral "Brak danych o parkingu"
        _parking_display_name = _pname if _pname else "Brak danych o parkingu"
        return AttractionItem(
            type=ItemType.ATTRACTION,
            start_time=start_time,
            end_time=end_time,
            duration_min=visit_min,
            poi_id=poi_dict.get("id", ""),
            name=poi_dict.get("name", ""),
            description_short=poi_dict.get("description_short", ""),
            # FIX #3.2: Use extracted lat/lng values
            lat=lat_value,
            lng=lng_value,
            address=poi_dict.get("address", ""),
            # FIX: Cross-city POI contamination (15.05.2026) - pass city field to AttractionItem
            city=poi_dict.get("city", ""),
            # 11.03.2026 - Supabase Storage integration
            image_key=poi_dict.get("image_key"),
            image_url=build_poi_image_url(poi_dict.get("image_key", "")),
            cost_estimate=estimated_cost,  # Poprawiono z estimated_cost
            cost_note=cost_note,  # BUGFIX (19.02.2026 - Issue #7)
            ticket_info=TicketInfo(
                ticket_normal=int(ticket_normal_value),  # CLIENT_FEEDBACK #5: Use extracted values
                ticket_reduced=int(ticket_reduced_value),  # CLIENT_FEEDBACK #5: Use extracted values
                cost_breakdown_note=cost_breakdown_note  # FIX #18: Explain trail costs
            ),
            # PHASE 8 Feature #1: Rozszerzona ParkingInfo (address, type, cost, lat/lng)
            parking=ParkingInfo(
                name=_parking_display_name,
                address=poi_dict.get("parking_address", "") or poi_dict.get("address", ""),
                parking_type=_parking_type_enum,
                cost=int(_raw_parking_cost) if _raw_parking_cost else None,
                walk_time_min=poi_dict.get("parking_walk_time_min", 5) or 5,
                lat=poi_dict.get("parking_lat"),
                lng=poi_dict.get("parking_lng")
            ),
            pro_tip=poi_dict.get("pro_tip"),  # ADD pro_tip from POI
            why_selected=why_selected,  # ETAP 2 Day 5
            quality_badges=quality_badges  # ETAP 2 Day 5
        )

    def _estimate_cost(self, poi_dict: Dict[str, Any], user: Dict[str, Any]) -> int:
        """
        4.11: Cost estimation logic for ENTIRE GROUP.
        
        BUGFIX (16.02.2026 - Client Feedback):
        - Consistent calculation using group_size and children_age
        - Returns total cost for entire group (not per person)
        - Clear handling for each group type
        
        Logic:
        - free_entry POI: 0 PLN
        - family_kids: (adults × ticket_normal) + (children × ticket_reduced)
        - couples: group_size × ticket_normal (default: 2 adults)
        - friends: group_size × ticket_normal
        - seniors: group_size × ticket_reduced (assume senior discount)
        - solo: ticket_normal (1 person)
        - fallback (no price data): 50 PLN per person × group_size
        
        Args:
            poi_dict: POI data dict with ticket_normal, ticket_reduced, free_entry
            user: User dict with target_group, group_size, children_age
            
        Returns:
            Total estimated cost in PLN for entire group
        """
        free_entry = poi_dict.get("free_entry", False)
        
        if free_entry:
            return 0
        
        # FIX #68 (23.05.2026): Distinguish genuinely-free POI (ticket=0) from unknown price (ticket=None/NaN)
        # Root cause: Excel has no "free_entry" column → free_entry always False.
        # POIs like Krupówki, Kaplica have ticket_normal=0, ticket_reduced=0 → should be cost=0.
        # Previously: 0+0 with free_entry=False → 50 PLN/person fallback (WRONG).
        import math as _math
        def _parse_ticket(val):
            """Return float if valid number, None if missing/NaN/empty."""
            if val is None:
                return None
            try:
                f = float(val)
                if _math.isnan(f):
                    return None
                return f
            except (TypeError, ValueError):
                return None
        
        ticket_normal_raw = poi_dict.get("ticket_normal")
        ticket_reduced_raw = poi_dict.get("ticket_reduced")
        t_normal = _parse_ticket(ticket_normal_raw)
        t_reduced = _parse_ticket(ticket_reduced_raw)
        
        # Explicitly zero for both → genuinely free
        if t_normal == 0 and t_reduced == 0:
            return 0
        
        ticket_normal = t_normal if t_normal is not None else 0
        ticket_reduced = t_reduced if t_reduced is not None else 0
        
        # Extract user info
        group_type = user.get("target_group", "solo")
        group_size = user.get("group_size", 1)
        children_age = user.get("children_age")  # Only relevant for family_kids
        
        # BUGFIX: Fallback for POI without price data (both tickets unknown/None)
        if t_normal is None and t_reduced is None and not free_entry:
            # Use reasonable default: 50 PLN per person
            default_price = 50
            return group_size * default_price
        
        # Group-specific calculation
        if group_type == "family_kids":
            # Assume: 2 adults + (group_size - 2) children
            # If group_size is 4: 2 adults + 2 children
            # If group_size is 3: 2 adults + 1 child
            # If group_size is 5: 2 adults + 3 children
            adults = 2
            children = max(0, group_size - 2)
            return (adults * ticket_normal) + (children * ticket_reduced)
        
        elif group_type == "seniors":
            # Assume all group members are seniors (use reduced ticket)
            return group_size * ticket_reduced
        
        elif group_type == "solo":
            # Single person, normal ticket
            return ticket_normal
        
        else:
            # couples, friends, or any other group: group_size × ticket_normal
            return group_size * ticket_normal

    def _generate_transit_item(
        self,
        from_poi_data: Dict[str, Any],
        to_poi_data: Dict[str, Any],
        start_time: str,
        context: Dict[str, Any]
    ) -> TransitItem:
        """Generuje TransitItem między dwoma POI."""
        from_poi = from_poi_data["poi"]
        to_poi = to_poi_data["poi"]
        
        # Oblicz czas przejazdu (uproszczony)
        # TODO: użyć travel_time_minutes z engine
        travel_min = 15  # default
        
        end_time = self._add_minutes(start_time, travel_min)
        
        # Określ mode na podstawie context["transport"]
        transport = context.get("transport", "walk")
        mode_map = {
            "walk": TransitMode.WALK,
            "car": TransitMode.CAR,
            "bus": TransitMode.PUBLIC_TRANSPORT,
            "public_transport": TransitMode.PUBLIC_TRANSPORT,
        }
        mode = mode_map.get(transport, TransitMode.WALK)
        
        return TransitItem(
            type=ItemType.TRANSIT,
            start_time=start_time,
            end_time=end_time,
            duration_min=travel_min,
            mode=mode,
            from_name=from_poi.name,
            to_name=to_poi.name,
            from_lat=from_poi.lat,
            from_lng=from_poi.lng,
            to_lat=to_poi.lat,
            to_lng=to_poi.lng
        )

    def _fill_gaps_in_items(
        self,
        items: List[Any],
        all_pois: List[Dict[str, Any]],
        context: Dict[str, Any],
        user: Dict[str, Any],
        global_used: set = None
    ) -> List[Any]:
        """
        Fill gaps >15 min between items with POI or free_time.
        
        BUGFIX (31.01.2026 - Problem #4): ACTIVE gap filling
        FIX #4 (15.02.2026): Lower threshold 20→15 min, add end-of-day free_time
        Philosophy: "Najlepiej jakby w ogóle nie było luk czasowych, szczególnie jak atrakcje są otwarte"
        
        NEW LOGIC:
        1. Detect gap >15 min
        2. TRY: Find available POI that fits in gap (is_open, duration fits)
        3. TRY: Prefer shorter, nearby POI
        4. LAST RESORT: Add free_time only if NO POI available
        
        This runs AFTER _convert_engine_result_to_items so all items have
        proper start_time/end_time including transit items.
        
        Args:
            items: List of PlanResponse items (Pydantic models)
            all_pois: All available POIs
            context: Trip context
            user: User preferences
            
        Returns:
            Updated list of items with gaps filled
        """
        print("[GAP FILLING] ACTIVE mode - try POI first, free_time LAST RESORT")
        
        # HOTFIX (02.02.2026): Get attraction limits for target group
        from ...domain.planner.engine import GROUP_ATTRACTION_LIMITS
        target_group = user.get("target_group", "solo")
        limits = GROUP_ATTRACTION_LIMITS.get(target_group, {"hard": 8})
        hard_limit = limits["hard"]
        
        result = []
        
        # ETAP 2 - DAY 3 (15.02.2026): Initialize from global_used for cross-day tracking
        used_poi_ids = set(global_used) if global_used is not None else set()
        
        attraction_count = 0  # Count attractions to enforce limit
        
        # Collect POIs already used in plan and count attractions
        for item in items:
            if hasattr(item, 'poi_id'):
                used_poi_ids.add(item.poi_id)
                attraction_count += 1
        
        for i, item in enumerate(items):
            result.append(item)
            item_dict = item.dict()
            item_type = item_dict['type']
            
            # Get end time of current item
            # FIX #4.2 (20.02.2026): Include free_time and dinner_break for gap detection
            # Client issue (test-02): Gaps after free_time or dinner_break were not detected
            current_end = None
            if item_type in ['attraction', 'transit', 'lunch_break', 'parking', 'free_time', 'dinner_break']:
                if 'end_time' in item_dict:
                    current_end = time_to_minutes(item_dict['end_time'])
                    # Add walk_time for parking
                    if item_type == 'parking' and 'walk_time_min' in item_dict:
                        current_end += item_dict['walk_time_min']
            elif item_type == 'day_start':
                if 'time' in item_dict:
                    current_end = time_to_minutes(item_dict['time'])
            
            if current_end is None:
                continue
            
            # Get last POI location for travel time calculation
            last_poi_location = None
            if item_type == 'attraction':
                last_poi_location = {
                    'lat': item_dict.get('lat', 0),
                    'lng': item_dict.get('lng', 0)
                }
            
            # Check gap to next item
            if i < len(items) - 1:
                next_item = items[i + 1].dict()
                next_type = next_item['type']
                
                # Get next start time
                # FIX #4.1 (20.02.2026): Include parking in gap detection
                # FIX #4.4 (20.02.2026): Include day_end in gap detection
                # Client issue (test-02): Gaps before day_end were not detected
                next_start = None
                if next_type in ['attraction', 'lunch_break', 'parking', 'dinner_break', 'free_time']:
                    if 'start_time' in next_item:
                        next_start = time_to_minutes(next_item['start_time'])
                elif next_type == 'day_end':
                    if 'time' in next_item:
                        next_start = time_to_minutes(next_item['time'])
                
                if next_start is not None:
                    gap = next_start - current_end
                    
                    print(f"[GAP FILLING] {item_type} ends {current_end} -> {next_type} starts {next_start} = GAP {gap} min")
                    
                    # FIX #7 (22.02.2026 - UAT Round 3, TEST-03 Issue):
                    # CRITICAL: Skip gap filling between transit and parking
                    # Problem: Engine adds transit, then plan_service adds parking, gap_filling detects gap
                    # Solution: Transit->Parking is a natural sequence (travel + parking arrival), NO free_time needed
                    # Client feedback (TEST-03): 3 occurrences of "transit -> free_time -> parking" pattern
                    if item_type == 'transit' and next_type == 'parking':
                        print(f"[GAP FILLING] SKIP transit->parking gap ({gap} min) - natural travel sequence")
                        continue
                    
                    # FIX #4.3 (20.02.2026): Removed skip condition for lunch_break
                    # Client requirement (test-02): ALL gaps >15 min must be filled, including before meal breaks
                    
                    # FIX #39 (CLIENT FEEDBACK): REMOVED is_open skip that was hiding gaps
                    # BEFORE: If next attraction is open NOW, skip gap filling (assume attraction starts earlier)
                    # PROBLEM: Attraction start time was already fixed by parking computation (+15min)
                    #          so the attraction NEVER started earlier, leaving invisible gaps in the timeline
                    # EXAMPLE: transit ends 12:20, attraction starts 12:36 (parking took 16min)
                    #          is_open() returned True → gap filling skipped → 12:20-12:36 was INVISIBLE
                    # FIX: Always fill gaps >15 min regardless of POI open status
                    
                    # FIX #4 (15.02.2026): Lower threshold from 20 to 15 min
                    if gap > 15:
                        # HOTFIX (02.02.2026): Check if attraction limit reached
                        if attraction_count >= hard_limit:
                            print(f"[GAP FILLING] ✗ SKIP - attraction limit reached ({attraction_count}/{hard_limit})")
                            # Add free_time instead of POI
                            # FIX #76 (26.05.2026): Cap free_time at 60 min to match engine's internal cap.
                            # Bug: When seniors/family_kids hit attraction hard_limit, the entire
                            # remaining gap (120-200+ min) was inserted as ONE free_time block.
                            # Engine itself never creates free_time >60 min; this aligns gap_filler.
                            day_end_str = context.get("day_end")
                            free_duration = min(60, gap)  # FIX #76: was: gap (uncapped)
                            
                            if day_end_str:
                                day_end_min = time_to_minutes(day_end_str)
                                free_time_end_proposed = current_end + free_duration
                                
                                # If proposed end exceeds day_end, cap it
                                if free_time_end_proposed > day_end_min:
                                    free_duration = day_end_min - current_end
                                    if free_duration < 5:  # Skip if too short
                                        print(f"[GAP FILLING] SKIP free_time - would exceed day_end")
                                        continue
                                    print(f"[GAP FILLING] CAPPED free_time to day_end: {gap} min -> {free_duration} min")
                            
                            free_time_start = minutes_to_time(current_end)
                            free_time_end = minutes_to_time(current_end + free_duration)
                            
                            # FIX #Problem9 (14.05.2026): Check for overlap before adding free_time
                            # Bug: Gap filling adds free_time without checking if it overlaps with existing items
                            # This can happen when POI selection changes due to lunch timing fixes
                            # Solution: Convert result to dict list, check overlap, skip if conflict
                            result_dicts = [item.dict() if hasattr(item, 'dict') else item for item in result]
                            overlaps_detected = False
                            for existing_item in result_dicts:
                                if 'start_time' in existing_item and 'end_time' in existing_item:
                                    exist_start = time_to_minutes(existing_item['start_time'])
                                    exist_end = time_to_minutes(existing_item['end_time'])
                                    free_start_min = current_end
                                    free_end_min = current_end + free_duration
                                    
                                    # Check if time ranges overlap
                                    if not (free_end_min <= exist_start or free_start_min >= exist_end):
                                        overlaps_detected = True
                                        print(f"[GAP FILLING] OVERLAP DETECTED: free_time {free_time_start}-{free_time_end} would conflict with {existing_item.get('type')} {existing_item.get('start_time')}-{existing_item.get('end_time')} - SKIPPING")
                                        break
                            
                            if overlaps_detected:
                                continue  # Skip adding this free_time
                            
                            # FIX #78 (27.05.2026): Add rotating suggestions and time-aware label for hard-limit free_time
                            _FT78_SETS_HL = [
                                ["Spacer po centrum", "Kawa/herbata w kawiarni", "Czas na zdjęcia i relaks"],
                                ["Odpoczynek na ławce", "Zwiedzanie na własną rękę", "Zakupy pamiątek"],
                                ["Lody lub deser w kawiarni", "Zdjęcia panoramiczne", "Krótki spacer na świeżym powietrzu"],
                                ["Wizyta w lokalnym sklepiku", "Relaks przy kawie lub herbacie", "Spacer po okolicy"],
                                ["Fotografia podróżnicza", "Widokówki i pamiątki dla bliskich", "Chwila wytchnienia"],
                            ]
                            _ft78hl_sugg = _FT78_SETS_HL[(current_end // 30) % len(_FT78_SETS_HL)]
                            if current_end < time_to_minutes("11:00"):
                                _ft78hl_label = "Poranny spacer i kawa" if free_duration >= 20 else "Chwila przed następną atrakcją"
                            elif current_end < time_to_minutes("14:00"):
                                _ft78hl_label = "Przerwa południowa" if free_duration >= 30 else "Krótka przerwa"
                            elif current_end < time_to_minutes("17:00"):
                                _ft78hl_label = "Popołudniowy relaks" if free_duration >= 30 else "Chwila odpoczynku"
                            elif current_end < time_to_minutes("20:00"):
                                # FIX EXTRA4 (01.06.2026): Client approved 24.05.2026 — evening = Kolacja i Krupówki
                                _ft78hl_label = "Kolacja i Krupówki: restauracja, spacer po Krupówkach" if free_duration >= 30 else "Czas przed kolacją"
                            else:
                                _ft78hl_label = "Wieczór: relaks i podsumowanie dnia" if free_duration >= 30 else "Chwila na dobranoc"
                            result.append(FreeTimeItem(
                                type=ItemType.FREE_TIME,
                                start_time=free_time_start,
                                end_time=minutes_to_time(current_end + free_duration),
                                duration_min=free_duration,
                                label=_ft78hl_label,
                                suggestions=_ft78hl_sugg[:3],
                                is_technical_buffer=(free_duration < 5)  # FIX #39: Only filter truly tiny (<5min) artifacts
                            ))
                            continue
                        
                        # BUGFIX (31.01.2026 - Problem #4): TRY find POI first before free_time
                        # CLIENT FEEDBACK (30.01.2026): Prefer SOFT POI for gaps >20 min
                        # Soft POI criteria:
                        # - intensity: low (or medium if very short)
                        # - time_min: 10-30 min
                        # - must_see_score: low (0-2)
                        # - type: spacer, punkt widokowy, plac, deptak, krótka ekspozycja, mini atrakcja
                        # - priority: low/filler
                        
                        poi_found = False
                        best_poi = None
                        best_score = -9999
                        best_duration = 0
                        best_travel = 0
                        
                        # Determine if we should prioritize soft POI (gaps >20 min)
                        prefer_soft_poi = gap > 20
                        
                        if prefer_soft_poi:
                            print(f"[GAP FILLING] Gap {gap} min >20 → PRIORITIZING SOFT POI (low intensity, 10-30min, must_see 0-2)")
                        
                        for poi in all_pois:
                            poi_id = poi.get('id', '')
                            
                            # Skip if already used
                            if poi_id in used_poi_ids:
                                continue
                            
                            # HOTFIX #9 (03.02.2026): Gap filling MUST respect target_group and intensity filters
                            # Import filter functions from scoring modules
                            from app.domain.scoring.family_fit import should_exclude_by_target_group
                            from app.domain.scoring.intensity_scoring import should_exclude_by_intensity
                            
                            # STEP 1: Target group hard filter
                            try:
                                should_exclude_target = should_exclude_by_target_group(poi, user)
                                print(f"[GAP FILLING DEBUG] POI {poi.get('id', 'unknown')} target filter result: {should_exclude_target}")
                                if should_exclude_target:
                                    print(f"[GAP FILLING] EXCLUDED by target_group: POI_ID={poi_id}")
                                    continue  # EXCLUDE - target group mismatch
                            except Exception as e:
                                print(f"[GAP FILLING] WARNING: EXCEPTION in target filter for POI_ID={poi.get('id', 'unknown')}: {e}")
                                import traceback
                                traceback.print_exc()
                                continue  # Exclude on error (safer)
                            
                            # STEP 2: Intensity hard filter
                            if should_exclude_by_intensity(poi, user):
                                continue  # EXCLUDE - intensity conflict
                            
                            # BUGFIX (01.02.2026): Skip POI with invalid data (NaN values)
                            poi_name = poi.get('name', '')
                            if not poi_name or str(poi_name).lower() == 'nan':
                                continue  # Invalid POI data
                            
                            # FIX #3.2: POI dict has capitalized keys from Excel ("Lat", "Lng")
                            poi_lat = poi.get('Lat', 0)
                            poi_lng = poi.get('Lng', 0)
                            if poi_lat == 0 or poi_lng == 0:
                                continue  # Missing location data
                            
                            # Calculate travel time
                            travel = 0
                            if last_poi_location:
                                travel = travel_time_minutes(last_poi_location, poi, context)
                            else:
                                # First POI - no travel
                                travel = 0
                            
                            # Check if POI fits in gap (travel + duration)
                            poi_duration = poi.get('time_min', 30)
                            if travel + poi_duration > gap:
                                continue  # Too long
                            
                            # Check if POI is open at this time
                            poi_start = current_end + travel
                            poi_start_str = minutes_to_time(int(poi_start))
                            
                            # Ensure context has 'date' field before calling is_open
                            if not context.get('date'):
                                # Skip is_open check if no date in context
                                pass
                            elif not is_open(poi, int(poi_start), poi_duration, context.get('season', 'all'), context):
                                continue  # Closed
                            
                            # CLIENT FEEDBACK (30.01.2026): SOFT POI filtering for gaps >20 min
                            # Check if POI matches soft POI criteria
                            is_soft_poi = False
                            if prefer_soft_poi:
                                # Criteria 1: intensity=low (or medium if duration <20min)
                                poi_intensity = str(poi.get('intensity', '')).lower()
                                intensity_ok = (poi_intensity == 'low') or (poi_intensity == 'medium' and poi_duration < 20)
                                
                                # Criteria 2: time_min=10-30 min
                                duration_ok = 10 <= poi_duration <= 30
                                
                                # Criteria 3: must_see_score low (0-2)
                                must_see = poi.get('must_see_score', 0) or 0
                                must_see_ok = must_see <= 2
                                
                                # Criteria 4: type=spacer, punkt widokowy, plac, deptak, krótka ekspozycja
                                poi_type = str(poi.get('type', '')).lower()
                                poi_tags = [str(t).lower() for t in poi.get('tags', []) if t]
                                soft_types = ['viewpoint', 'square', 'promenade', 'walk', 'scenic', 'panorama', 'mini', 'krótka']
                                type_ok = any(tag in soft_types for tag in poi_tags) or any(st in poi_type for st in ['viewpoint', 'square', 'walk'])
                                
                                # POI is soft if meets 3/4 criteria (flexible)
                                criteria_met = sum([intensity_ok, duration_ok, must_see_ok, type_ok])
                                is_soft_poi = criteria_met >= 3
                                
                                if is_soft_poi:
                                    print(f"[SOFT POI] ✓ POI {poi.get('id')}: intensity={poi_intensity}, duration={poi_duration}min, must_see={must_see}, criteria={criteria_met}/4")
                                else:
                                    # For gaps >20 min, STRONGLY prefer soft POI - skip non-soft unless no alternatives
                                    # This ensures gaps >20 min are filled with appropriate low-key activities
                                    print(f"[SOFT POI] ✗ POI {poi.get('id')}: NOT soft (criteria={criteria_met}/4) - consider as fallback")
                            
                            # Simple scoring: prefer nearby, short duration
                            # Shorter = better (fits in gaps)
                            # Closer = better (less travel)
                            score = 100 - travel * 0.5 - poi_duration * 0.2
                            
                            # CLIENT FEEDBACK (30.01.2026): BOOST soft POI score for gaps >20 min
                            if prefer_soft_poi and is_soft_poi:
                                score += 50  # Strong boost for soft POI in large gaps
                                print(f"[SOFT POI] Score boost: {score-50:.1f} → {score:.1f} (soft POI)")
                            elif prefer_soft_poi and not is_soft_poi:
                                score -= 30  # Penalty for non-soft POI in large gaps (but still possible as fallback)
                                print(f"[SOFT POI] Score penalty: {score+30:.1f} → {score:.1f} (non-soft fallback)")
                            
                            if score > best_score:
                                best_poi = poi
                                best_score = score
                                best_duration = poi_duration
                                best_travel = travel
                                poi_found = True
                        
                        if poi_found and best_poi:
                            # Add POI to fill gap!
                            print(f"[GAP FILLING] FILLING {gap} min gap with POI_ID: {best_poi.get('id', 'unknown')}")
                            
                            # HOTFIX #10.5: Debug logging - track POI ID being added in gap filling
                            gap_filling_poi_id = best_poi.get('id', 'UNKNOWN')
                            print(f"[GAP FILLING] Adding POI: id={gap_filling_poi_id}")
                            
                            # Add transit if needed
                            if best_travel > 0:
                                transit_start = minutes_to_time(current_end)
                                transit_end = minutes_to_time(current_end + best_travel)
                                
                                # Map transport string to TransitMode enum
                                transport = context.get('transport', 'car')
                                mode_map = {
                                    'walk': TransitMode.WALK,
                                    'car': TransitMode.CAR,
                                    'bus': TransitMode.PUBLIC_TRANSPORT,
                                    'public_transport': TransitMode.PUBLIC_TRANSPORT,
                                }
                                mode = mode_map.get(transport, TransitMode.CAR)
                                
                                transit_item = TransitItem(
                                    type=ItemType.TRANSIT,
                                    start_time=transit_start,
                                    end_time=transit_end,
                                    duration_min=best_travel,
                                    mode=mode,
                                    from_location="Previous location",
                                    to_location=best_poi.get('name', 'Attraction')
                                )
                                result.append(transit_item)
                            
                            # Add attraction
                            attr_start = minutes_to_time(current_end + best_travel)
                            
                            attraction_item = self._generate_attraction_item(
                                best_poi,
                                attr_start,
                                user,
                                user.get('target_group', 'family_kids'),
                                context,  # ETAP 2 Day 5: Pass context for explainability
                                None  # FIX #120: no day_used_reasons tracking in gap-fill context
                            )
                            result.append(attraction_item)
                            
                            # Mark as used
                            used_poi_ids.add(best_poi.get('id', ''))
                            
                            # HOTFIX (02.02.2026): Increment attraction counter
                            attraction_count += 1
                            print(f"[GAP FILLING] Attraction count after fill: {attraction_count}/{hard_limit}")
                            
                            continue  # Skip free_time - POI added instead
                        
                        # NO POI FOUND - add free_time as LAST RESORT
                        # FIX #4.4 (20.02.2026): Removed 40 min limit (second occurrence)
                        # Client requirement (test-02): Fill entire gaps, not just partial
                        # FIX #3 (22.02.2026): Respect day_end - don't exceed it with free_time
                        # FIX #9 (22.02.2026 - UAT Round 3, TEST-03 Issue): Cap free_time at 60 min
                        # Problem (TEST-03): 157-minute gap creates single massive "Czas wolny" block
                        # Solution: Cap at 60 min - large gaps will become multiple smaller free_time blocks
                        # Client feedback: 2.6-hour single gap looks like poor planning
                        # CLIENT FEEDBACK (30.01.2026): For gaps >20 min, cap free_time at 30-40 min (soft activities)
                        # CRITICAL FIX (01.05.2026): Apply cap FIRST, then check day_end (bug: day_end check bypassed cap)
                        
                        # STEP 1: Apply cap based on gap size (ALWAYS apply this first)
                        if prefer_soft_poi:  # gap > 20
                            gap_duration = min(gap, 40)  # Cap at 40 min for soft activities
                        else:
                            gap_duration = min(gap, 60)  # Cap at 60 min for smaller gaps
                        
                        # STEP 2: Check if cap reduced the gap
                        if gap_duration < gap:
                            print(f"[GAP FILLING] CAPPED free_time: {gap} min -> {gap_duration} min (max {40 if prefer_soft_poi else 60})")
                        
                        # STEP 3: Respect day_end - don't exceed it (cap again if needed)
                        day_end_str = context.get("day_end")
                        if day_end_str:
                            day_end_min = time_to_minutes(day_end_str)
                            free_time_end_proposed = current_end + gap_duration
                            
                            # If proposed end exceeds day_end, cap it AGAIN
                            if free_time_end_proposed > day_end_min:
                                original_gap_duration = gap_duration
                                gap_duration = day_end_min - current_end
                                if gap_duration < 5:  # Skip if too short
                                    print(f"[GAP FILLING] SKIP free_time - would exceed day_end ({free_time_end_proposed} > {day_end_min})")
                                    continue
                                print(f"[GAP FILLING] CAPPED to day_end: {original_gap_duration} min -> {gap_duration} min")
                        
                        free_time_start = minutes_to_time(current_end)
                        free_time_end = minutes_to_time(current_end + gap_duration)
                        
                        print(f"[GAP FILLING] WARNING: LAST RESORT: No available POI, adding free_time ({free_time_start}-{free_time_end})")
                        
                        # CLIENT FEEDBACK (30.01.2026): Descriptive suggestions for free_time
                        # "spacer po centrum, kawa/herbata, czas wolny na zdjęcia, odpoczynek na ławce, lody/deser"
                        # FIX #78 (27.05.2026): Rotate suggestion sets so consecutive free_time blocks
                        # don't always show the same 3 options. Rotation based on block start time.
                        _FT78_SETS = [
                            ["Spacer po centrum", "Kawa/herbata w kawiarni", "Czas na zdjęcia i relaks"],
                            ["Odpoczynek na ławce", "Zwiedzanie na własną rękę", "Zakupy pamiątek"],
                            ["Lody lub deser w kawiarni", "Zdjęcia panoramiczne", "Krótki spacer na świeżym powietrzu"],
                            ["Wizyta w lokalnym sklepiku", "Relaks przy kawie lub herbacie", "Spacer po okolicy"],
                            ["Fotografia podróżnicza", "Widokówki i pamiątki dla bliskich", "Chwila wytchnienia"],
                        ]
                        _ft78_idx = (current_end // 30) % len(_FT78_SETS)
                        free_time_suggestions = _FT78_SETS[_ft78_idx]
                        
                        # FIX #18.1 (03.05.2026 - CLIENT FEEDBACK Problem #3):
                        # Special label for gap right after day_start to avoid "day starts with rest" UX issue
                        # Client quote: "plan zaczyna się od odpoczynku" looks weird
                        is_day_start_gap = (item_type == 'day_start')
                        
                        # FIX #106 (28.05.2026): Skip short free_time at day start (<60min)
                        # A <60min gap right after day_start = "plan starts with rest" — confusing UX.
                        # Engine picks first POI shortly after start; this tiny free_time is noise.
                        if is_day_start_gap and gap_duration < 60:
                            print(f"[FIX #106] Skip day-start free_time ({gap_duration}min < 60min) — too short, skipping")
                            continue
                        
                        # FIX #78 (27.05.2026): Context-aware labels based on time of day and duration
                        if is_day_start_gap:
                            # Gap right after day_start → suggest preparation/travel
                            label = "Przygotowanie / dojazd do pierwszej atrakcji"
                            free_time_suggestions = [
                                "Śniadanie w hotelu",
                                "Przygotowanie do wyjścia",
                                "Dojazd na parking",
                                "Organizacja plecaka i sprzętu"
                            ]
                        elif current_end < time_to_minutes("11:00"):
                            label = "Poranny spacer i kawa" if gap_duration >= 20 else "Chwila przed następną atrakcją"
                        elif current_end < time_to_minutes("14:00"):
                            label = "Przerwa południowa" if gap_duration >= 30 else "Krótka przerwa"
                        elif current_end < time_to_minutes("17:00"):
                            label = "Popołudniowy relaks" if gap_duration >= 30 else "Chwila odpoczynku"
                        elif current_end < time_to_minutes("20:00"):
                            # FIX EXTRA4 (01.06.2026): Client approved 24.05.2026 — evening = Kolacja i Krupówki
                            label = "Kolacja i Krupówki: restauracja, spacer po Krupówkach" if gap_duration >= 30 else "Czas przed kolacją"
                        else:
                            label = "Wieczór: relaks i podsumowanie dnia" if gap_duration >= 30 else "Chwila na dobranoc"
                        
                        free_time_item = FreeTimeItem(
                            type=ItemType.FREE_TIME,
                            start_time=free_time_start,
                            end_time=free_time_end,
                            duration_min=gap_duration,
                            label=label,
                            suggestions=free_time_suggestions[:3],  # Top 3 suggestions
                            is_technical_buffer=(gap_duration < 5)  # FIX #39: Only filter truly tiny (<5min) artifacts
                        )
                        
                        # FIX #Problem9 (14.05.2026): Check for overlap before adding free_time (location 2)
                        result_dicts_2 = [item.dict() if hasattr(item, 'dict') else item for item in result]
                        overlaps_detected_2 = False
                        for existing_item_2 in result_dicts_2:
                            if 'start_time' in existing_item_2 and 'end_time' in existing_item_2:
                                exist_start_2 = time_to_minutes(existing_item_2['start_time'])
                                exist_end_2 = time_to_minutes(existing_item_2['end_time'])
                                free_start_min_2 = current_end
                                free_end_min_2 = current_end + gap_duration
                                
                                # Check if time ranges overlap
                                if not (free_end_min_2 <= exist_start_2 or free_start_min_2 >= exist_end_2):
                                    overlaps_detected_2 = True
                                    print(f"[GAP FILLING] OVERLAP DETECTED (location 2): free_time {free_time_start}-{free_time_end} would conflict with {existing_item_2.get('type')} {existing_item_2.get('start_time')}-{existing_item_2.get('end_time')} - SKIPPING")
                                    break
                        
                        if not overlaps_detected_2:
                            result.append(free_time_item)
                        else:
                            # Skip this free_time and the remaining gap filling loop below
                            continue
                        
                        # FIX #17 (29.04.2026 - CLIENT FEEDBACK): Fill remaining gap after capped free_time
                        # Problem: If gap = 142 min, code adds 60-min free_time, but leaves 82-min gap unfilled
                        #          because loop continues to next item in original list
                        # Solution: After adding capped free_time, check if remaining gap exists and fill it
                        #           with additional free_time blocks (recursive filling)
                        remaining_gap = gap - gap_duration
                        current_fill_end = current_end + gap_duration
                        
                        while remaining_gap > 15:  # Continue filling if gap > 15 min remains
                            # Calculate next free_time block duration (max 60 min)
                            next_duration = min(remaining_gap, 60)
                            
                            # Cap at day_end if applicable
                            if day_end_str:
                                day_end_min = time_to_minutes(day_end_str)
                                if current_fill_end + next_duration > day_end_min:
                                    next_duration = day_end_min - current_fill_end
                                    if next_duration < 5:  # Too short, skip
                                        break
                            
                            next_free_time_start = minutes_to_time(current_fill_end)
                            next_free_time_end = minutes_to_time(current_fill_end + next_duration)
                            
                            print(f"[GAP FILLING] FIX #17: Filling remaining {remaining_gap} min gap with additional free_time ({next_free_time_start}-{next_free_time_end})")
                            
                            # FIX #78 (27.05.2026): Rotate labels for recursive fill blocks (avoid repetition)
                            _FT78_NEXT_LABELS = [
                                "Swobodne zwiedzanie okolicy",
                                "Przerwa kawowa i odpoczynek",
                                "Czas na własne odkrycia",
                                "Relaks i chwila wytchnienia",
                                "Spacer i fotografia podróżnicza",
                            ]
                            _ft78_next_idx = (current_fill_end // 30) % len(_FT78_NEXT_LABELS)
                            next_label = _FT78_NEXT_LABELS[_ft78_next_idx]
                            
                            next_free_time = FreeTimeItem(
                                type=ItemType.FREE_TIME,
                                start_time=next_free_time_start,
                                end_time=next_free_time_end,
                                duration_min=next_duration,
                                label=next_label,
                                suggestions=free_time_suggestions[:3] if 'free_time_suggestions' in locals() else None,  # Use same suggestions
                                is_technical_buffer=(next_duration < 5)  # FIX #39
                            )
                            
                            result.append(next_free_time)
                            
                            # Update for next iteration
                            remaining_gap -= next_duration
                            current_fill_end += next_duration
        
        # FIX #4 (15.02.2026): Add end-of-day free_time if gap >30 min before day_end
        # FIX #4.5 (20.02.2026): Changed threshold from 30 to 15 min to be consistent with main gap filling
        # Client issue (test-02 Day 1): Gap 21 min before day_end was not filled (21 < 30)
        # FIX #6.2 (22.02.2026): Add dinner_break instead of free_time if appropriate
        if result and len(result) >= 2:
            # Check second-to-last item (last is usually DAY_END)
            last_item = result[-2] if result[-1].dict()['type'] == 'day_end' else result[-1]
            last_end_str = None
            
            # Get last item's end_time
            if hasattr(last_item, 'end_time') and last_item.end_time:
                last_end_str = last_item.end_time
            
            # Get day_end from context
            day_end_str = context.get("day_end")
            
            if last_end_str and day_end_str:
                last_end_min = time_to_minutes(last_end_str)
                day_end_min = time_to_minutes(day_end_str)
                gap_to_end = day_end_min - last_end_min
                
                if gap_to_end > 15:  # Changed from 30 to 15
                    # FIX #6.2 (22.02.2026): Check if dinner_break should be added instead of free_time
                    # Conditions for dinner:
                    # 1. Gap >= 60 min (enough time for dinner)
                    # 2. Last item ends >= 17:30 (reasonable dinner time)
                    # 3. No dinner_break exists yet in this day
                    has_dinner = any(item.dict().get('type') == 'dinner_break' for item in result)
                    should_add_dinner = (
                        gap_to_end >= 60 and 
                        last_end_min >= time_to_minutes("17:30") and 
                        not has_dinner
                    )
                    
                    if should_add_dinner:
                        # Add dinner_break instead of free_time
                        # FIX #80 (27.05.2026): Min dinner is guaranteed by should_add_dinner condition (gap_to_end >= 60)
                        dinner_duration = min(60, gap_to_end)  # Max 60 min for dinner
                        dinner_start = last_end_str
                        dinner_end = minutes_to_time(last_end_min + dinner_duration)
                        
                        # Generate suggestions (simple default - user preferences not available here)
                        suggestions = [
                            "Regionalna restauracja z kuchnią góralską",
                            "Bacówka z degustacją oscypka",
                            "Karcma z tradycyjnymi potrawami"
                        ]
                        
                        dinner_item = DinnerBreakItem(
                            type=ItemType.DINNER_BREAK,
                            start_time=dinner_start,
                            end_time=dinner_end,
                            duration_min=dinner_duration,
                            suggestions=suggestions
                        )
                        
                        # Insert before DAY_END
                        if result[-1].dict()['type'] == 'day_end':
                            result.insert(-1, dinner_item)
                        else:
                            result.append(dinner_item)
                        
                        print(f"[GAP FILLING] ✓ Added end-of-day dinner_break: {dinner_start}-{dinner_end} ({dinner_duration} min)")
                        
                        # FIX #30 (18.05.2026): Fill ALL remaining time after dinner to day_end
                        # Each free_time block is capped at 60 min per client requirement (Problem #7),
                        # but we now add MULTIPLE blocks to fully cover the gap to day_end.
                        remaining_gap = gap_to_end - dinner_duration
                        current_ft_start = time_to_minutes(dinner_end)
                        ft_block_num = 0
                        while remaining_gap > 15:
                            ft_block_num += 1
                            ft_block_duration = min(remaining_gap, 60)  # Keep ≤60 min per block
                            ft_block_end_min = current_ft_start + ft_block_duration
                            ft_block_start_str = minutes_to_time(current_ft_start)
                            ft_block_end_str = minutes_to_time(ft_block_end_min)
                            
                            ft_label = "Wieczór: spacer, zakupy, relaks w hotelu" if ft_block_num == 1 else "Czas wolny wieczorny"
                            # FIX #78 (27.05.2026): Add suggestions for post-dinner free_time blocks
                            _FT78_SETS_PD = [
                                ["Spacer po centrum", "Kawa/herbata w kawiarni", "Czas na zdjęcia i relaks"],
                                ["Odpoczynek na ławce", "Zwiedzanie na własną rękę", "Zakupy pamiątek"],
                                ["Lody lub deser w kawiarni", "Zdjęcia panoramiczne", "Krótki spacer na świeżym powietrzu"],
                                ["Wizyta w lokalnym sklepiku", "Relaks przy kawie lub herbacie", "Spacer po okolicy"],
                                ["Fotografia podróżnicza", "Widokówki i pamiątki dla bliskich", "Chwila wytchnienia"],
                            ]
                            _ft78pd_sugg = _FT78_SETS_PD[(current_ft_start // 30) % len(_FT78_SETS_PD)]
                            free_time_item = FreeTimeItem(
                                type=ItemType.FREE_TIME,
                                start_time=ft_block_start_str,
                                end_time=ft_block_end_str,
                                duration_min=ft_block_duration,
                                label=ft_label,
                                suggestions=_ft78pd_sugg[:3],
                                is_technical_buffer=(ft_block_duration < 5)  # FIX #39
                            )
                            
                            if result[-1].dict()['type'] == 'day_end':
                                result.insert(-1, free_time_item)
                            else:
                                result.append(free_time_item)
                            
                            print(f"[GAP FILLING] Added post-dinner free_time block #{ft_block_num}: {ft_block_start_str}-{ft_block_end_str} ({ft_block_duration} min)")
                            current_ft_start = ft_block_end_min
                            remaining_gap -= ft_block_duration
                    else:
                        # Add free_time as usual
                        print(f"[GAP FILLING] Adding end-of-day free_time: {gap_to_end} min gap before day_end ({last_end_str} -> {day_end_str})")
                        
                        # FIX #82+#84 (27.05.2026): Prevent consecutive free_time spam at end of day.
                        # FIX #30 created a while-loop of 60+60+40 min blocks (client: "za dużo bloków").
                        # Now: single block (max 90 min) with context-aware evening anchor label.
                        # FIX #82 = no multiple blocks; FIX #84 = meaningful evening suggestion.
                        eod_block_start_str = minutes_to_time(last_end_min)
                        eod_block_duration = min(gap_to_end, 90)  # FIX #82: single block, cap 90 min
                        eod_block_end_min = last_end_min + eod_block_duration
                        eod_block_end_str = minutes_to_time(eod_block_end_min)

                        # FIX #84 (27.05.2026): Context-aware evening anchor label based on gap size.
                        if gap_to_end >= 90:
                            eod_label = "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
                            _ft84_sugg = [
                                "Termy/SPA w okolicy",
                                "Spacer po Krupówkach",
                                "Kolacja w restauracji góralskiej"
                            ]
                        elif gap_to_end >= 60:
                            eod_label = "Wieczór: spacer i kolacja w centrum"
                            _ft84_sugg = [
                                "Spacer po centrum Zakopanego",
                                "Kolacja w restauracji",
                                "Odpoczynek w hotelu"
                            ]
                        else:
                            eod_label = "Czas wolny na koniec dnia"
                            # FIX #78 rotating suggestions still apply for short gaps
                            _FT78_SETS_EOD = [
                                ["Spacer po centrum", "Kawa/herbata w kawiarni", "Czas na zdjęcia i relaks"],
                                ["Odpoczynek na ławce", "Zwiedzanie na własną rękę", "Zakupy pamiątek"],
                                ["Lody lub deser w kawiarni", "Zdjęcia panoramiczne", "Krótki spacer na świeżym powietrzu"],
                                ["Wizyta w lokalnym sklepiku", "Relaks przy kawie lub herbacie", "Spacer po okolicy"],
                                ["Fotografia podróżnicza", "Widokówki i pamiątki dla bliskich", "Chwila wytchnienia"],
                            ]
                            _ft84_sugg = _FT78_SETS_EOD[(last_end_min // 30) % len(_FT78_SETS_EOD)]

                        end_of_day_item = FreeTimeItem(
                            type=ItemType.FREE_TIME,
                            start_time=eod_block_start_str,
                            end_time=eod_block_end_str,
                            duration_min=eod_block_duration,
                            label=eod_label,
                            suggestions=_ft84_sugg[:3],
                            is_technical_buffer=(eod_block_duration < 5)  # FIX #39
                        )

                        if result[-1].dict()['type'] == 'day_end':
                            result.insert(-1, end_of_day_item)
                        else:
                            result.append(end_of_day_item)

                        print(f"[GAP FILLING] FIX#82/#84 Single EOD block: {eod_block_start_str}-{eod_block_end_str} ({eod_block_duration} min): {eod_label[:50]}")
        
        print(f"[GAP FILLING] Final: {len(items)} -> {len(result)} items")
        return result

    def _remove_timeline_overlaps(self, items: List[Any], day_num: int) -> List[Any]:
        """
        FIX #Problem9 (14.05.2026): Remove overlapping items from timeline.
        
        Problem:
        - Gap filling can add both POI and free_time independently
        - This creates overlaps when POI selection changes (e.g. due to lunch timing fixes)
        - Example from test-03: attraction 18:17-18:52 overlaps with free_time 18:19-19:19
        
        Strategy:
        - Iterate through sorted items
        - If current item overlaps with previous: remove the less important one
        - Priority: attraction/meal > free_time (prefer non-free_time)
        
        Args:
            items: Sorted list of timeline items
            day_num: Day number for logging
            
        Returns:
            List of items without overlaps
        """
        if not items:
            return items
        
        result = []
        prev_item = None
        overlaps_removed = 0
        
        for item in items:
            # Get time ranges
            item_dict = item.dict() if hasattr(item, 'dict') else item
            item_type = item_dict.get('type')
            item_start_str = item_dict.get('start_time') or item_dict.get('time')
            item_end_str = item_dict.get('end_time')
            
            # Skip items without time info (like day_start, day_end handled separately)
            if not item_start_str:
                result.append(item)
                continue
            
            item_start = time_to_minutes(item_start_str)
            item_end = time_to_minutes(item_end_str) if item_end_str else item_start
            
            # Check overlap with previous item
            if prev_item is not None:
                prev_dict = prev_item.dict() if hasattr(prev_item, 'dict') else prev_item
                prev_type = prev_dict.get('type')
                prev_end_str = prev_dict.get('end_time')
                
                if prev_end_str:
                    prev_end = time_to_minutes(prev_end_str)
                    
                    # Check if overlap: current starts before previous ends
                    if item_start < prev_end:
                        # OVERLAP DETECTED
                        overlap_min = prev_end - item_start
                        
                        # Determine which item to keep
                        # Priority: non-free_time > free_time
                        prev_is_free = prev_type == 'free_time' or prev_type == ItemType.FREE_TIME
                        curr_is_free = item_type == 'free_time' or item_type == ItemType.FREE_TIME
                        
                        if curr_is_free and not prev_is_free:
                            # Current is free_time, previous is attraction/meal - SKIP current
                            print(f"[OVERLAP HEAL] Day {day_num}: Removed free_time {item_start_str}-{item_end_str} (overlaps {overlap_min}min with {prev_type})")
                            overlaps_removed += 1
                            continue
                        elif prev_is_free and not curr_is_free:
                            # Previous is free_time, current is attraction/meal - REMOVE previous, keep current
                            print(f"[OVERLAP HEAL] Day {day_num}: Removed previous free_time (overlaps {overlap_min}min with {item_type} {item_start_str}-{item_end_str})")
                            result.pop()  # Remove previous free_time
                            overlaps_removed += 1
                            # Don't update prev_item yet - will be set below
                        else:
                            # Both same priority (both free_time or both non-free_time) - keep first
                            print(f"[OVERLAP HEAL] Day {day_num}: Removed {item_type} {item_start_str}-{item_end_str} (overlaps {overlap_min}min with previous {prev_type})")
                            overlaps_removed += 1
                            continue
            
            # Add current item and update prev_item
            result.append(item)
            prev_item = item
        
        if overlaps_removed > 0:
            print(f"[OVERLAP HEAL] Day {day_num}: Removed {overlaps_removed} overlapping items")
        else:
            print(f"[OVERLAP HEAL] Day {day_num}: No overlaps detected")
        
        return result

    def _sort_items_by_time(self, items: List[Any]) -> List[Any]:
        """
        FIX #21 (03.05.2026 - CLIENT FEEDBACK Round 2 - Problem #1): Sort items by start_time.
        
        Problem:
        - Items are added by engine, validation, and gap_filling in different orders
        - This creates chronological chaos where items appear out of order in response
        - Example from JSON 1 Day 1:
          * 17:04–17:20 free_time "Krótki odpoczynek"
          * 17:08–18:08 free_time "Czas wolny do końca dnia"  ← Added by validation
          * 17:20–17:55 attraction "Muzeum"                    ← Added by engine earlier
          * 18:08–19:00 free_time                              ← Added by gap filling
        - Items are NOT in chronological order!
        
        Solution:
        - Sort all items by start_time before consolidation
        - Keep day_start first and day_end last (special handling)
        - This ensures timeline is chronologically correct
        
        Args:
            items: List of plan items (may be in wrong order)
            
        Returns:
            Items sorted by start_time (chronological order)
        """
        if not items:
            return items
        
        print(f"[SORT ITEMS] Sorting {len(items)} items by start_time")
        
        from app.domain.planner.time_utils import time_to_minutes
        
        # Separate day_start and day_end (keep them at boundaries)
        day_start_item = None
        day_end_item = None
        sortable_items = []
        
        for item in items:
            item_dict = item.dict()
            item_type = item_dict.get('type')
            
            if item_type == 'day_start':
                day_start_item = item
            elif item_type == 'day_end':
                day_end_item = item
            else:
                sortable_items.append(item)
        
        # Sort by start_time (or time field for items without start_time)
        def get_sort_key(item):
            item_dict = item.dict()
            start_time = item_dict.get('start_time')
            if start_time:
                return time_to_minutes(start_time)
            # Fallback for items without start_time (e.g., some special items)
            time_field = item_dict.get('time')
            if time_field:
                return time_to_minutes(time_field)
            # Items without any time field go to end (shouldn't happen)
            return 9999
        
        # DEBUG: Log items BEFORE sort
        print(f"[SORT ITEMS] BEFORE SORT: {len(sortable_items)} items")
        for idx, item in enumerate(sortable_items[10:18] if len(sortable_items) > 10 else sortable_items[:8]):  # Items 10-17
            item_dict = item.dict()
            item_type = item_dict.get('type')
            start_time = item_dict.get('start_time', 'N/A')
            sort_key = get_sort_key(item)
            print(f"  [{idx+10 if len(sortable_items) > 10 else idx}] sort_key={sort_key:4} {item_type:12} {start_time}")
        
        sortable_items.sort(key=get_sort_key)
        
        # DEBUG: Log sorted items to verify order
        print(f"[SORT ITEMS] AFTER SORT (Day ?): {len(sortable_items)} items")
        for idx, item in enumerate(sortable_items[:10]):  # First 10 items
            item_dict = item.dict()
            item_type = item_dict.get('type')
            start_time = item_dict.get('start_time', 'N/A')
            end_time = item_dict.get('end_time', 'N/A')
            name = item_dict.get('name') or item_dict.get('label', '')[:30]
            print(f"  [{idx}] {item_type:12} {start_time}-{end_time}  {name}")
        
        # Reconstruct list: day_start first, sorted items, day_end last
        result = []
        if day_start_item:
            result.append(day_start_item)
        result.extend(sortable_items)
        if day_end_item:
            result.append(day_end_item)
        
        return result

    def _consolidate_consecutive_free_time_blocks(self, items: List[Any]) -> List[Any]:
        """
        FIX #18 (03.05.2026 - CLIENT FEEDBACK MAY 3): Consolidate consecutive free_time blocks.
        
        Problem:
        - FIX #17 (29.04.2026) creates multiple 60-min free_time blocks to fill large gaps
        - Result: 3-4 consecutive "Czas wolny" blocks looks repetitive and poorly planned
        - Examples from client feedback:
          * JSON 1 Day 3: Several 60-min free_time blocks in a row
          * JSON 2 Day 1: 3 consecutive rest blocks after termy
          * JSON 2 Day 3: 4 consecutive "Czas wolny do końca dnia" blocks
        
        Solution:
        - Post-processing step after gap filling
        - Merge consecutive free_time blocks with similar labels into single longer blocks
        - Keep blocks separate if they have distinct contexts (e.g., "Przygotowanie" vs "Odpoczynek")
        - Generate smart labels based on consolidated duration
        
        Benefits:
        - Better UX - one "2-hour relax" instead of four "30-min free time" blocks
        - Cleaner timeline appearance
        - No changes to core algorithm needed (post-processing only)
        
        Args:
            items: List of plan items (may contain consecutive free_time blocks)
            
        Returns:
            Consolidated list with merged free_time blocks
        """
        if not items:
            return items
        
        # DEBUG PROBLEM #4: Log inputs to consolidation
        print(f"\n[CONSOLIDATE DEBUG] Received {len(items)} items", flush=True)
        free_time_count = sum(1 for item in items if hasattr(item, 'type') and item.type == ItemType.FREE_TIME)
        print(f"[CONSOLIDATE DEBUG] Free time count: {free_time_count}", flush=True)
        
        consolidated = []
        i = 0
        
        while i < len(items):
            item = items[i]
            
            # Non-free_time items pass through unchanged
            if not hasattr(item, 'type') or item.type != ItemType.FREE_TIME:
                consolidated.append(item)
                i += 1
                continue
            
            # Found free_time - check if next items are also free_time
            free_time_group = [item]
            j = i + 1
            
            # FIX #76 (26.05.2026): Cap merged free_time at 90 min.
            # Bug: 5 consecutive 60-min blocks for seniors mountain got merged into 291 min.
            # Engine/gap_filler never creates blocks >60 min; consolidation must respect same limit.
            # FIX #86 (28.05.2026): Raised cap to 180 min — engine now creates large afternoon/evening
            # blocks directly (FIX #86), so consolidation should merge them up to 3h.
            MAX_MERGED_FREE_TIME = 180
            
            while j < len(items):
                next_item = items[j]
                if hasattr(next_item, 'type') and next_item.type == ItemType.FREE_TIME:
                    # FIX #76: Stop merging if accumulated total would exceed 90 min
                    current_total = sum(getattr(b, 'duration_min', 0) for b in free_time_group)
                    next_dur = getattr(next_item, 'duration_min', 0)
                    if current_total + next_dur > MAX_MERGED_FREE_TIME:
                        print(f"[CONSOLIDATE] FIX#76: Stop merge at {current_total}+{next_dur}min > {MAX_MERGED_FREE_TIME}min cap")
                        break
                    # Check if should merge with previous block
                    should_merge = self._should_merge_free_time(free_time_group[-1], next_item)
                    print(f"[CONSOLIDATE DEBUG] Checking merge: block {i} ({getattr(free_time_group[-1], 'duration_min', '?')}min, tech_buffer={getattr(free_time_group[-1], 'is_technical_buffer', None)}) + block {j} ({getattr(next_item, 'duration_min', '?')}min, tech_buffer={getattr(next_item, 'is_technical_buffer', None)}) → {should_merge}", flush=True)
                    if should_merge:
                        free_time_group.append(next_item)
                        j += 1
                    else:
                        # Different context - don't merge
                        break
                else:
                    # Not free_time - stop looking
                    break
            
            # If we found multiple consecutive free_time blocks, merge them
            if len(free_time_group) > 1:
                merged = self._merge_free_time_blocks(free_time_group)
                consolidated.append(merged)
                print(f"[CONSOLIDATE] Merged {len(free_time_group)} free_time blocks into 1 ({merged.duration_min} min, {free_time_group[0].start_time}-{merged.end_time})")
            else:
                # Single free_time block - keep as is
                consolidated.append(item)
            
            # Move to next unprocessed item
            i = j if j > i + 1 else i + 1

        # FIX #82 (27.05.2026): Collapse trailing EOD consecutive free_time blocks into 1.
        # Engine often creates 3×60-min blocks when no more activities fit. FIX #76 cap (90 min)
        # prevents merging them pairwise, leaving 3 generic blocks. Post-process: if the last
        # N items (before day_end) are all free_time, merge them into a single meaningful block.
        _tail_ft = []
        _tail_start_idx = len(consolidated)
        for _k in range(len(consolidated) - 1, -1, -1):
            _citem = consolidated[_k]
            if hasattr(_citem, 'type') and _citem.type == ItemType.FREE_TIME:
                _tail_ft.insert(0, _citem)
                _tail_start_idx = _k
            elif hasattr(_citem, 'type') and _citem.type in (ItemType.DAY_END,):
                continue  # skip day_end sentinel
            else:
                break  # hit a real activity — stop scanning
        if len(_tail_ft) >= 2:
            _merged_eod = self._merge_free_time_blocks(_tail_ft)
            consolidated = consolidated[:_tail_start_idx] + [_merged_eod]
            print(f"[CONSOLIDATE] FIX#82: Collapsed {len(_tail_ft)} trailing EOD free_time blocks → 1 ({_merged_eod.duration_min} min, {_merged_eod.start_time}-{_merged_eod.end_time}, label={_merged_eod.label})")

        return consolidated

    def _should_merge_free_time(self, block1: FreeTimeItem, block2: FreeTimeItem) -> bool:
        """
        Helper for _consolidate_consecutive_free_time_blocks.
        
        Determines if two consecutive free_time blocks should be merged.
        
        Merge if:
        - Both have generic labels (Czas wolny, Odpoczynek, Relaks, etc.)
        - Both are NOT technical buffers (technical buffers are intentionally short)
        
        Don't merge if:
        - Either has a specific context label (e.g., "Przygotowanie", "Dojazd")
        - Either is marked as technical buffer
        
        Args:
            block1: First free_time block
            block2: Second (consecutive) free_time block
            
        Returns:
            True if blocks should be merged, False otherwise
        """
        # FIX #24.6 (10.05.2026 - CLIENT FEEDBACK Round 2 - Problem #4): Fix consecutive FREE_TIME regression
        # ROOT CAUSE: Line 2177 blocks merge if EITHER block is technical_buffer
        # PROBLEM: Technical buffer (short padding) followed by genuine free_time should merge
        # SOLUTION: Only block merge if SECOND block is technical_buffer UNLESS it's end-of-day free_time
        # ALLOW: technical_buffer → genuine free_time (consolidate padding with subsequent free time)
        # ALLOW: genuine free_time → end-of-day technical_buffer (consolidate with short end-of-day block)
        # BLOCK: anything → technical_buffer padding (keep intentional padding separate)
        
        # Exception: "Czas wolny na koniec dnia" is marked as technical_buffer if < 30min,
        # but it's genuine free_time that should merge with preceding free_time blocks
        if block2.is_technical_buffer:
            # Check if block2 is end-of-day free_time (not padding)
            end_of_day_labels = ["Czas wolny na koniec dnia", "Czas wolny", "Krótki odpoczynek"]
            is_end_of_day = any(block2.label.startswith(pattern) for pattern in end_of_day_labels)
            if not is_end_of_day:
                return False
            # If block2 is end-of-day, continue to label check (allow merge)
        # If block1 is technical_buffer but block2 is not, allow merge (transition case)
        # If both are not technical_buffer, continue to label check below (existing behavior)
        
        # Generic label patterns that can be safely merged (use startswith for partial match)
        # This allows matching "Czas wolny do końca dnia: kolacja, spacer..." with base pattern
        generic_label_patterns = [
            "Czas wolny",
            "Odpoczynek",
            "Relaks",
            "Dłuższy odpoczynek",
            "Krótki odpoczynek",
            "Wieczór:",  # Matches "Wieczór: spacer, zakupy, relaks w hotelu"
            "Wieczorny relaks",  # FIX #86: "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
            "Czas wolny / relaks",
            "Odpoczynek / spacer",
        ]
        
        # Check if both labels start with generic patterns
        label1_is_generic = any(block1.label.startswith(pattern) for pattern in generic_label_patterns)
        label2_is_generic = any(block2.label.startswith(pattern) for pattern in generic_label_patterns)
        
        # Also check exact matches for short labels
        exact_generic = [
            "Czas wolny na koniec dnia"
        ]
        if block1.label in exact_generic:
            label1_is_generic = True
        if block2.label in exact_generic:
            label2_is_generic = True
        
        # Merge if both labels are generic
        return label1_is_generic and label2_is_generic

    def _merge_free_time_blocks(self, blocks: List[FreeTimeItem]) -> FreeTimeItem:
        """
        Helper for _consolidate_consecutive_free_time_blocks.
        
        Merges multiple consecutive free_time blocks into a single block with:
        - Start time from first block
        - End time from last block
        - Total duration = sum of all block durations
        - Smart label based on total duration
        - Combined suggestions (deduplicated)
        - is_technical_buffer = False (consolidated blocks are real free time)
        
        Args:
            blocks: List of consecutive FreeTimeItem objects to merge
            
        Returns:
            Single FreeTimeItem representing the merged time period
        """
        if not blocks:
            raise ValueError("Cannot merge empty list of free_time blocks")
        
        if len(blocks) == 1:
            return blocks[0]
        
        # Get time boundaries
        start_time = blocks[0].start_time
        end_time = blocks[-1].end_time
        total_duration = sum(b.duration_min for b in blocks)
        
        # FIX #84 (27.05.2026): If merging blocks that END in the evening (end ≥ 18:00)
        # and total time ≥ 60 min, use evening anchor label instead of generic one.
        _merge_start_min = time_to_minutes(start_time) if start_time else 0
        _merge_end_min = time_to_minutes(blocks[-1].end_time) if (blocks and blocks[-1].end_time) else 0
        _is_evening_merge = _merge_end_min >= time_to_minutes("18:00") and total_duration >= 60

        # Generate smart label based on total duration
        if _is_evening_merge:
            if total_duration >= 90:
                label = "Wieczorny relaks: termy, spacer po Krupówkach lub kolacja"
            else:
                label = "Wieczór: spacer i kolacja w centrum"
        elif total_duration >= 180:  # 3+ hours
            label = "Dłuższy odpoczynek / czas na własne aktywności"
        elif total_duration >= 120:  # 2+ hours
            label = "Dłuższy odpoczynek / spacer / relaks"
        elif total_duration >= 90:  # 1.5+ hours
            label = "Odpoczynek / spacer po okolicy"
        elif total_duration >= 60:  # 1+ hour
            label = "Czas wolny / relaks"
        else:  # < 1 hour
            label = "Odpoczynek"
        
        # Combine suggestions from all blocks (deduplicate)
        all_suggestions = []
        seen = set()
        for block in blocks:
            if hasattr(block, 'suggestions') and block.suggestions:
                for suggestion in block.suggestions:
                    if suggestion not in seen:
                        all_suggestions.append(suggestion)
                        seen.add(suggestion)
        
        # Use combined suggestions or default set
        # FIX #84 (27.05.2026): For evening merges, inject evening activity suggestions.
        if _is_evening_merge:
            _evening_suggestions = [
                "Termy/SPA w okolicy",
                "Spacer po Krupówkach",
                "Kolacja w restauracji góralskiej",
                "Relaks w hotelu",
                "Wieczorna kawa z widokiem na Tatry"
            ]
            # Prepend evening suggestions, keeping any unique original ones
            all_suggestions = _evening_suggestions + [s for s in all_suggestions if s not in _evening_suggestions]
        elif not all_suggestions:
            all_suggestions = [
                "Spacer po centrum",
                "Kawa/herbata w kawiarni",
                "Czas na zdjęcia i relaks",
                "Odpoczynek na ławce",
                "Lody lub deser"
            ]
        
        return FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time=start_time,
            end_time=end_time,
            duration_min=total_duration,
            label=label,
            suggestions=all_suggestions[:5],  # Max 5 suggestions
            is_technical_buffer=False  # Consolidated blocks are NOT technical buffers
        )

    def _add_minutes(self, time_str: str, minutes: int) -> str:
        """Helper: dodaje minuty do czasu HH:MM."""
        from app.domain.planner.time_utils import (
            time_to_minutes,
            minutes_to_time
        )
        
        total_min = time_to_minutes(time_str) + minutes
        return minutes_to_time(total_min)

    def _update_transit_destinations(self, items: List[Any]) -> List[Any]:
        """
        FIX #3 (02.02.2026): Update transit 'to_location' after gap filling.
        
        Problem:
        - Gap filling inserts new POI between transit and its original destination
        - Transit "to" field still points to old destination
        - Example:
          1. Engine generates: [Transit to DINO, DINO Park]
          2. Gap filling inserts: [Transit to DINO, **Dom do góry nogami**, DINO Park]
          3. Transit "to" should be "Dom do góry nogami", not "DINO Park"!
        
        Solution:
        - Iterate through items
        - For each transit, find NEXT attraction (skip lunch/free_time/etc)
        - Update transit.to_location to match next attraction's name
        
        Also fixes:
        - FIX #4: Transit "from" after lunch should be last attraction before lunch
        
        Args:
            items: List of PlanResponse items (after gap filling)
            
        Returns:
            Updated list with correct transit destinations
        """
        # FIX #101b (29.05.2026): Build result while skipping orphaned transits.
        result = []
        for i, item in enumerate(items):
            # Skip non-transit items
            if item.type != ItemType.TRANSIT:
                result.append(item)
                continue
            
            # Find NEXT attraction after this transit (in original list)
            next_attraction = None
            for j in range(i + 1, len(items)):
                if items[j].type == ItemType.ATTRACTION:
                    next_attraction = items[j]
                    break
            
            # If no following attraction, transit is orphaned — remove it
            if not next_attraction:
                print(f"[TRANSIT FIX #101b] Removing orphaned transit: '{item.from_location}' -> '{item.to_location}' (no following attraction)")
                continue
            
            # Update "to" to match next attraction
            item.to_location = next_attraction.name
            print(f"[TRANSIT FIX] Updated transit destination: '{item.from_location}' -> '{item.to_location}'")
            
            # FIX #4: Update "from" to match PREVIOUS attraction
            # Find last attraction BEFORE this transit (in original list)
            prev_attraction = None
            for j in range(i - 1, -1, -1):
                if items[j].type == ItemType.ATTRACTION:
                    prev_attraction = items[j]
                    break
            
            if prev_attraction:
                item.from_location = prev_attraction.name
                print(f"[TRANSIT FIX] Updated transit origin: -> '{prev_attraction.name}'")
            
            result.append(item)
        
        return result
