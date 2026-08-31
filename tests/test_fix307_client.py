"""FIX #307 — Poznań leftover: first hops, Cytadela/Wilson, tickets, hours."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayStartItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TicketInfo,
    TransitItem,
    TransitMode,
)
from app.domain.scoring.profile_poi_rules import (
    poi_trip_repeat_key,
    should_deny_poi_for_profile,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.406, lng=16.925, tickets=None):
    kwargs = dict(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=lat,
        lng=lng,
        address="Poznań",
        city="Poznań",
        cost_estimate=0,
    )
    if tickets is not None:
        kwargs["ticket_info"] = tickets
    return AttractionItem.model_construct(**kwargs)


def _tr(frm, to, start, end, *, km, dur, mode=TransitMode.CAR, src="estimated_road"):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=mode,
        routing_source=src,
    )


def test_stare_zoo_gets_leading_hop_at_day_start():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Stare Zoo", "09:00", "10:00", 60, lat=52.4175, lng=16.9070),
    ]
    out = _svc()._ensure_leading_transit(
        items,
        {},
        {
            "requested_city": "Poznań",
            "has_car": True,
            "day_start": "09:00",
            "day_end": "19:00",
        },
        day_num=1,
    )
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "zoo" in (hops[0].to_location or "").lower()


def test_rusalka_seeded_leading_hop_without_coords():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION,
            poi_id="rusa",
            name="Jezioro Rusałka",
            description_short="",
            start_time="09:00",
            end_time="10:30",
            duration_min=90,
            lat=0,
            lng=0,
            address="Poznań",
            city="Poznań",
            cost_estimate=0,
        ),
    ]
    out = _svc()._ensure_leading_transit(
        items,
        {},
        {
            "requested_city": "Poznań",
            "has_car": True,
            "day_start": "09:00",
            "day_end": "19:00",
        },
        day_num=1,
    )
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "rusał" in (hops[0].to_location or "").lower() or "rusal" in (
        hops[0].to_location or ""
    ).lower()


def test_park_cytadela_unique_across_days():
    days = [
        SimpleNamespace(day=2, items=[
            _attr("Park Cytadela", "14:00", "15:30"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Park Cytadela", "11:00", "12:30"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("cytadela" in n.lower() for n in names) == 1
    assert poi_trip_repeat_key("Park Cytadela") == "poz_park_cytadela"


def test_park_wilsona_unique_across_days():
    days = [
        SimpleNamespace(day=2, items=[
            _attr("Park Wilsona", "15:00", "16:00"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Park Wilsona", "10:00", "11:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    names = [
        getattr(it, "name", "")
        for d in out for it in (d.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert sum("wilsona" in n.lower() for n in names) == 1


def test_okraglak_denied_for_family_with_8yo():
    poi = {"name": "Okrąglak", "city": "Poznań"}
    user = {"target_group": "family_kids", "children_age": 8, "preferences": []}
    assert should_deny_poi_for_profile(poi, user) is True


def test_wielkopolskie_museum_clipped_to_1600():
    items = [
        _attr(
            "Muzeum Powstania Wielkopolskiego",
            "15:00", "17:30", 150,
        ),
    ]
    out = _svc()._strip_after_hours_museums(
        items, day_num=1, trip_date="2026-06-01",
    )
    assert out
    assert out[0].end_time <= "16:00"


def test_zamek_reduced_ticket_capped_at_normal():
    tickets = TicketInfo.model_construct(ticket_normal=20, ticket_reduced=45)
    items = [
        _attr(
            "Zamek Królewski", "10:00", "11:30", 90,
            tickets=tickets,
        ),
    ]
    out = _svc()._sanitize_attraction_ticket_prices(items, day_num=1)
    info = out[0].ticket_info
    assert int(info.ticket_normal) == 20
    assert int(info.ticket_reduced) <= 20


def test_ghost_restaurant_hop_retargets_to_cytadela():
    items = [
        _attr("Muzeum Iluzji", "14:00", "15:00", 60),
        _tr("Muzeum Iluzji", "Restauracja Drevny Kocur", "15:00", "15:12", km=1.2, dur=12),
        _attr("Park Cytadela", "15:20", "16:50", 90, lat=52.4215, lng=16.9360),
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=2)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    assert "cytadela" in (hops[0].to_location or "").lower()


def test_lunch_context_follows_olio_hop():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:10",
        end_time="14:10",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="olio-1", name="Olio", lat=52.408, lng=16.933,
            )
        ],
        location_context="Zamek Królewski",
    )
    items = [
        _attr("Zamek Królewski", "11:00", "13:00", 120),
        _tr("Zamek Królewski", "Olio", "13:00", "13:10", km=0.6, dur=10,
            mode=TransitMode.WALK, src="estimated_walk"),
        lunch,
    ]
    out = _svc()._reset_stale_meal_location_context(items, day_num=3)
    meal = next(it for it in out if it.type == ItemType.LUNCH_BREAK)
    ctx = (getattr(meal, "location_context", "") or "").lower()
    assert "zamek" not in ctx
    assert "olio" in ctx


def test_haversine_short_walk_becomes_estimated_walk():
    items = [
        _tr(
            "Fotoplastykon", "Antrejka",
            "12:00", "12:06", km=0.285, dur=6,
            mode=TransitMode.WALK, src="haversine",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=6, context={"has_car": True})
    assert "walk" in str(out[0].routing_source or "").lower()
    assert "haversine" not in str(out[0].routing_source or "").lower()


def test_honest_19km_walk_untouched():
    items = [
        _tr(
            "Stary Rynek", "Park Wilsona",
            "15:00", "15:28", km=1.90, dur=28,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=1, context={"has_car": True})
    assert out[0].mode == TransitMode.WALK
    assert int(out[0].duration_min) == 28


def test_rogalin_to_lednica_gets_a_drive():
    items = [
        _attr(
            "Muzeum Pałacu w Rogalinie", "09:30", "11:00", 90,
            lat=52.2444, lng=16.9000,
        ),
        _attr(
            "Ostrów Lednicki", "12:00", "14:00", 120,
            lat=52.5269, lng=17.3756,
        ),
    ]
    out = _svc()._ensure_city_to_far_after_meal(
        items, {}, {"requested_city": "Poznań", "has_car": True}, day_num=5,
    )
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert hops
    dest = (hops[0].to_location or "").lower()
    assert "lednick" in dest


def test_return_to_car_then_wilsona_gets_a_hop():
    items = [
        _attr("Muzeum Armii Poznań", "11:00", "12:00", 60, lat=52.421, lng=16.933),
        _tr(
            "Park Szelągowski", "Muzeum Armii Poznań",
            "13:00", "13:10", km=1.1, dur=10,
            src="return_to_car",
        ),
        _attr("Park Wilsona", "13:20", "14:20", 60, lat=52.4005, lng=16.9120),
    ]
    out = _svc()._ensure_stop_to_stop_legs(
        items, {}, {"requested_city": "Poznań", "has_car": True}, day_num=2,
    )
    hops = [
        it for it in out
        if getattr(it, "type", None) == ItemType.TRANSIT
        and str(getattr(it, "routing_source", "") or "") != "return_to_car"
    ]
    assert any("wilsona" in (it.to_location or "").lower() for it in hops)


def test_182min_ft_before_dinner_is_eaten():
    dinner = DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time="19:00",
        end_time="20:00",
        duration_min=60,
        suggestions=[],
    )
    items = [
        _attr("Stary Rynek", "14:00", "15:58", 118),
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="15:58",
            end_time="19:00",
            duration_min=182,
            label="Czas dla siebie",
            suggestions=[],
        ),
        dinner,
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=1)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 45


def test_day_clamped_to_user_window():
    items = [
        _attr("Termy Maltańskie", "18:30", "20:13", 103, lat=52.4018, lng=16.9780),
    ]
    out = _svc()._clamp_timeline_to_day_end(
        items, {"day_end": "19:00"}, day_num=1,
    )
    assert out
    assert out[0].end_time <= "19:00"


def test_30min_hole_is_named():
    items = [
        _attr("Park Adama Wodziczki", "17:00", "18:22", 82, lat=52.430, lng=16.890),
        _attr("Stary Rynek", "18:52", "19:30", 38),
    ]
    out = _svc()._name_remaining_holes(
        items, {"day_start": "09:00", "day_end": "20:00"}, day_num=5,
    )
    named = [
        it for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
    ]
    assert named
