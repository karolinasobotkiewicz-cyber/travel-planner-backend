"""FIX #368: P5 scrub hops after profile drop; P4 refuse insane legs; leading/idle."""
from __future__ import annotations


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_p5_scrubs_hops_to_dropped_profile_ban():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
        TransitItem, TransitMode, LunchBreakItem, RestaurantSuggestion,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:15",
            duration_min=15, from_location="Katowice",
            to_location="Pijalnia Czekolady E.Wedel",
            mode=TransitMode.WALK, distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w",
            name="Pijalnia Czekolady E.Wedel",
            description_short="x", why_selected=["x"],
            start_time="09:15", end_time="10:00", duration_min=45,
            lat=52.2297, lng=21.0122, city="Warszawa",
            cost_estimate=30,
            target_groups=["solo", "family_kids", "couples"],
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:00", end_time="10:15",
            duration_min=15, from_location="Pijalnia Czekolady E.Wedel",
            to_location="Kato Pizza - Pizzeria w stylu Detroit",
            mode=TransitMode.WALK, distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="p",
            name="Kato Pizza - Pizzeria w stylu Detroit",
            description_short="x", why_selected=["x"],
            start_time="10:15", end_time="11:00", duration_min=45,
            lat=50.264, lng=19.023, city="Katowice", cost_estimate=40,
            target_groups=["friends", "couples", "solo"],
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="12:00", end_time="12:40",
            duration_min=40, label="Kato Pizza - Pizzeria w stylu Detroit",
            suggestions=[RestaurantSuggestion.model_construct(
                name="Kato Pizza - Pizzeria w stylu Detroit",
                lat=50.264, lng=19.023,
            )],
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Katowice", "has_car": True, "day_end": "19:00",
        "group_type": "friends", "travel_style": "balanced",
        "preferences": ["history_mystery"],
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=2)
    names = [getattr(it, "name", "") or "" for it in out if _tv(it) == "attraction"]
    assert not any("wedel" in n.lower() for n in names), names
    for it in out:
        if _tv(it) != "transit":
            continue
        frm = (getattr(it, "from_location", "") or "").lower()
        to = (getattr(it, "to_location", "") or "").lower()
        assert "wedel" not in frm and "wedel" not in to, (frm, to)
        km = float(getattr(it, "distance_km", 0) or 0)
        assert km < 80.0, km


def test_p4_drops_insane_cross_city_leg():
    from app.domain.models.plan import (
        DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
        AttractionItem,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Spodek",
            description_short="x", why_selected=["x"],
            start_time="09:30", end_time="10:30", duration_min=60,
            lat=50.266, lng=19.027, city="Katowice", cost_estimate=0,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="10:30", end_time="10:45",
            duration_min=15, from_location="Spodek",
            to_location="Pijalnia Czekolady E.Wedel",
            mode=TransitMode.CAR, distance_km=0.9,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w",
            name="Pijalnia Czekolady E.Wedel",
            description_short="x", why_selected=["x"],
            start_time="10:45", end_time="11:30", duration_min=45,
            lat=52.2297, lng=21.0122, city="Warszawa", cost_estimate=30,
            target_groups=["friends", "couples", "solo"],
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Katowice", "has_car": True, "day_end": "19:00",
        "group_type": "friends",
    }
    out = svc._seal_fix368_p4_recompute_legs(items, ctx, day_num=1)
    for it in out:
        if _tv(it) != "transit":
            continue
        km = float(getattr(it, "distance_km", 0) or 0)
        assert km < 80.0, (
            getattr(it, "from_location", None),
            getattr(it, "to_location", None),
            km,
        )


def test_leading_hub_hop_inserted_for_first_stop():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, FreeTimeItem,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME, start_time="09:00", end_time="09:25",
            duration_min=25, label="bufor",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="g", name="Giszowiec",
            description_short="x", why_selected=["x"],
            start_time="09:25", end_time="10:25", duration_min=60,
            lat=50.223, lng=19.069, city="Katowice", cost_estimate=0,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Katowice", "has_car": True, "day_end": "19:00",
        "day_start": "09:00", "group_type": "friends",
    }
    out = svc._seal_fix367_uat_day(items, ctx, day_num=2)
    # Should have a hop to Giszowiec and no idle morning free_time
    hops_to = [
        (getattr(it, "from_location", ""), getattr(it, "to_location", ""))
        for it in out if _tv(it) == "transit"
    ]
    assert any("giszowiec" in (t or "").lower() for _, t in hops_to), hops_to
    for it in out:
        if _tv(it) != "free_time":
            continue
        st = getattr(it, "start_time", "") or ""
        assert st >= "09:20" or st == "", st


