"""FIX #293 — Wrocław leftover: dupes, 3 km/5 min walks, FT labels, clocks."""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    FreeTimeItem,
    ItemType,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.planner.explainability import _explain_profile_match
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key


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


def _tr(frm, to, start, end, *, km, dur, mode=TransitMode.WALK, src="estimated_walk"):
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


def _ft(start, end, dur, *, label="Czas wolny", suggestions=None):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=suggestions or [],
    )


def test_hydropolis_and_botaniczny_repeat_keys():
    assert poi_trip_repeat_key("Hydropolis") == "wro_hydropolis"
    assert poi_trip_repeat_key("Ogród Botaniczny Uniwersytetu Wrocławskiego")


def test_katedra_and_tumski_caps():
    assert visit_duration_hard_cap({"name": "Katedra Wrocławska"}) == 60
    assert visit_duration_hard_cap({"name": "Most Tumski"}) == 20


def test_declared_3km_walk_in_5_min_becomes_car():
    hop = _tr(
        "Hydropolis", "Galeria Neon Side", "16:00", "16:05",
        km=3.464, dur=5, mode=TransitMode.WALK, src="estimated_road",
    )
    # Fake endpoints 200 m apart so haversine would lie.
    hyd = _attr("Hydropolis", "14:00", "16:00", 120, lat=51.104, lng=17.056)
    neon = _attr("Galeria Neon Side", "16:30", "17:15", 45, lat=51.105, lng=17.057)
    out = _svc()._sanitize_walk_leg_durations(
        [hyd, hop, neon], {}, day_num=2, context={"has_car": True},
    )
    legs = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert legs
    mode = str(getattr(legs[0].mode, "value", legs[0].mode)).lower()
    assert "car" in mode
    assert int(legs[0].duration_min) >= 8


def test_38m_11min_walk_shrinks():
    hop = _tr(
        "Izba Muzealna", "Rynek w Oławie", "16:00", "16:11",
        km=0.038, dur=11, mode=TransitMode.WALK, src="estimated_road",
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=8)
    assert "walk" in str(getattr(out[0].mode, "value", out[0].mode)).lower()
    assert int(out[0].duration_min) <= 5


def test_84m_15min_walk_shrinks():
    hop = _tr(
        "Aula Leopoldina", "Restauracja", "14:00", "14:15",
        km=0.084, dur=15, mode=TransitMode.WALK,
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=2)
    assert int(out[0].duration_min) <= 5


def test_hala_follows_pergola_in_time():
    items = [
        _attr("Pergola przy Hali Stulecia", "11:00", "11:40", 40),
        _attr("Rynek we Wrocławiu", "12:30", "13:30", 60),
        _attr("Hala Stulecia", "15:00", "16:00", 60),
    ]
    out = _svc()._cluster_adjacent_icons(items, day_num=1)
    hala = next(it for it in out if "Hala" in it.name)
    assert hala.start_time <= "11:55"


def test_inverted_neon_clock_repaired():
    items = [_attr("Galeria Neon Side", "18:27", "18:05", 45)]
    out = _svc()._fix_inverted_item_clocks(items, day_num=4)
    assert out[0].start_time == "18:27"
    assert out[0].end_time > out[0].start_time


def test_morning_label_after_attraction_rewritten():
    items = [
        _attr("Movie Gate", "09:30", "11:15", 105),
        _ft(
            "11:15", "11:45", 30,
            label="Spokojny poranek",
            suggestions=["Śniadanie kawowe w okolicy"],
        ),
    ]
    out = _svc()._relabel_free_time_by_context(items, day_num=8)
    ft = next(it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME)
    blob = (ft.label or "").lower() + " " + " ".join(str(s).lower() for s in (ft.suggestions or []))
    assert "śniadanie" not in blob
    assert "sniadanie" not in blob
    assert "kawa na start" not in blob


def test_popoludniowa_before_13_relabelled():
    items = [_ft("12:00", "12:24", 24, label="Popołudniowa przerwa")]
    out = _svc()._relabel_free_time_by_context(items, day_num=4)
    assert "popołudniow" not in (out[0].label or "").lower()


def test_eat_ft_to_fit_day_end():
    items = [
        _attr("Hydropolis", "16:00", "17:00", 60),
        _ft("17:00", "17:47", 47),
        _attr("Kolacja-like", "18:00", "19:32", 92),
        DayEndItem(time="19:32"),
    ]
    out = _svc()._eat_free_time_to_fit_day_end(
        items, {"day_end": "19:00"}, day_num=1,
    )
    last = max(
        time_to_minutes_safe(getattr(it, "end_time", None))
        for it in out
        if getattr(it, "end_time", None)
    )
    assert last <= 19 * 60 + 10


def time_to_minutes_safe(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def test_pana_tadeusza_not_group_adventure():
    text = _explain_profile_match(
        {"name": "Muzeum Pana Tadeusza", "tags": "museum park heritage"},
        {"target_group": "friends", "travel_style": "adventure"},
    )
    assert text != "Świetne na grupowe przygody"


def test_zajezdnia_pulled_over_long_break():
    items = [
        _attr("Rynek", "12:00", "13:00", 60),
        _ft("13:00", "14:19", 79),
        _attr("Centrum Historii Zajezdnia", "14:19", "15:45", 86),
    ]
    out = _svc()._eat_long_free_time_before_attraction(items, day_num=2)
    ft = next(it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME)
    zaje = next(
        it for it in out
        if "Zajezdnia" in (getattr(it, "name", None) or "")
    )
    assert int(ft.duration_min) <= 25
    assert zaje.start_time < "14:19"


def test_slot_relabel_does_not_restore_morning_copy_after_noonish():
    items = [
        _attr("Movie Gate", "09:30", "11:15", 105),
        _ft(
            "11:15", "11:45", 30,
            label="Popołudniowa przerwa",
            suggestions=["Kawa na start dnia"],
        ),
    ]
    out = _svc()._relabel_free_time_by_slot(
        items, {"day_start": "09:00", "day_end": "19:00"}, day_num=8,
    )
    out = _svc()._relabel_free_time_by_context(out, day_num=8)
    ft = next(it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME)
    blob = (ft.label or "").lower() + " " + " ".join(
        str(s).lower() for s in (ft.suggestions or [])
    )
    assert "śniadanie" not in blob
    assert "sniadanie" not in blob
    assert "kawa na start" not in blob
    assert "poranna" not in blob
