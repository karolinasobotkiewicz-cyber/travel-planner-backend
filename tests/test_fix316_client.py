"""FIX #316 — winter Wojsławice, day_end chronology, stacked / mid-day FT.

Client Wrocław 7-day follow-up:
  D7 Arboretum Wojsławice 09:00–10:01 overlaps Wrocław → Ząbkowice 09:00–10:32
  and must not be a February visit.
  D7 day_end 14:43 with free_time 14:55–15:14 (activity after the day ended).
  D4 15:30–16:20 unnamed before day_end 16:20.
  D4 69 min Czas dla siebie after lunch (90-min rule is not enough).
  D6 35 min buffer + 90 min FT stacked before lunch.
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayPlan,
    DayStartItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    TransitItem,
    TransitMode,
)


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=50.7250, lng=16.8520):
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
        address="Wojsławice",
        city="Niemcza",
        cost_estimate=0,
    )


def _tr(frm, to, start, end, *, km=50.0, dur=92, mode=TransitMode.CAR):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=mode,
        routing_source="estimated_road",
    )


def _ft(start, end, dur, label="Czas dla siebie"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def _lunch(start, end, dur=45):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start,
        end_time=end,
        duration_min=dur,
        suggestions=[],
        location_context="centrum",
    )


def _ctx(**extra):
    base = {
        "requested_city": "Wrocław",
        "has_car": True,
        "day_start": "09:00",
        "day_end": "19:00",
        "start_date": "2026-02-20",
        "date": "2026-02-26",
        "season": "winter",
    }
    base.update(extra)
    return base


def test_wojslawice_is_stripped_in_february_even_without_arboretum_prefix():
    items = [_attr("Wojsławice", "09:00", "10:01", 61)]
    out = _svc()._strip_winter_closed_attractions(items, "2026-02-26", day_num=7)
    assert not [
        it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION
    ]


def test_d7_wojslawice_does_not_overlap_zabkowice_drive():
    days = [
        DayPlan(
            day=7, title="D7",
            items=[
                DayStartItem(type=ItemType.DAY_START, time="09:00"),
                _attr("Arboretum Wojsławice", "09:00", "10:01", 61),
                _tr("Wrocław", "Zamek w Ząbkowicach Śląskich", "09:00", "10:32"),
                _attr(
                    "Zamek w Ząbkowicach Śląskich", "10:32", "12:00", 88,
                    lat=50.5890, lng=16.8100,
                ),
                DayEndItem(time="16:00"),
            ],
        ),
    ]
    out = _svc()._guard_trip_invariants(days, _ctx(), coord_map={}, user={})
    d7 = out[0]
    names = [
        (getattr(it, "name", "") or "").lower()
        for it in (d7.items or [])
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert not any("wojsław" in n or "wojslaw" in n for n in names)
    castle_kept = any("ząbkow" in n or "zabkow" in n for n in names)
    hops = [
        it for it in (d7.items or [])
        if getattr(it, "type", None) == ItemType.TRANSIT
    ]
    # FIX #322: lonely castle after ≥35 km / ≥35 min is thin — hops only
    # if the excursion itself survived cluster-or-drop.
    if castle_kept:
        assert hops
    timed = []
    for it in d7.items:
        st = getattr(it, "start_time", None) or getattr(it, "time", None)
        en = getattr(it, "end_time", None)
        if not st or not en:
            continue
        if getattr(it, "type", None) in (ItemType.DAY_START, ItemType.DAY_END):
            continue
        timed.append((st, en, getattr(it, "type", None)))
    for i, (a_st, a_en, _) in enumerate(timed):
        for b_st, b_en, _ in timed[i + 1:]:
            assert a_en <= b_st or b_en <= a_st, (
                f"overlap {a_st}-{a_en} vs {b_st}-{b_en}"
            )


def test_free_time_after_day_end_is_dropped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Zamek w Ząbkowicach Śląskich", "10:32", "14:30", 238,
              lat=50.5890, lng=16.8100),
        DayEndItem(time="14:43"),
        _ft("14:55", "15:14", 19),
    ]
    out = _svc()._drop_items_after_day_end(items, day_num=7)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert not fts


def test_gap_before_day_end_marker_is_named():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Wystawa Pająków", "14:30", "15:30", 60, lat=51.094, lng=17.021),
        DayEndItem(time="16:20"),
    ]
    out = _svc()._name_remaining_holes(
        items, _ctx(day_end="19:00"), day_num=4,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts, "15:30–16:20 before day_end must be a named block"
    assert any(it.start_time <= "15:35" and it.end_time >= "16:10" for it in fts)


def test_69min_after_lunch_is_eaten():
    items = [
        _lunch("12:36", "13:21", 45),
        _ft("13:21", "14:30", 69),
        _attr("Wystawa Pająków", "14:30", "15:30", 60, lat=51.094, lng=17.021),
    ]
    out = _svc()._eat_long_free_time_before_attraction(
        items, day_num=4, min_ft=45, keep=20,
    )
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts
    assert int(fts[0].duration_min) <= 25
    pajaki = next(
        it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION
    )
    assert pajaki.start_time < "14:30"


def test_stacked_buffer_and_ft_before_lunch_collapse():
    items = [
        _attr("Hydropolis", "10:00", "11:00", 60, lat=51.104, lng=17.056),
        _ft("11:00", "11:35", 35, label="Krótka przerwa / bufor"),
        _ft("11:35", "13:05", 90, label="Czas dla siebie"),
        _lunch("13:05", "13:50", 45),
    ]
    out = _svc()._collapse_adjacent_free_time(items, day_num=6)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert len(fts) == 1
    assert int(fts[0].duration_min) >= 120
    out2 = _svc()._eat_long_free_time_before_attraction(
        out, day_num=6, min_ft=45, keep=20, pull_lunch=True,
    )
    fts2 = [it for it in out2 if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert fts2
    assert int(fts2[0].duration_min) <= 45
    lunch = next(
        it for it in out2 if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    )
    assert lunch.start_time <= "12:00"
