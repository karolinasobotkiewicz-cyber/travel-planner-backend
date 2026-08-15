"""FIX #271 — Kraków remaining client: caps, denies, why_selected, polish gate."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _city_needs_car_gap_polish,
    _is_ojcow_stop_name,
)
from app.domain.models.plan import AttractionItem, ParkingInfo, TicketInfo
from app.domain.planner.engine import (
    poi_geo_region_key,
    visit_duration_hard_cap,
)
from app.domain.planner.explainability import (
    _explain_category_highlight,
    _explain_duration_fit,
    explain_poi_selection,
)
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile


def test_fix271_krakow_uses_shared_polish():
    assert _city_needs_car_gap_polish("Kraków")
    assert _city_needs_car_gap_polish("krakow")


def test_fix271_city_tourism_without_trip_type():
    from app.domain.planner.city_copy import is_city_tourism_trip

    assert is_city_tourism_trip({"requested_city": "Kraków"})
    assert not is_city_tourism_trip({"is_zakopane_trip": True, "requested_city": "Zakopane"})


def test_fix271_warszawa_polish_still_on():
    assert _city_needs_car_gap_polish("Warszawa")


def test_fix271_labirynt_capped():
    assert visit_duration_hard_cap(
        {"name": "Lustrzany Labirynt"}, for_scheduling=True
    ) == 40


def test_fix271_maczuga_capped():
    assert visit_duration_hard_cap(
        {"name": "Maczuga Herkulesa"}, for_scheduling=True
    ) == 60


def test_fix271_ojcow_region():
    assert poi_geo_region_key({"name": "Jaskinia Łokietka"}) == "region_ojcow"
    assert poi_geo_region_key({"name": "Zamek Pieskowa Skała"}) == "region_ojcow"


def test_fix271_jordana_denied_cultural():
    assert should_deny_poi_for_profile(
        {"name": "Park Jordana"},
        {
            "target_group": "couples",
            "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
            "travel_style": "cultural",
        },
    )


def test_fix271_lotnikow_denied_adventure_underground():
    assert should_deny_poi_for_profile(
        {"name": "Park Lotników Polskich"},
        {
            "target_group": "friends",
            "preferences": ["underground", "history_mystery", "museum_heritage"],
            "travel_style": "adventure",
        },
    )


def test_fix271_jaskinia_not_theme_park():
    reason = _explain_category_highlight(
        {"name": "Jaskinia Ciemna", "tags": ["amusement"]},
        {"target_group": "solo"},
    )
    assert reason
    assert "tematycznego" not in reason.lower()
    assert "jaskini" in reason.lower()


def test_fix271_brama_not_long_and_short():
    reasons = explain_poi_selection(
        {
            "name": "Brama Floriańska",
            "priority_level": 6,
            "time_min": 20,
            "tags": ["museum", "heritage"],
        },
        {"requested_city": "Kraków"},
        {"target_group": "couples", "travel_style": "relax"},
    )
    blob = " ".join(reasons).lower()
    assert not (
        "dłuższej wizyty" in blob and "krótki przystanek" in blob
    )


def _attr(name: str, st: str, en: str) -> AttractionItem:
    sh, sm = (int(x) for x in st.split(":"))
    eh, em = (int(x) for x in en.split(":"))
    dur = eh * 60 + em - (sh * 60 + sm)
    return AttractionItem(
        poi_id="t",
        name=name,
        start_time=st,
        end_time=en,
        duration_min=dur,
        description_short="d",
        lat=50.06,
        lng=19.94,
        address="a",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="p", walk_time_min=0),
    )


def test_fix271_ojcow_name_helper():
    assert _is_ojcow_stop_name("Jaskinia Łokietka")
    assert _is_ojcow_stop_name("Zamek w Ojcowie")
    assert not _is_ojcow_stop_name("Wawel")


def test_fix271_drop_crushed_pieskowa():
    svc = PlanService.__new__(PlanService)
    out = svc._drop_crushed_named_visits(
        [_attr("Zamek Pieskowa Skała", "20:27", "21:00")],
        {"target_group": "friends"},
        day_num=2,
    )
    assert out == []


def test_fix271_promote_late_family_zoo():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr("LEGO", "10:05", "11:47"),
        _attr("Ogród Zoologiczny", "15:01", "17:31"),
    ]
    items[1] = items[1].model_copy(update={"duration_min": 150})
    out = svc._promote_family_zoo(
        items,
        {"target_group": "family_kids"},
        {"day_start": "10:00", "day_end": "16:00"},
        day_num=1,
    )
    zoo = next(it for it in out if "zoo" in it.name.lower())
    assert zoo.start_time == "10:05"
    assert int(zoo.duration_min) >= 120
    assert zoo.end_time <= "16:00"


def test_fix271_strip_city_on_ojcow_day():
    svc = PlanService.__new__(PlanService)
    out = svc._strip_mixed_opn_krakow_attractions(
        [
            _attr("Muzeum Galicji", "10:00", "11:00"),
            _attr("Zamek w Ojcowie", "11:48", "13:03"),
            _attr("MOCAK", "17:00", "18:00"),
        ],
        None,
        6,
    )
    names = [it.name for it in out if hasattr(it, "name")]
    assert names == ["Zamek w Ojcowie"]
