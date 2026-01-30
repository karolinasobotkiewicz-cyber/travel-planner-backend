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
    FreeTimeItem,
    TicketInfo,
    ParkingInfo,
    ItemType,
    TransitMode,
    ParkingType,  # Dodano dla parking_type
)
from app.application.services.trip_mapper import trip_input_to_engine_params
from app.domain.planner.engine import build_day
from app.infrastructure.repositories import POIRepository


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
        
        # WAŻNE: Engine expects dict, nie Pydantic models
        # Konwersja POI → dict
        all_pois_dict = [poi.model_dump() for poi in all_pois]
        
        if not all_pois_dict:
            # FIXME: graceful handling gdy brak POI
            # Na razie zwróć pusty plan
            return PlanResponse(
                plan_id=str(uuid.uuid4()),
                version=1,
                days=[]
            )
        
        # Generuj plan dla każdego dnia
        days = []
        
        for day_num in range(trip_input.trip_length.days):
            # Update context dla tego dnia
            context["date"] = dates[day_num]
            
            # Wywołaj engine.build_day()
            # Argumenty: (pois, user, context, day_start, day_end)
            engine_result = build_day(
                all_pois_dict,  # POIs jako dict, nie Pydantic
                user,
                context,
                day_start,  # User-provided start time
                day_end     # User-provided end time
            )
            
            # Konwersja engine result → PlanResponse items
            day_items = self._convert_engine_result_to_items(
                engine_result,
                day_start,
                day_end,
                context,
                user,
                trip_input
            )
            
            day_plan = DayPlan(
                day=day_num + 1,
                items=day_items
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
            parking_item = self._generate_parking_item(
                first_attraction,
                day_start
            )
            items.append(parking_item)
        
        # 3. KONWERTUJ ITEMS Z ENGINE
        lunch_added = False  # Track czy engine dodał lunch
        
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
            
            elif item_type == "attraction":
                # 5. ATTRACTION (4.11 - z cost estimation)
                attraction_item = self._generate_attraction_item(
                    item.get("poi"),
                    item.get("start_time"),
                    user,
                    trip_input.group.type
                )
                items.append(attraction_item)
            
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
                
                transit_item = TransitItem(
                    type=ItemType.TRANSIT,
                    start_time=start_time,
                    end_time=end_time,
                    duration_min=duration,
                    mode=item.get("mode", "walk"),
                    from_location=item.get("from"),
                    to_location=item.get("to")
                )
                items.append(transit_item)
        
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
        start_time: str
    ) -> ParkingItem:
        """
        4.10: Parking logic - 1 parking na start dnia.
        
        - Z pierwszej atrakcji (parking_name, parking_lat, parking_lng)
        - Stały czas: 15 minut
        - Tylko dla transport_modes = car
        """
        # Stały czas: 15 minut
        end_time = self._add_minutes(start_time, 15)
        
        return ParkingItem(
            type=ItemType.PARKING,
            start_time=start_time,
            end_time=end_time,
            name=poi_dict.get("parking_name") or "Parking",
            address=poi_dict.get("parking_address", ""),
            lat=poi_dict.get("parking_lat") or poi_dict.get("lat", 0.0),
            lng=poi_dict.get("parking_lng") or poi_dict.get("lng", 0.0),
            parking_type=ParkingType.PAID,  # FIXME: z POI?
            walk_time_min=5  # FIXME: oblicz z odległości?
        )

    def _generate_attraction_item(
        self,
        poi_dict: Dict[str, Any],  # POI jako dict z engine
        start_time: str,
        user: Dict[str, Any],
        group_type: str
    ) -> AttractionItem:
        """
        Generuje AttractionItem z cost estimation (4.11).
        
        Cost estimation (4.11):
        - ticket_normal jako baseline
        - family_kids: (2×normal + 2×reduced)
        - free_entry: 0
        """
        # Engine zwraca dict z POI
        visit_min = poi_dict.get("time_min", 60)
        
        end_time = self._add_minutes(start_time, visit_min)
        
        # 4.11: Cost estimation
        estimated_cost = self._estimate_cost(poi_dict, group_type)
        
        return AttractionItem(
            type=ItemType.ATTRACTION,
            start_time=start_time,
            end_time=end_time,
            duration_min=visit_min,
            poi_id=poi_dict.get("id", ""),
            name=poi_dict.get("name", ""),
            description_short=poi_dict.get("description_short", ""),
            lat=poi_dict.get("lat", 0.0),
            lng=poi_dict.get("lng", 0.0),
            address=poi_dict.get("address", ""),
            cost_estimate=estimated_cost,  # Poprawiono z estimated_cost
            ticket_info=TicketInfo(
                ticket_normal=poi_dict.get("ticket_normal", 0) or 0,
                ticket_reduced=poi_dict.get("ticket_reduced", 0) or 0,
                free_entry=poi_dict.get("free_entry", False) or False
            ),
            parking=ParkingInfo(
                name=poi_dict.get("parking_name") or "Brak parkingu",
                walk_time_min=5  # FIXME: oblicz z odległości?
            ),
            pro_tip=poi_dict.get("pro_tip")  # ADD pro_tip from POI
        )

    def _estimate_cost(self, poi_dict: Dict[str, Any], group_type: str) -> int:
        """
        4.11: Cost estimation logic.
        
        - ticket_normal jako baseline
        - family_kids: (2×normal + 2×reduced)
        - free_entry: 0
        """
        free_entry = poi_dict.get("free_entry", False)
        
        if free_entry:
            return 0
        
        ticket_normal = poi_dict.get("ticket_normal", 0) or 0
        ticket_reduced = poi_dict.get("ticket_reduced", 0) or 0
        
        if group_type == "family_kids":
            # Zakładamy: 2 dorosłych + 2 dzieci
            return (2 * ticket_normal) + (2 * ticket_reduced)
        
        # Inne grupy: baseline
        return ticket_normal

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
            "bus": TransitMode.BUS,
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

    def _add_minutes(self, time_str: str, minutes: int) -> str:
        """Helper: dodaje minuty do czasu HH:MM."""
        from app.domain.planner.time_utils import (
            time_to_minutes,
            minutes_to_time
        )
        
        total_min = time_to_minutes(time_str) + minutes
        return minutes_to_time(total_min)