def test_scrub_keeps_city_hop_when_dropped_poi_contains_city():
    """'Pixel XL Katowice' dropped must not scrub 'Katowice' -> Zoo."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
        TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:20",
            duration_min=20, from_location="Katowice",
            to_location="Slaski Ogrod Zoologiczny",
            mode=TransitMode.CAR, distance_km=6.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="z", name="Slaski Ogrod Zoologiczny",
            description_short="x", why_selected=["x"],
            start_time="09:20", end_time="11:20", duration_min=120,
            lat=50.287, lng=18.995, city="Chorzow", cost_estimate=30,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="x", name="Pixel XL Katowice",
            description_short="x", why_selected=["x"],
            start_time="11:20", end_time="12:20", duration_min=60,
            lat=50.26, lng=19.02, city="Katowice", cost_estimate=60,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {
        "requested_city": "Katowice", "has_car": True, "day_end": "19:00",
        "group_type": "seniors", "travel_style": "relax",
        "preferences": ["relaxation"],
    }
    out = svc._seal_fix368_p5_profile_dedupe_cost(items, ctx, day_num=1)
    hops = [
        (getattr(it, "from_location", ""), getattr(it, "to_location", ""))
        for it in out if _tv(it) == "transit"
    ]
    assert ("Katowice", "Slaski Ogrod Zoologiczny") in hops, hops


def _ft(st, en):
    from app.domain.models.plan import FreeTimeItem, ItemType
    return FreeTimeItem(
        type=ItemType.FREE_TIME, start_time=st, end_time=en,
        duration_min=0, label="Czas dla siebie",
    )


def test_katowice_tail_gap_pulls_dinner_within_rules():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, DinnerBreakItem, ItemType,
        LunchBreakItem, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="12:00", end_time="12:40",
            duration_min=40, label="Lunch",
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="n", name="Nikiszowiec",
            description_short="x", why_selected=["x"],
            start_time="15:00", end_time="16:20", duration_min=80,
            lat=50.24, lng=19.08, city="Katowice", cost_estimate=0,
        ),
        _ft("16:20", "17:20"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="18:30", end_time="18:40",
            duration_min=10, from_location="Nikiszowiec",
            to_location="Stara Ponderosa", mode=TransitMode.CAR, distance_km=4.0,
        ),
        DinnerBreakItem.model_construct(
            type=ItemType.DINNER_BREAK, start_time="18:40", end_time="19:00",
            duration_min=20, label="Stara Ponderosa",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Katowice", "day_start": "09:00", "day_end": "19:00"}
    out = svc._seal_fix368_katowice_tail_gaps(items, ctx, day_num=1)
    tr = [it for it in out if _tv(it) == "transit"][0]
    din = [it for it in out if _tv(it) == "dinner_break"][0]
    assert tr.start_time == "17:20", tr.start_time
    assert din.start_time >= "17:00"
    assert din.start_time <= "17:40", din.start_time
    from app.domain.planner.time_utils import time_to_minutes as tm
    assert tm(din.end_time) - tm(din.start_time) >= 30


def test_katowice_inbound_glue_at_day_start():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType,
        TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="08:50"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="09:00", end_time="09:14",
            duration_min=14, from_location="Katowice", to_location="JUMPCITY",
            mode=TransitMode.CAR, distance_km=6.0,
        ),
        _ft("09:14", "10:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="j", name="JUMPCITY",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:30", duration_min=90,
            lat=50.25, lng=19.0, city="Katowice", cost_estimate=40,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Katowice", "day_start": "09:00", "day_end": "19:00"}
    out = svc._seal_fix368_katowice_tail_gaps(items, ctx, day_num=3)
    tr = [it for it in out if _tv(it) == "transit"][0]
    from app.domain.planner.time_utils import time_to_minutes as tm
    assert 600 - tm(tr.end_time) < 45
    assert tm(tr.start_time) - 540 < 40
    assert not [it for it in out if _tv(it) == "free_time"]


def test_tail_gap_seal_is_katowice_only():
    from app.domain.models.plan import DayEndItem, DayStartItem

    svc = _svc()
    items = [DayStartItem(time="09:00"), _ft("10:00", "11:00"), DayEndItem(time="19:00")]
    ctx = {"requested_city": "Krakow", "day_start": "09:00", "day_end": "19:00"}
    assert svc._seal_fix368_katowice_tail_gaps(items, ctx, day_num=1) is items


def test_poznan_final_from_anchor_drops_ghost_and_reanchors_walk():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, LunchBreakItem,
        RestaurantSuggestion, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="10:00"),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:52", end_time="14:01",
            duration_min=9, from_location="Pomnik Ofiar Czerwca 1956",
            to_location="La Farina Italiana", mode=TransitMode.CAR, distance_km=3.3,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="14:01", end_time="14:21",
            duration_min=20, from_location="La Farina Italiana",
            to_location="Park Cytadela", mode=TransitMode.WALK, distance_km=0.8,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="14:21", end_time="15:04",
            duration_min=43, label="La Farina Italiana",
            suggestions=[RestaurantSuggestion.model_construct(
                name="La Farina Italiana", lat=52.41, lng=16.93,
            )],
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="15:32", end_time="15:59",
            duration_min=27, from_location="Park Cytadela",
            to_location="Wartostrada", mode=TransitMode.WALK, distance_km=1.9,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w", name="Wartostrada",
            description_short="x", why_selected=["x"],
            start_time="15:59", end_time="16:44", duration_min=45,
            lat=52.40, lng=16.94, city="Poznan", cost_estimate=0,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Poznań", "day_start": "10:00", "day_end": "18:00"}
    out = svc._seal_fix368_final_from_anchor(items, ctx, day_num=2)
    hops = [
        (getattr(it, "from_location", ""), getattr(it, "to_location", ""))
        for it in out if _tv(it) == "transit"
    ]
    assert ("La Farina Italiana", "Park Cytadela") not in hops, hops
    assert ("La Farina Italiana", "Wartostrada") in hops, hops


def test_final_from_anchor_not_applied_to_krakow():
    from app.domain.models.plan import DayEndItem, DayStartItem

    svc = _svc()
    items = [DayStartItem(time="09:00"), DayEndItem(time="19:00")]
    ctx = {"requested_city": "Krakow"}
    assert svc._seal_fix368_final_from_anchor(items, ctx, day_num=1) is items


def test_poznan_meal_anchor_follows_label_not_area_tag():
    """J10 D2: lunch labelled 'La Farina Italiana' but tagged 'Park Cytadela'."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, LunchBreakItem,
        TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:45"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Park Szelągowski",
            description_short="x", why_selected=["x"],
            start_time="12:30", end_time="13:10", duration_min=40,
            lat=52.425, lng=16.955, city="Poznan", cost_estimate=0,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="13:42", end_time="14:01",
            duration_min=19, from_location="Park Szelągowski",
            to_location="La Farina Italiana", mode=TransitMode.CAR, distance_km=3.0,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="14:01", end_time="14:21",
            duration_min=20, from_location="La Farina Italiana",
            to_location="Park Cytadela", mode=TransitMode.WALK, distance_km=0.8,
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="14:21", end_time="15:04",
            duration_min=43, label="La Farina Italiana", suggestions=[],
            location_context="Park Cytadela",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="15:32", end_time="15:59",
            duration_min=27, from_location="Park Cytadela",
            to_location="Wartostrada", mode=TransitMode.WALK, distance_km=1.9,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="w", name="Wartostrada",
            description_short="x", why_selected=["x"],
            start_time="15:59", end_time="16:44", duration_min=45,
            lat=52.40, lng=16.94, city="Poznan", cost_estimate=0,
        ),
        DayEndItem(time="18:00"),
    ]
    ctx = {"requested_city": "Poznań", "day_start": "09:45", "day_end": "18:00"}
    out = svc._seal_fix368_final_from_anchor(items, ctx, day_num=2)
    hops = [
        (getattr(it, "from_location", ""), getattr(it, "to_location", ""))
        for it in out if _tv(it) == "transit"
    ]
    assert ("La Farina Italiana", "Park Cytadela") not in hops, hops
    assert ("La Farina Italiana", "Wartostrada") in hops, hops
    assert all(f != "Park Cytadela" for f, _ in hops), hops
    lunch = [it for it in out if _tv(it) == "lunch_break"][0]
    assert lunch.location_context == "La Farina Italiana"
    # Validator view: every transit starts where people last stopped.
    from app.domain.validators import client_invariants as ci
    prev = None
    for it in sorted(
        (x for x in out if getattr(x, "start_time", None)),
        key=lambda x: x.start_time,
    ):
        if _tv(it) == "transit":
            if prev:
                assert ci._names_match(it.from_location, prev), (it.from_location, prev)
        elif ci._stop_name(it):
            prev = ci._stop_name(it)
