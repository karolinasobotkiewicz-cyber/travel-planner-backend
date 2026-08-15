"""FIX #273 — Katowice remaining client: polish gate, caps, copy, denies."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _city_needs_car_gap_polish,
    _filter_meal_suggestions,
    _is_gliwice_stop_name,
    _is_zabrze_stop_name,
)
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    ParkingInfo,
    RestaurantSuggestion,
    TicketInfo,
)
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.planner.explainability import _explain_category_highlight, explain_poi_selection
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def test_fix273_katowice_uses_shared_polish():
    assert _city_needs_car_gap_polish("Katowice")
    assert _city_needs_car_gap_polish("katowice")
    assert _city_needs_car_gap_polish("Poznań")
    assert _city_needs_car_gap_polish("Kraków")


def test_fix273_caps():
    assert visit_duration_hard_cap({"name": "Browar Mariacki"}, for_scheduling=True) == 75
    assert visit_duration_hard_cap({"name": "Rynek w Katowicach"}, for_scheduling=True) == 60
    assert visit_duration_hard_cap({"name": "Spodek"}, for_scheduling=True) == 60
    assert visit_duration_hard_cap(
        {"name": "Dolina Trzech Stawów"}, for_scheduling=True
    ) == 90
    assert visit_duration_hard_cap(
        {"name": "Tężnia Solankowa"}, for_scheduling=True
    ) == 60
    assert visit_duration_hard_cap(
        {"name": "Górnośląski Park Etnograficzny"}, for_scheduling=True
    ) == 90
    assert visit_duration_hard_cap({"name": "Papugarnia Carmen"}, for_scheduling=True) == 75
    assert visit_duration_hard_cap(
        {"name": "Planetarium Śląskie"}, for_scheduling=True
    ) == 90


def test_fix273_nikiszowiec_not_museum_copy():
    reason = _explain_category_highlight(
        {"name": "Nikiszowiec", "tags": "museum,heritage"},
        {"target_group": "family_kids"},
    )
    assert reason
    assert "osiedle" in reason.lower()
    assert "ekspozycja" not in reason.lower()


def test_fix273_gliwice_must_see_not_katowice():
    reasons = explain_poi_selection(
        {"name": "Rynek w Gliwicach", "priority_level": 12, "city": "Katowice"},
        {"requested_city": "Katowice"},
        {"target_group": "couples"},
    )
    blob = " ".join(reasons).lower()
    assert "gliwic" in blob
    assert "katowicach" not in blob


def test_fix273_nemo_trip_repeat_and_kosciuszki_church():
    assert poi_trip_repeat_key("Park Wodny Nemo") == "kat_nemo"
    assert poi_trip_repeat_key("Kościół św. Michała") == poi_trip_repeat_key(
        "Park Kościuszki"
    )
    assert poi_trip_repeat_key(
        "Kościół Świętego Michała Archanioła"
    ) == poi_trip_repeat_key("Park Kościuszki")


def test_fix273_planetarium_not_active_sport():
    assert should_deny_poi_for_profile(
        {"name": "Planetarium Śląskie"},
        {
            "target_group": "friends",
            "preferences": ["active_sport", "history_mystery"],
            "travel_style": "adventure",
        },
    )
    assert poi_covers_preference_report(
        {"name": "House of Air - Park Trampolin", "tags": "active_sport"},
        "active_sport",
    )
    assert not poi_covers_preference_report(
        {"name": "Planetarium Śląskie", "tags": "active_sport"},
        "active_sport",
    )


def test_fix273_sw_anny_off_water_relax():
    assert should_deny_poi_for_profile(
        {"name": "Kościół św. Anny"},
        {
            "target_group": "couples",
            "preferences": ["water_attractions", "local_food_experience", "relaxation"],
            "travel_style": "relax",
        },
    )


def test_fix273_ciao_italia_not_regional():
    sugs = [
        RestaurantSuggestion(
            id="r1",
            name="Ciao Italia",
            lat=50.26,
            lng=19.02,
            cuisine_type="italian",
        ),
        RestaurantSuggestion(
            id="r2",
            name="Karczma Śląska",
            lat=50.26,
            lng=19.02,
            cuisine_type="polish",
        ),
    ]
    out = _filter_meal_suggestions(
        sugs,
        preferences=["local_food_experience"],
        target_group="couples",
    )
    names = [s.name for s in out]
    assert "Ciao Italia" not in names
    assert "Karczma Śląska" in names


def test_fix273_zabrze_gliwice_names():
    assert _is_zabrze_stop_name("Kopalnia Guido")
    assert _is_gliwice_stop_name("Rynek w Gliwicach")


def test_fix273_rewrite_satellite_city():
    svc = PlanService.__new__(PlanService)
    it = AttractionItem(
        poi_id="t",
        name="Rynek w Gliwicach",
        start_time="10:00",
        end_time="11:00",
        duration_min=60,
        description_short="d",
        lat=50.29,
        lng=18.67,
        address="a",
        city="Katowice",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="p", walk_time_min=0),
        why_selected=["Must-see w Katowicach"],
    )
    out = svc._rewrite_katowice_satellite_copy([it], day_num=3)
    assert out[0].city == "Gliwice"
    assert "Katowicach" not in " ".join(out[0].why_selected)

    tychy = AttractionItem(
        poi_id="t2",
        name="Wodny Park Tychy",
        start_time="12:00",
        end_time="13:00",
        duration_min=60,
        description_short="d",
        lat=50.12,
        lng=19.00,
        address="a",
        city="Katowice",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="p", walk_time_min=0),
        why_selected=["Must-see w Katowicach"],
    )
    out2 = svc._rewrite_katowice_satellite_copy([tychy], day_num=1)
    assert out2[0].city == "Tychy"
    assert "Katowicach" not in " ".join(out2[0].why_selected)
