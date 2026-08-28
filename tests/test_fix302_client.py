"""FIX #302 — Wrocław leftover: ghost hops, parking seed, Mamuta, combat pair."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _place_names_match,
)
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03, city="Wrocław"):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=lat,
        lng=lng,
        address=city,
        city=city,
        cost_estimate=0,
    )


def _tr(
    frm, to, start, end, *, km, dur,
    mode=TransitMode.CAR, src="estimated_road",
):
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


def test_pergola_matches_full_hala_name():
    assert _place_names_match("Pergola", "Pergola przy Hali Stulecia")


def test_return_to_car_to_aula_does_not_block_hop_to_pergola():
    items = [
        _attr("Wyspa Słodowa", "12:00", "13:00", 60, lat=51.116, lng=17.038),
        _tr(
            "Wyspa Słodowa", "Aula Leopoldina",
            "13:00", "13:15", km=0.6, dur=15,
            mode=TransitMode.WALK, src="return_to_car",
        ),
        _attr(
            "Pergola przy Hali Stulecia", "13:15", "14:00", 45,
            lat=51.107, lng=17.077,
        ),
    ]
    out = _svc()._ensure_stop_to_stop_legs(
        items, {}, {"has_car": True, "requested_city": "Wrocław"}, day_num=2,
    )
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert any("pergola" in (h.to_location or "").lower() for h in hops)


def test_ghost_opening_walk_does_not_park_car_at_aula():
    items = [
        _tr(
            "Aula Leopoldina", "Wyspa Słodowa",
            "09:00", "09:12", km=0.8, dur=12,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
        _attr("Wyspa Słodowa", "09:12", "11:00", 108, lat=51.116, lng=17.038),
        _tr(
            "Wyspa Słodowa", "Hala Stulecia",
            "11:00", "11:20", km=4.2, dur=20,
        ),
        _attr("Hala Stulecia", "11:20", "12:20", 60, lat=51.107, lng=17.077),
    ]
    coords = {
        "Wyspa Słodowa": {"lat": 51.116, "lng": 17.038},
        "Hala Stulecia": {"lat": 51.107, "lng": 17.077},
    }
    out = _svc()._enforce_car_parking_logistics(
        items, coords, {"has_car": True, "requested_city": "Wrocław"}, day_num=2,
    )
    tos = " ".join(
        str(getattr(it, "to_location", "") or "")
        for it in out if it.type == ItemType.TRANSIT
    ).lower()
    assert "aula" not in tos


def test_vaffanapoli_self_leg_is_stripped():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:00",
        end_time="14:00",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="v", name="VaffaNapoli", lat=51.11, lng=17.03, city="Wrocław",
            )
        ],
    )
    items = [
        lunch,
        _tr("VaffaNapoli", "VaffaNapoli", "14:00", "14:10", km=0, dur=10),
        _attr("Hydropolis", "14:20", "15:20", 60, lat=51.104, lng=17.057),
    ]
    out = _svc()._strip_self_transits(items, day_num=2)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops == []


def test_park_mamuta_floor_is_45():
    items = [_attr("Park Mamuta", "15:00", "15:20", 20, lat=51.09, lng=17.02)]
    out = _svc()._cap_stretched_attraction_durations(
        items, day_num=1,
        user={"target_group": "family_kids", "travel_style": "balanced"},
    )
    assert int(out[0].duration_min) >= 45


def test_second_combat_same_day_is_stripped():
    items = [
        _attr("CityPaintball", "10:00", "11:30", 90, lat=51.08, lng=17.01),
        _attr("Laser Tag", "12:00", "13:00", 60, lat=51.09, lng=17.02),
        _attr("Hydropolis", "14:00", "15:30", 90, lat=51.104, lng=17.057),
    ]
    out = _svc()._strip_second_combat_same_day(items, day_num=1)
    names = [it.name.lower() for it in out if _is_attr(it)]
    assert any("paintball" in n for n in names)
    assert not any("laser" in n for n in names)


def test_przyrodnicze_twice_same_day_is_stripped():
    items = [
        _attr("Muzeum Przyrodnicze", "10:00", "11:30", 90, lat=51.11, lng=17.05),
        _attr(
            "Muzeum Przyrodnicze Uniwersytetu Wrocławskiego",
            "14:00", "15:00", 60, lat=51.11, lng=17.05,
        ),
    ]
    out = _svc()._strip_same_day_duplicate_attractions(items, day_num=1)
    attrs = [it for it in out if _is_attr(it)]
    assert len(attrs) == 1


def test_long_walk_with_road_source_becomes_car():
    items = [
        _tr(
            "GoJump", "Pod przykrywką",
            "10:00", "10:11", km=4.916, dur=11,
            mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._normalize_transit_mode_source(items, day_num=1)
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" not in mode
    assert out[0].routing_source == "estimated_road"


def test_honest_city_walk_stays_walk_in_normalize():
    items = [
        _tr(
            "Taste", "Hydropolis",
            "12:46", "13:22", km=1.9, dur=36,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._normalize_transit_mode_source(items, day_num=1)
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode
    assert out[0].duration_min == 36


def test_transit_cannot_start_during_pergola():
    items = [
        _attr("Pergola przy Hali Stulecia", "13:27", "14:02", 35, lat=51.107, lng=17.077),
        _tr("Pergola", "Warzywniak", "13:51", "14:05", km=1.2, dur=14, mode=TransitMode.WALK),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=1)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops[0].start_time >= "14:02"


def _is_attr(it) -> bool:
    return getattr(it, "type", None) == ItemType.ATTRACTION
