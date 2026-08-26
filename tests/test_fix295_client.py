"""FIX #295 — Warszawa leftover: transits, Kampinos thin hops, uniqueness, floors."""
from __future__ import annotations

from types import SimpleNamespace

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    FreeTimeItem,
    ItemType,
    TransitItem,
    TransitMode,
)
from app.domain.planner.engine import visit_duration_hard_cap
from app.domain.planner.explainability import _explain_category_highlight
from app.domain.planner.poi_copy import classify_poi_category
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur=60, *, lat=52.23, lng=21.01, city="Warszawa"):
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


def _ft(start, end, dur, *, label="Czas wolny"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def test_x_pawilon_repeat_key():
    assert poi_trip_repeat_key("X Pawilon Cytadeli Warszawskiej") == "waw_x_pawilon"


def test_x_pawilon_stripped_on_second_day():
    def _ns(name, st, en, dur):
        return SimpleNamespace(
            type=ItemType.ATTRACTION,
            name=name,
            start_time=st,
            end_time=en,
            duration_min=dur,
            poi_id=None,
            lat=52.26,
            lng=21.00,
        )

    days = [
        SimpleNamespace(
            day=4, quality_badges=None, date=None, weekday=None,
            items=[_ns("X Pawilon", "11:00", "12:00", 60)],
        ),
        SimpleNamespace(
            day=5, quality_badges=None, date=None, weekday=None,
            items=[
                _ns("X Pawilon", "10:00", "11:00", 60),
                _ns("POLIN", "12:00", "14:00", 120),
            ],
        ),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    d5 = [getattr(it, "name", "") for it in (out[1].items or [])]
    assert not any("pawilon" in n.lower() for n in d5)
    assert any("POLIN" in n for n in d5)


def test_pkin_ogrody_wodka_kopernik_floors():
    svc = _svc()
    pkin = svc._cap_stretched_attraction_durations(
        [_attr("Pałac Kultury i Nauki", "11:00", "11:20", 20)], day_num=1,
    )
    assert int(pkin[0].duration_min) >= 60
    ogrody = svc._cap_stretched_attraction_durations(
        [_attr("Ogrody Zamku Królewskiego", "14:00", "14:20", 20)], day_num=2,
    )
    assert int(ogrody[0].duration_min) >= 45
    wodka = svc._cap_stretched_attraction_durations(
        [_attr("Muzeum Polskiej Wódki", "15:00", "15:26", 26)], day_num=6,
    )
    assert int(wodka[0].duration_min) >= 45
    kop = svc._cap_stretched_attraction_durations(
        [_attr("Centrum Nauki Kopernik", "10:00", "10:50", 50)], day_num=8,
    )
    assert int(kop[0].duration_min) >= 90
    assert visit_duration_hard_cap({"name": "Centrum Nauki Kopernik"}) == 150


def test_wilanow_to_msn_too_short_walk_becomes_car():
    hop = _tr(
        "Wilanów", "MSN", "14:00", "14:10",
        km=13.6, dur=10, mode=TransitMode.WALK, src="estimated_road",
    )
    wilanow = _attr("Wilanów", "11:00", "14:00", 180, lat=52.165, lng=21.090)
    msn = _attr("MSN", "14:10", "15:10", 60, lat=52.232, lng=20.999)
    out = _svc()._sanitize_walk_leg_durations(
        [wilanow, hop, msn], {}, day_num=10, context={"has_car": True},
    )
    legs = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert legs
    mode = str(getattr(legs[0].mode, "value", legs[0].mode)).lower()
    assert "car" in mode
    assert int(legs[0].duration_min) >= 20


def test_417m_walk_24min_shrinks():
    hop = _tr(
        "Hala", "Koszyki", "13:00", "13:24",
        km=0.417, dur=24, mode=TransitMode.WALK, src="estimated_walk",
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=3)
    assert int(out[0].duration_min) <= 12


def test_321m_and_1km_car_become_walk():
    short = _tr(
        "A", "B", "12:00", "12:31",
        km=0.321, dur=31, mode=TransitMode.CAR, src="estimated_road",
    )
    mid = _tr(
        "C", "D", "15:00", "15:12",
        km=1.1, dur=12, mode=TransitMode.CAR, src="estimated_road",
    )
    out_s = _svc()._force_short_city_hops_walk([short], day_num=5)
    out_m = _svc()._force_short_city_hops_walk([mid], day_num=8)
    for hop in (out_s[0], out_m[0]):
        mode = str(getattr(hop.mode, "value", hop.mode)).lower()
        assert "walk" in mode


def test_tutti_santi_self_transit_stripped():
    items = [
        _attr("Tutti Santi", "13:00", "14:00", 60),
        _tr(
            "Tutti Santi", "Tutti Santi", "14:00", "14:12",
            km=0.0, dur=12, mode=TransitMode.WALK, src="estimated_walk",
        ),
        _attr("Zamek Królewski", "14:20", "15:50", 90),
    ]
    out = _svc()._strip_self_transits(items, day_num=7)
    hops = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert not hops


def test_kampinos_return_for_one_city_poi_dropped():
    items = [
        _attr(
            "Kampinoski Park Narodowy", "10:00", "12:00", 120,
            lat=52.32, lng=20.85,
        ),
        _tr(
            "Kampinoski Park Narodowy", "POLIN",
            "12:00", "14:12", km=53.0, dur=132, mode=TransitMode.CAR,
            src="estimated_road",
        ),
        _attr("POLIN", "14:12", "15:42", 90, lat=52.25, lng=20.99),
    ]
    out = _svc()._drop_post_far_excursion_lonely_city_stop(items, day_num=5)
    names = [getattr(it, "name", "") for it in out]
    assert any("Kampinos" in n for n in names)
    assert not any("POLIN" in n for n in names)


def test_dolina_wkry_after_kampinos_dropped():
    items = [
        _attr(
            "Kampinoski Park Narodowy", "10:00", "12:00", 120,
            lat=52.32, lng=20.85,
        ),
        _tr(
            "Kampinoski Park Narodowy", "Dolina Wkry",
            "12:00", "14:10", km=42.9, dur=130, mode=TransitMode.CAR,
            src="estimated_road",
        ),
        _attr(
            "Dolina Wkry", "14:10", "14:43", 33,
            lat=52.45, lng=20.73, city="Pomiechówek",
        ),
    ]
    out = _svc()._drop_thin_lonely_far_stops(items, day_num=8)
    names = [getattr(it, "name", "") for it in out]
    assert not any("Wkry" in n for n in names)
    assert any("Kampinos" in n for n in names)


def test_53km_132min_car_is_rebuilt():
    hop = _tr(
        "Kampinos", "Warszawa", "14:00", "16:12",
        km=53.0, dur=132, mode=TransitMode.CAR, src="estimated_road",
    )
    out = _svc()._sanitize_walk_leg_durations([hop], {}, day_num=5)
    assert int(out[0].duration_min) <= 90


def test_ft_after_long_far_hop_stripped():
    items = [
        _attr("Kampinoski Park Narodowy", "10:00", "12:00", 120),
        _tr(
            "Kampinoski Park Narodowy", "Warszawa centrum",
            "12:00", "14:12", km=53.96, dur=132, mode=TransitMode.CAR,
            src="estimated_road",
        ),
        _ft("14:12", "15:21", 69),
        _attr("POLIN", "15:21", "16:21", 60),
    ]
    out = _svc()._strip_free_time_before_long_far_hop(items, day_num=4)
    fts = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert not fts


def test_koszyki_is_not_active_sport():
    poi = {
        "name": "Hala Koszyki",
        "tags": ["physical_activity", "group_activity", "food_hall", "shopping"],
    }
    assert poi_covers_preference_report(poi, "active_sport") is False


def test_most_swietokrzyski_is_not_heritage_copy():
    poi = {
        "name": "Most Świętokrzyski",
        "tags": ["heritage", "historic", "bridge", "viewpoint"],
    }
    assert classify_poi_category(poi) == "viewpoint"
    reason = _explain_category_highlight(poi, {"target_group": "couples"})
    assert reason is None or "Zabytek z bogatą historią" not in reason


def test_walk_estimated_road_is_normalized():
    hop = _tr(
        "POLIN", "Stare Miasto", "14:00", "14:25",
        km=1.6, dur=25, mode=TransitMode.WALK, src="estimated_road",
    )
    out = _svc()._normalize_transit_mode_source([hop], day_num=6)
    assert out[0].routing_source == "estimated_walk"


def test_clock_span_5_vs_duration_19_syncs_down():
    hop = _tr(
        "A", "B", "15:21", "15:26",
        km=0.4, dur=19, mode=TransitMode.WALK, src="estimated_walk",
    )
    out = _svc()._sync_transit_duration_to_clock([hop], day_num=9)
    assert int(out[0].duration_min) <= 8


def test_zamek_tutti_santi_clock_expands_to_duration():
    hop = _tr(
        "Zamek Królewski", "Tutti Santi", "13:00", "13:05",
        km=1.917, dur=20, mode=TransitMode.WALK, src="estimated_road",
    )
    out = _svc()._sync_transit_duration_to_clock([hop], day_num=2)
    assert int(out[0].duration_min) == 20
    assert out[0].end_time == "13:20"
