"""FIX #304 — Wrocław leftover: honest transits + 5-day icon uniqueness."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=51.11, lng=17.03):
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
        address="Wrocław",
        city="Wrocław",
        cost_estimate=0,
    )


def _tr(frm, to, start, end, *, km, dur, mode=TransitMode.WALK, src="estimated_road"):
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


def test_073km_walk_is_not_2_min():
    items = [
        _tr(
            "Wyspa Słodowa", "Dom Krasnali",
            "12:00", "12:02", km=0.726, dur=2,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=2, context={"has_car": True})
    assert int(out[0].duration_min) >= 10
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode


def test_5465km_walk_becomes_car():
    items = [
        _tr(
            "GoJump", "Movie Gate",
            "10:00", "10:10", km=5.465, dur=10,
            mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=1, context={"has_car": True})
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" not in mode
    src = str(out[0].routing_source or "").lower()
    assert "walk" not in src


def test_48km_3min_walk_becomes_honest_car():
    items = [
        _tr(
            "Browar Stu Mostów", "Konspira",
            "18:00", "18:03", km=4.8, dur=3,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=3, context={"has_car": True})
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" not in mode
    assert int(out[0].duration_min) >= 10


def test_1888km_walk_keeps_walk_but_honest_time():
    items = [
        _tr(
            "IDA", "Muzeum Narodowe",
            "14:00", "14:10", km=1.888, dur=10,
            mode=TransitMode.WALK, src="estimated_road",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=3, context={"has_car": True})
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode
    assert int(out[0].duration_min) >= 20
    assert "walk" in str(out[0].routing_source or "").lower()


def test_honest_19km_walk_untouched():
    items = [
        _tr(
            "Taste", "Hydropolis",
            "12:46", "13:22", km=1.9, dur=36,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._honest_transit_physics(items, day_num=1, context={"has_car": True})
    mode = str(getattr(out[0].mode, "value", out[0].mode) or "").lower()
    assert "walk" in mode
    assert int(out[0].duration_min) == 36


def test_sanitize_expands_too_short_micro_walk():
    items = [
        _tr(
            "Wyspa Słodowa", "Dom Krasnali",
            "12:00", "12:02", km=0.726, dur=2,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._sanitize_walk_leg_durations(
        items, {}, day_num=2, context={"has_car": True},
    )
    assert int(out[0].duration_min) >= 8


def test_snap_closes_24min_gap_after_wyspa():
    items = [
        _attr("Wyspa Słodowa", "17:58", "18:58", 60),
        _tr(
            "Wyspa Słodowa", "Kolacja",
            "19:22", "19:40", km=1.2, dur=18,
            mode=TransitMode.WALK, src="estimated_walk",
        ),
    ]
    out = _svc()._snap_transits_to_previous_stop_end(items, day_num=2)
    hop = next(it for it in out if it.type == ItemType.TRANSIT)
    assert hop.start_time == "18:58"


def test_ghost_hala_to_skytower_retargets_to_forum_lunch():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:40",
        end_time="14:40",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="forum", name="Forum Kulinarne", lat=51.11, lng=17.03,
                city="Wrocław",
            )
        ],
    )
    items = [
        _attr("Hala Stulecia", "12:30", "13:30", 60, lat=51.107, lng=17.077),
        _tr("Hala Stulecia", "Punkt Widokowy Sky Tower", "13:30", "13:40", km=2.0, dur=10),
        lunch,
    ]
    out = _svc()._retarget_all_legs_to_next_stop(items, day_num=4)
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    assert hops
    assert "forum" in (hops[0].to_location or "").lower()


def test_hop_after_forum_does_not_restart_from_skytower():
    lunch = LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time="13:40",
        end_time="14:40",
        duration_min=60,
        suggestions=[
            RestaurantSuggestion.model_construct(
                id="forum", name="Forum Kulinarne", lat=51.11, lng=17.03,
                city="Wrocław",
            )
        ],
    )
    items = [
        _attr("Punkt Widokowy Sky Tower", "12:30", "13:20", 50),
        _tr("Sky Tower", "Forum Kulinarne", "13:20", "13:40", km=2.0, dur=20),
        lunch,
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="14:40",
            end_time="15:38",
            duration_min=58,
            label="Czas dla siebie",
            suggestions=[],
        ),
        _tr(
            "Sky Tower", "Muzeum Pana Tadeusza",
            "15:38", "16:01", km=2.759, dur=23,
        ),
        _attr("Muzeum Pana Tadeusza", "16:01", "17:00", 59),
    ]
    out = _svc()._retarget_all_legs_to_prev_stop(items, day_num=4, context={})
    hops = [it for it in out if it.type == ItemType.TRANSIT]
    last = hops[-1]
    assert "forum" in (last.from_location or "").lower()


def test_five_day_wroclaw_icons_are_unique():
    days = [
        SimpleNamespace(day=1, items=[
            _attr("Pergola przy Hali Stulecia", "10:00", "11:00"),
            _attr("Ogród Japoński", "11:30", "12:30"),
        ]),
        SimpleNamespace(day=3, items=[
            _attr("Pergola", "10:00", "11:00"),
            _attr("Ogród Japoński we Wrocławiu", "11:30", "12:30"),
            _attr("Muzeum Świat Iluzji", "13:00", "14:00"),
            _attr("Hala Stulecia", "14:30", "15:30"),
        ]),
        SimpleNamespace(day=4, items=[
            _attr("Hala Stulecia", "10:00", "11:00"),
        ]),
        SimpleNamespace(day=5, items=[
            _attr("Muzeum Świat Iluzji", "15:00", "16:00"),
        ]),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)

    def _names(day):
        return [
            (getattr(it, "name", "") or "").lower()
            for it in (day.items or [])
            if it.type == ItemType.ATTRACTION
        ]

    all_names = [n for d in out for n in _names(d)]
    assert sum("pergola" in n for n in all_names) == 1
    assert sum("japoń" in n or "japon" in n for n in all_names) == 1
    assert sum("iluzj" in n for n in all_names) == 1
    assert sum("hala stulecia" in n and "pergola" not in n for n in all_names) <= 1


def test_eat_130min_free_time_before_next_attraction():
    items = [
        _attr("Panorama Racławicka", "10:57", "11:57", 60),
        FreeTimeItem(
            type=ItemType.FREE_TIME,
            start_time="11:57",
            end_time="14:07",
            duration_min=130,
            label="Czas dla siebie",
            suggestions=[],
        ),
        _attr("Hydropolis", "14:07", "15:30", 83),
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=3)
    fts = [it for it in out if it.type == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 25
