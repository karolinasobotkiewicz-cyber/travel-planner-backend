"""FIX #278 — Wrocław json8: early day_end, real day-trips, winter free_time copy."""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _city_genitive,
    _early_close_note,
    _is_winter_plan_context,
    _quality_first_trip,
    _snap_day_end_up,
    _strip_trailing_free_time,
)
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    FreeTimeItem,
    ItemType,
)
from app.domain.planner.engine import should_skip_poi_candidate


def _attr(name: str, start: str, end: str, dur: int, *, lat=51.11, lng=17.03):
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
        address="",
        cost_estimate=0,
    )


def _ft(start: str, end: str, dur: int) -> FreeTimeItem:
    return FreeTimeItem(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label="Czas wolny",
        suggestions=["Przerwa na lody lub zimne napoje"],
    )


def test_fix278_snap_and_winter_context():
    assert _snap_day_end_up(14 * 60 + 5) == 14 * 60 + 30
    assert _snap_day_end_up(16 * 60 + 1) == 16 * 60 + 30
    assert _is_winter_plan_context({"season": "winter"})
    assert _is_winter_plan_context({"start_date": "2026-02-20"})
    assert not _is_winter_plan_context({"season": "summer"})
    assert _quality_first_trip({"num_days": 7})


def test_fix278_early_close_drops_multi_hour_free_time():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr("Rynek we Wrocławiu", "09:38", "11:38", 120),
        _attr("Wyspa Słodowa", "12:50", "14:05", 75),
        _ft("14:05", "14:50", 45),
        _ft("14:50", "16:50", 120),
        _ft("16:50", "20:00", 190),
        DayEndItem(time="20:00"),
    ]
    out, note, day_end = svc._apply_quality_first_early_close(
        items, {"num_days": 7, "day_end": "20:00", "requested_city": "Wrocław"},
        day_num=1,
    )
    assert day_end == "14:30"
    assert note and "spokojniej" in note.lower()
    ft = [
        it for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
    ]
    assert sum(int(it.duration_min or 0) for it in ft) <= 15
    ends = [it for it in out if getattr(it, "type", None) == ItemType.DAY_END]
    assert ends and ends[0].time == "14:30"


def test_fix278_close_tail_skipped_on_long_trip_afternoon():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr("Aquapark", "10:00", "12:00", 120),
        _attr("Muzeum", "13:00", "14:12", 72),
        _ft("14:12", "20:00", 348),
    ]
    out = svc._close_day_end_tail(
        items, {"num_days": 7, "day_end": "20:00"}, day_num=3,
    )
    ft = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert ft and int(ft[0].duration_min) == 348


def test_fix278_winter_afternoon_copy():
    assert any(
        "lody" in " ".join(sugs).lower()
        for _label, sugs in PlanService._FT253_AFTERNOON
    ) is False
    winter = " ".join(
        " ".join(sugs) for _label, sugs in PlanService._FT253_AFTERNOON_WINTER
    ).lower()
    assert "lody" not in winter
    assert "koc" not in winter


def test_fix278_baszta_not_skipped_as_micro_stop():
    ctx = {
        "num_days": 7,
        "city_centroid": (51.11, 17.03),
    }
    poi = {
        "name": "Baszta Miejska w Niemczy",
        "city": "Niemcza",
        "lat": 50.72,
        "lng": 16.83,
        "time_max": 30,
        "time_min": 15,
    }
    assert not should_skip_poi_candidate(poi, ctx)


def test_fix278_return_added_instead_of_strip():
    svc = PlanService.__new__(PlanService)
    items = [
        _attr(
            "Laboratorium dr. Frankensteina",
            "11:00", "11:40", 40,
            lat=50.589, lng=16.81,
        ),
        _ft("11:40", "20:00", 500),
    ]
    out = svc._strip_far_last_excursion(
        items,
        {"requested_city": "Wrocław", "day_end": "20:00"},
        day_num=7,
    )
    names = [getattr(it, "name", "") for it in out if _attr_name(it)]
    assert any("Frankenstein" in (n or "") for n in names)
    trans = [
        it for it in out
        if str(getattr(getattr(it, "type", None), "value", it.type)).lower()
        == "transit"
    ]
    assert trans
    assert "wrocław" in (getattr(trans[-1], "to_location", "") or "").lower()


def _attr_name(it) -> str:
    return getattr(it, "name", "") or ""


def test_fix278_early_close_note_day5():
    note = _early_close_note(
        [_attr("Hala", "10:00", "12:00", 120)],
        day_num=5, num_days=7, city="Wrocław",
    )
    assert "wcześniej" in note.lower() or "wczesniej" in note.lower()


def test_fix280_day1_note_uses_city_genitive():
    """Client-facing: 'odkrywanie Wrocławia', never nominative 'Wrocław'."""
    assert _city_genitive("Wrocław") == "Wrocławia"
    assert _city_genitive("Kraków") == "Krakowa"
    note = _early_close_note(
        [_attr("Rynek we Wrocławiu", "09:00", "11:00", 120)],
        day_num=1, num_days=7, city="Wrocław",
    )
    assert "Wrocławia" in note
    assert "odkrywanie Wrocław." not in note


def test_fix278_trailing_strip_helper():
    items = [
        _attr("A", "09:00", "14:00", 300),
        _ft("14:00", "20:00", 360),
    ]
    out = _strip_trailing_free_time(items, max_min=12)
    assert not any(getattr(it, "type", None) == ItemType.FREE_TIME for it in out)
