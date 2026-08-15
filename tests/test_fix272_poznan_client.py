"""FIX #272 — Poznań remaining client: polish gate, caps, tags, clusters."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _city_needs_car_gap_polish,
    _is_gniezno_stop_name,
    _is_kornik_stop_name,
    _lunch_latest_min,
)
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    LunchBreakItem,
    ParkingInfo,
    RestaurantSuggestion,
    TicketInfo,
)
from app.domain.planner.engine import poi_geo_region_key, visit_duration_hard_cap
from app.domain.planner.explainability import _explain_category_highlight
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile


def test_fix272_poznan_uses_shared_polish():
    assert _city_needs_car_gap_polish("Poznań")
    assert _city_needs_car_gap_polish("poznan")


def test_fix272_krakow_warszawa_still_on():
    assert _city_needs_car_gap_polish("Kraków")
    assert _city_needs_car_gap_polish("Warszawa")


def test_fix272_family_lunch_latest():
    assert _lunch_latest_min({"target_group": "family_kids"}) == 14 * 60
    assert _lunch_latest_min({"target_group": "couples"}) == 14 * 60 + 30


def test_fix272_caps():
    assert visit_duration_hard_cap({"name": "Muzeum Iluzji"}, for_scheduling=True) == 75
    assert visit_duration_hard_cap({"name": "Palmiarnia Poznańska"}, for_scheduling=True) == 75
    assert visit_duration_hard_cap({"name": "Szachty"}, for_scheduling=True) == 75
    assert visit_duration_hard_cap({"name": "Letni Tor Saneczkowy"}, for_scheduling=True) == 45
    assert visit_duration_hard_cap({"name": "Ratusz w Poznaniu"}, for_scheduling=True) == 60
    assert visit_duration_hard_cap({"name": "Pomnik Ofiar Czerwca 1956"}, for_scheduling=True) == 25
    assert visit_duration_hard_cap(
        {"name": "Park Stare Koryto Warty"}, for_scheduling=True
    ) == 75
    assert visit_duration_hard_cap(
        {"name": "Muzeum Początków Państwa Polskiego"}, for_scheduling=True
    ) == 90


def test_fix272_gniezno_kornik_regions():
    assert poi_geo_region_key({"name": "Muzeum Początków Państwa Polskiego"}) == "region_gniezno"
    assert poi_geo_region_key({"name": "Zamek w Kórniku"}) == "region_kornik"
    assert _is_gniezno_stop_name("Katedra w Gnieźnie")
    assert _is_gniezno_stop_name("Katedra Gnieźnieńska")
    assert _is_gniezno_stop_name("Muzeum Początków Państwa Polskiego")
    assert _is_kornik_stop_name("Arboretum Kórnickie")
    assert _is_kornik_stop_name("Arboretum w Kórniku")


def test_fix272_genius_loci_not_nature():
    assert not poi_covers_preference_report(
        {"name": "Rezerwat Genius Loci", "tags": "garden,nature_landscape"},
        "nature_landscape",
    )
    reason = _explain_category_highlight(
        {"name": "Rezerwat Genius Loci", "tags": "garden"},
        {"target_group": "seniors"},
    )
    assert reason
    assert "archeolog" in reason.lower()


def test_fix272_cytadela_not_underground():
    assert not poi_covers_preference_report(
        {"name": "Park Cytadela", "tags": "underground,park"},
        "underground",
    )


def test_fix272_jump_arena_needs_sport():
    assert should_deny_poi_for_profile(
        {"name": "Jump Arena"},
        {
            "target_group": "friends",
            "preferences": ["underground", "history_mystery", "museum_heritage"],
            "travel_style": "adventure",
        },
    )
    assert not should_deny_poi_for_profile(
        {"name": "Jump Arena"},
        {
            "target_group": "friends",
            "preferences": ["active_sport"],
            "travel_style": "adventure",
        },
    )


def test_fix272_zamek_cesarski_off_family_relax():
    assert should_deny_poi_for_profile(
        {"name": "Zamek Cesarski"},
        {
            "target_group": "family_kids",
            "preferences": ["kids_attractions", "relaxation"],
            "travel_style": "relax",
        },
    )


def test_fix272_strip_city_on_gniezno_day():
    svc = PlanService.__new__(PlanService)

    def _attr(name: str, st: str, en: str) -> AttractionItem:
        sh, sm = (int(x) for x in st.split(":"))
        eh, em = (int(x) for x in en.split(":"))
        return AttractionItem(
            poi_id="t",
            name=name,
            start_time=st,
            end_time=en,
            duration_min=eh * 60 + em - (sh * 60 + sm),
            description_short="d",
            lat=52.4,
            lng=16.9,
            address="a",
            cost_estimate=0,
            ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
            parking=ParkingInfo(name="p", walk_time_min=0),
        )

    out = svc._strip_mixed_opn_krakow_attractions(
        [
            _attr("Muzeum Narodowe w Poznaniu", "10:00", "11:00"),
            _attr("Muzeum Początków Państwa Polskiego", "11:10", "13:00"),
            _attr("Park Cytadela", "16:00", "17:00"),
        ],
        None,
        5,
    )
    names = [it.name for it in out]
    assert names == ["Muzeum Początków Państwa Polskiego"]

    late = svc._strip_mixed_opn_krakow_attractions(
        [
            _attr("Park Cytadela", "10:00", "11:00"),
            _attr("Wartostrada", "11:10", "12:00"),
            _attr("Podziemia Fary", "13:10", "13:45"),
            _attr("Zamek w Kórniku", "15:02", "16:02"),
            _attr("Arboretum w Kórniku", "19:46", "20:35"),
        ],
        None,
        2,
    )
    late_names = [it.name for it in late]
    assert "Zamek w Kórniku" not in late_names
    assert "Arboretum w Kórniku" not in late_names
    assert "Park Cytadela" in late_names

    locked = svc._strip_mixed_opn_krakow_attractions(
        [
            _attr("Park Cytadela", "10:00", "11:00"),
            _attr("Katedra Gnieźnieńska", "16:51", "17:27"),
            _attr("Muzeum Początków Państwa Polskiego", "17:36", "19:06"),
        ],
        None,
        6,
    )
    assert [it.name for it in locked] == [
        "Katedra Gnieźnieńska",
        "Muzeum Początków Państwa Polskiego",
    ]


def test_fix272_force_kornik_arboretum_coords():
    svc = PlanService.__new__(PlanService)
    it = AttractionItem(
        poi_id="t",
        name="Arboretum w Kórniku",
        start_time="15:00",
        end_time="16:00",
        duration_min=60,
        description_short="d",
        lat=52.4064,
        lng=16.9252,
        address="Poznań",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="p", walk_time_min=0),
    )
    out = svc._force_known_good_poi_coords([it], day_num=2)
    assert abs(out[0].lat - 52.2447) < 0.002
    assert abs(out[0].lng - 17.0956) < 0.002


def test_fix272_coalesce_kornik_to_one_day():
    from types import SimpleNamespace

    svc = PlanService.__new__(PlanService)

    def _attr(name: str, st: str, en: str) -> AttractionItem:
        sh, sm = (int(x) for x in st.split(":"))
        eh, em = (int(x) for x in en.split(":"))
        return AttractionItem(
            poi_id="t",
            name=name,
            start_time=st,
            end_time=en,
            duration_min=eh * 60 + em - (sh * 60 + sm),
            description_short="d",
            lat=52.24,
            lng=17.09,
            address="a",
            cost_estimate=0,
            ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
            parking=ParkingInfo(name="p", walk_time_min=0),
        )

    days = [
        SimpleNamespace(day=2, items=[_attr("Zamek w Kórniku", "15:02", "16:02")]),
        SimpleNamespace(day=5, items=[_attr("Arboretum w Kórniku", "09:30", "11:00")]),
    ]
    out = svc._coalesce_poznan_daytrips(days, {"requested_city": "Poznań"})
    d5 = next(d for d in out if d.day == 5)
    names = [it.name for it in d5.items]
    assert "Arboretum w Kórniku" in names
    assert "Zamek w Kórniku" in names
    d2 = next(d for d in out if d.day == 2)
    assert not any("kórnik" in (it.name or "").lower() for it in d2.items)


def test_fix272_strip_cleared_restaurant_transit():
    from app.domain.models.plan import TransitItem, TransitMode

    svc = PlanService.__new__(PlanService)
    lunch = LunchBreakItem(
        type=ItemType.LUNCH_BREAK,
        start_time="13:13",
        end_time="14:13",
        duration_min=60,
        suggestions=[],
    )
    tr = TransitItem(
        type=ItemType.TRANSIT,
        start_time="11:55",
        end_time="13:13",
        duration_min=78,
        mode=TransitMode.CAR,
        from_location="Zamek w Kórniku",
        to_location="Restauracja Ratuszova – Stary Rynek 55 Poznań",
        routing_source="estimated_road",
    )
    out = svc._strip_transits_to_unscheduled_destinations([tr, lunch], day_num=5)
    assert not any(
        getattr(getattr(it, "type", None), "value", None) == "transit"
        or str(getattr(it, "type", "")) == "transit"
        for it in out
        if (getattr(it, "to_location", "") or "").lower().startswith("restauracja ratusz")
    )


def test_fix272_clear_far_kornik_meal_sorted():
    svc = PlanService.__new__(PlanService)
    castle = AttractionItem(
        poi_id="t",
        name="Zamek w Kórniku",
        start_time="15:02",
        end_time="16:02",
        duration_min=60,
        description_short="d",
        lat=52.2440,
        lng=17.0900,
        address="Kórnik",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="p", walk_time_min=0),
    )
    lunch = LunchBreakItem(
        type=ItemType.LUNCH_BREAK,
        start_time="16:10",
        end_time="16:50",
        duration_min=40,
        suggestions=[
            RestaurantSuggestion(
                id="r1",
                name="Just Friends Poznań",
                lat=52.4064,
                lng=16.9252,
            )
        ],
    )
    # Meal first in the list — clear must walk clock order, not insert order.
    out = svc._clear_far_daytrip_meals([lunch, castle], day_num=2)
    meals = [
        it for it in out
        if getattr(getattr(it, "type", None), "value", getattr(it, "type", None))
        == ItemType.LUNCH_BREAK.value
    ]
    assert meals
    assert list(getattr(meals[0], "suggestions", None) or []) == []
