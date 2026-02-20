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
from app.infrastructure.repositories import POIRepository

# ETAP 2 Day 5: Quality + Explainability
from app.domain.planner.quality_checker import validate_day_quality, check_poi_quality
from app.domain.planner.explainability import explain_poi_selection

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
        # Konwersja TripInput → engine params
        params = trip_input_to_engine_params(trip_input)
        
        context = params["context"]
        user = params["user"]
        dates = params["dates"]
        day_start = params["day_start"]
        day_end = params["day_end"]
        
        # Load POIs z repository
        all_pois = self.poi_repo.get_all()
        
        # HOTFIX #8 (03.02.2026): Engine expects normalized dicts z kluczami: 
        # "target_groups", "kids_only", "name", etc.
        # POI model ma inne field names (target_group singular, brak kids_only property)
        # Zamiast POI.model_dump() używamy RAW dict z normalizer
        from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
        
        all_pois_dict = load_zakopane_poi(self.poi_repo.excel_path)
        
        if not all_pois_dict:
            # FIXME: graceful handling gdy brak POI
            # Na razie zwróć pusty plan
            return PlanResponse(
                plan_id=str(uuid.uuid4()),
                version=1,
                days=[]
            )
        
        # ETAP 2 - DAY 3 (15.02.2026): Multi-day routing
        # Route to appropriate planner based on trip length
        num_days = trip_input.trip_length.days
        
        # Track POIs across all days (for multi-day)
        global_used_pois = set()
        
        if num_days > 1:
            # Multi-day plan: Use plan_multiple_days with cross-day tracking
            print(f"[PLAN SERVICE] Multi-day plan requested: {num_days} days")
            
            # Create contexts list (one per day)
            contexts = []
            for day_num in range(num_days):
                day_context = context.copy()
                day_context["date"] = dates[day_num]
                contexts.append(day_context)
            
            # Call multi-day planner
            engine_results = plan_multiple_days(
                pois=all_pois_dict,
                user=user,
                contexts=contexts,
                day_start=day_start,
                day_end=day_end
            )
            
        else:
            # Single-day plan: Use original build_day (Etap 1 behavior)
            print(f"[PLAN SERVICE] Single-day plan requested")
            context["date"] = dates[0]
            
            engine_result = build_day(
                all_pois_dict,
                user,
                context,
                day_start,
                day_end
            )
            
            # Wrap in list for uniform processing
            engine_results = [engine_result]
        
        # Process each day's engine result
        days = []
        
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
            
            # FIX #3 (02.02.2026): Update transit destinations after gap filling
            # Gap filling inserts new POI between transit and its original destination
            # This causes "to" field to point to wrong POI
            day_items = self._update_transit_destinations(day_items)
            
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
            if validation_warnings:
                print(f"[TIMELINE VALIDATOR] Day {day_num + 1}:")
                for warning in validation_warnings:
                    print(f"  {warning}")
            
            day_plan = DayPlan(
                day=day_num + 1,
                items=day_items,  # Use healed items with no overlaps
                quality_badges=day_quality_badges  # ETAP 2 Day 5
            )
            
            days.append(day_plan)
        
        # Generuj plan_id
        plan_id = str(uuid.uuid4())
        
        return PlanResponse(
            plan_id=plan_id,
            version=1,
            days=days
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
        
        if has_car and first_attraction:
            # BUGFIX: Parking musi kończyć się PRZED pierwszą atrakcją
            # attraction_start = parking_end + walk_time
            first_attr_start = first_attraction.get("start_time", day_start)
            
            # BUGFIX (31.01.2026 - Problem #2): Pass POI dict, not engine attraction item
            # first_attraction = {"type": "attraction", "poi": {...}, "start_time": "..."}
            # parking_item needs POI data for parking_address, parking_lat, parking_lng
            first_poi = first_attraction.get("poi", {})
            
            parking_item = self._generate_parking_item(
                first_poi,  # Pass POI dict with parking data
                day_start,
                first_attr_start  # Pass first attraction start time
            )
            items.append(parking_item)
        
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
                lunch_item = LunchBreakItem(
                    type=ItemType.LUNCH_BREAK,
                    start_time=item.get("start_time", "12:00"),
                    end_time=item.get("end_time", "13:30"),
                    duration_min=item.get("duration_min", 90),  # Add duration_min from engine
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
                
                # FIX #3.1: Removed current_parking_name requirement
                # Create parking for ANY location change with car, even without parking_name in POI
                if (has_car and 
                    first_attraction_index > 0 and 
                    location_changed):
                    
                    # Generate parking item before this attraction
                    attr_start_time_orig = item.get("start_time")
                    
                    # Calculate parking start: attraction_start - parking_duration - walk_time
                    from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                    
                    parking_duration = 15
                    walk_time_raw = poi.get("parking_walk_time_min")
                    walk_time = int(walk_time_raw) if walk_time_raw and walk_time_raw > 0 else 5
                    
                    attr_start_min = time_to_minutes(attr_start_time_orig)
                    parking_start_min = attr_start_min - parking_duration - walk_time
                    
                    # BUGFIX (19.02.2026 - UAT Round 2, Bug #1): Parking overlap with transit
                    # Ensure parking starts AFTER transit ends (never before/during transit!)
                    if items:
                        last_item = items[-1]
                        if last_item.type == ItemType.TRANSIT:
                            transit_end_min = time_to_minutes(last_item.end_time)
                            if parking_start_min < transit_end_min:
                                # Overlap detected! Move parking to start right after transit
                                parking_start_min = transit_end_min
                    
                    # FIX #2 (20.02.2026 - UAT Round 3): CASCADE UPDATE
                    # Problem: Round 2 fix adjusted parking_start but NOT attraction_start
                    # Result: parking moved forward but attraction stayed → OVERLAP!
                    # Solution: ALWAYS recalculate attraction start from actual parking times
                    # Formula: attraction.start = parking.end + walk_time
                    parking_end_min = parking_start_min + parking_duration
                    attr_start_min = parking_end_min + walk_time
                    attr_start_time = minutes_to_time(attr_start_min)  # Corrected start time
                    
                    parking_start = minutes_to_time(parking_start_min)
                    
                    # Generate parking item
                    parking_item = self._generate_parking_item(
                        poi,
                        parking_start,
                        attr_start_time  # Use corrected time (includes walk_time!)
                    )
                    items.append(parking_item)
                    last_parking_name = current_parking_name
                else:
                    # No parking created for this attraction - use original engine time
                    attr_start_time = item.get("start_time")
                
                # 5. ATTRACTION (4.11 - z cost estimation)
                
                # BUGFIX: Correct first attraction timing if parking exists
                # FIX #2: Only adjust if this is first attraction (attr_start_time may already be set above)
                if first_attraction_index == 0 and has_car and first_attraction:
                    # First attraction with parking - adjust start time
                    # parking duration: 15 min, walk time: from POI
                    from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
                    
                    parking_duration = 15
                    # BUGFIX (02.02.2026): Use actual POI parking_walk_time_min, not default 5
                    walk_time_raw = first_attraction.get("poi", {}).get("parking_walk_time_min")
                    walk_time = int(walk_time_raw) if walk_time_raw and walk_time_raw > 0 else 5
                    
                    # Calculate corrected start time: day_start + parking + walk
                    corrected_start_min = time_to_minutes(day_start) + parking_duration + walk_time
                    attr_start_time = minutes_to_time(corrected_start_min)
                    
                    # Track first parking name
                    last_parking_name = first_attraction.get("poi", {}).get("parking_name", "")
                
                first_attraction_index += 1
                
                attraction_item = self._generate_attraction_item(
                    item.get("poi"),
                    attr_start_time,
                    user,
                    trip_input.group.type,
                    context  # ETAP 2 Day 5: Pass context for explainability
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
                has_car = "car" in (trip_input.transport_modes or [])
                
                if has_car and duration >= 10:
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
                free_time_item = FreeTimeItem(
                    type=ItemType.FREE_TIME,
                    start_time=item.get("start_time", "12:00"),
                    end_time=item.get("end_time", "12:30"),
                    duration_min=item.get("duration_min", 30),
                    label=item.get("description", "Czas wolny")
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
        
        # 8. DAY_END
        items.append(DayEndItem(time=day_end))
        
        return items

    def _generate_parking_item(
        self,
        poi_dict: Dict[str, Any],  # POI jako dict z engine
        parking_start: str,
        attraction_start: str  # First attraction start time
    ) -> ParkingItem:
        """
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
        
        return ParkingItem(
            type=ItemType.PARKING,
            start_time=parking_start,
            end_time=parking_end,
            name=poi_dict.get("parking_name") or "Parking",
            address=parking_address,
            lat=parking_lat,
            lng=parking_lng,
            parking_type=ParkingType.PAID,  # FIXME: z POI parking_type?
            walk_time_min=walk_time
        )

    def _generate_attraction_item(
        self,
        poi_dict: Dict[str, Any],  # POI jako dict z engine
        start_time: str,
        user: Dict[str, Any],
        group_type: str,
        context: Dict[str, Any] = None  # ETAP 2 Day 5: Add context for explainability
    ) -> AttractionItem:
        """
        Generuje AttractionItem z cost estimation (4.11).
        
        ETAP 2 Day 5: Dodano explainability (why_selected) i quality badges.
        
        Cost estimation (4.11):
        - ticket_normal jako baseline
        - family_kids: (2×normal + 2×reduced)
        - free_entry: 0
        """
        # Engine zwraca dict z POI
        visit_min = poi_dict.get("time_min", 60)
        
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
            cost_estimate=estimated_cost,  # Poprawiono z estimated_cost
            cost_note=cost_note,  # BUGFIX (19.02.2026 - Issue #7)
            ticket_info=TicketInfo(
                ticket_normal=poi_dict.get("ticket_normal", 0) or 0,
                ticket_reduced=poi_dict.get("ticket_reduced", 0) or 0,
                free_entry=poi_dict.get("free_entry", False) or False
            ),
            parking=ParkingInfo(
                name=poi_dict.get("parking_name") or "Brak parkingu",
                walk_time_min=poi_dict.get("parking_walk_time_min", 5) or 5
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
        
        ticket_normal = poi_dict.get("ticket_normal", 0) or 0
        ticket_reduced = poi_dict.get("ticket_reduced", 0) or 0
        
        # Extract user info
        group_type = user.get("target_group", "solo")
        group_size = user.get("group_size", 1)
        children_age = user.get("children_age")  # Only relevant for family_kids
        
        # BUGFIX: Fallback for POI without price data (like DINO PARK with "brak danych")
        if ticket_normal == 0 and ticket_reduced == 0 and not free_entry:
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
        
        print(f"[GAP FILLING] Current attractions: {attraction_count}/{hard_limit}")
        
        for i, item in enumerate(items):
            result.append(item)
            item_dict = item.dict()
            item_type = item_dict['type']
            
            # Get end time of current item
            current_end = None
            if item_type in ['attraction', 'transit', 'lunch_break', 'parking']:
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
                # Client issue: Gaps before parking items were not filled
                next_start = None
                if next_type in ['attraction', 'lunch_break', 'parking', 'dinner_break', 'free_time']:
                    if 'start_time' in next_item:
                        next_start = time_to_minutes(next_item['start_time'])
                
                if next_start is not None:
                    gap = next_start - current_end
                    
                    print(f"[GAP FILLING] {item_type} ends {current_end} -> {next_type} starts {next_start} = GAP {gap} min")
                    
                    # BUGFIX (31.01.2026 - Problem #3): Skip gap filling before lunch if gap <50 min
                    # FIX #4 (15.02.2026): Reduced from 60 to 50 min to be less aggressive
                    # Lunch can start earlier instead of adding unnecessary free_time
                    if next_type == 'lunch_break' and gap < 50:
                        print(f"[GAP FILLING] ✗ SKIP filling {gap} min gap before lunch (lunch can start earlier)")
                        continue
                    
                    # BUGFIX (02.02.2026 - FIX #2): Skip free_time if next attraction opens soon
                    # Check if gap is caused by waiting for opening hours
                    if next_type == 'attraction' and gap > 0:
                        next_poi = next_item.get('poi')
                        if next_poi and context.get('date'):
                            # Check if POI is already open or opens within gap
                            poi_start_time = current_end
                            poi_duration = next_poi.get('time_min', 30)
                            
                            # If POI is open now, don't add free_time - attraction can start earlier
                            if is_open(next_poi, int(poi_start_time), poi_duration, context.get('season', 'all'), context):
                                print(f"[GAP FILLING] ✗ SKIP filling {gap} min gap - next attraction is already open, can start earlier")
                                continue
                    
                    # FIX #4 (15.02.2026): Lower threshold from 20 to 15 min
                    if gap > 15:
                        # HOTFIX (02.02.2026): Check if attraction limit reached
                        if attraction_count >= hard_limit:
                            print(f"[GAP FILLING] ✗ SKIP - attraction limit reached ({attraction_count}/{hard_limit})")
                            # Add free_time instead of POI
                            free_time_start = minutes_to_time(current_end)
                            free_time_end = minutes_to_time(min(current_end + gap, next_start))
                            free_duration = min(gap, 40)  # Max 40 min free time
                            
                            result.append(FreeTimeItem(
                                type=ItemType.FREE_TIME,
                                start_time=free_time_start,
                                end_time=minutes_to_time(current_end + free_duration),
                                duration_min=free_duration,
                                label="Czas wolny",
                                description="Spacer, kawa, odpoczynek"
                            ))
                            continue
                        
                        # BUGFIX (31.01.2026 - Problem #4): TRY find POI first before free_time
                        poi_found = False
                        best_poi = None
                        best_score = -9999
                        best_duration = 0
                        best_travel = 0
                        
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
                            
                            # Simple scoring: prefer nearby, short duration
                            # Shorter = better (fits in gaps)
                            # Closer = better (less travel)
                            score = 100 - travel * 0.5 - poi_duration * 0.2
                            
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
                                context  # ETAP 2 Day 5: Pass context for explainability
                            )
                            result.append(attraction_item)
                            
                            # Mark as used
                            used_poi_ids.add(best_poi.get('id', ''))
                            
                            # HOTFIX (02.02.2026): Increment attraction counter
                            attraction_count += 1
                            print(f"[GAP FILLING] Attraction count after fill: {attraction_count}/{hard_limit}")
                            
                            continue  # Skip free_time - POI added instead
                        
                        # NO POI FOUND - add free_time as LAST RESORT
                        gap_duration = min(gap, 40)  # Max 40 min free time
                        free_time_start = minutes_to_time(current_end)
                        free_time_end = minutes_to_time(current_end + gap_duration)
                        
                        print(f"[GAP FILLING] WARNING: LAST RESORT: No available POI, adding free_time ({free_time_start}-{free_time_end})")
                        
                        free_time_item = FreeTimeItem(
                            type=ItemType.FREE_TIME,
                            start_time=free_time_start,
                            end_time=free_time_end,
                            duration_min=gap_duration,
                            label="Czas wolny"
                        )
                        
                        result.append(free_time_item)
        
        # FIX #4 (15.02.2026): Add end-of-day free_time if gap >30 min before day_end
        # Client feedback: "Brakuje free_time na końcówkach dni"
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
                
                if gap_to_end > 30:
                    print(f"[GAP FILLING] Adding end-of-day free_time: {gap_to_end} min gap before day_end ({last_end_str} → {day_end_str})")
                    
                    # Cap at 90 min to avoid excessively long free time
                    free_time_duration = min(gap_to_end, 90)
                    free_time_start = last_end_str
                    free_time_end = minutes_to_time(last_end_min + free_time_duration)
                    
                    end_of_day_item = FreeTimeItem(
                        type=ItemType.FREE_TIME,
                        start_time=free_time_start,
                        end_time=free_time_end,
                        duration_min=free_time_duration,
                        label="Czas wolny na koniec dnia"
                    )
                    
                    # Insert before DAY_END
                    if result[-1].dict()['type'] == 'day_end':
                        result.insert(-1, end_of_day_item)
                    else:
                        result.append(end_of_day_item)
                    
                    print(f"[GAP FILLING] ✓ Added end-of-day free_time: {free_time_start}-{free_time_end} ({free_time_duration} min)")
                    print(f"[GAP FILLING] ✓ Added end-of-day free_time: {free_time_start}-{free_time_end} ({free_time_duration} min)")
        
        print(f"[GAP FILLING] Final: {len(items)} -> {len(result)} items")
        return result

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
        for i, item in enumerate(items):
            # Skip non-transit items
            if item.type != ItemType.TRANSIT:
                continue
            
            # Find NEXT attraction after this transit
            next_attraction = None
            for j in range(i + 1, len(items)):
                if items[j].type == ItemType.ATTRACTION:
                    next_attraction = items[j]
                    break
            
            # Update "to" to match next attraction
            if next_attraction:
                item.to_location = next_attraction.name
                print(f"[TRANSIT FIX] Updated transit destination: '{item.from_location}' -> '{item.to_location}'")
            else:
                # No attraction after transit - shouldn't happen, but log it
                print(f"[TRANSIT FIX] WARNING: Transit has no next attraction: '{item.from_location}' -> '{item.to_location}' (kept as is)")
            
            # FIX #4: Update "from" to match PREVIOUS attraction
            # Find last attraction BEFORE this transit
            prev_attraction = None
            for j in range(i - 1, -1, -1):
                if items[j].type == ItemType.ATTRACTION:
                    prev_attraction = items[j]
                    break
            
            if prev_attraction:
                item.from_location = prev_attraction.name
                print(f"[TRANSIT FIX] Updated transit origin: '{item.from_location}' ← '{prev_attraction.name}'")
        
        return items
