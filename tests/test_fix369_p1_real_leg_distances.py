"""FIX #369 P1: real leg distances from coordinates (Kraków UAT 2026-10-09).

Mateo's mail: Kopiec→Katedra and Katedra→Błonia "0,8 km/10 min" (>3 km by
coords), returns to the car "always 0,5 km", MOCAK→Schindler "0,5 km/10 min"
although both sit at Lipowa 4 (~22 m), Muzeum Obwarzanka→Plac Bohaterów Getta
"0,8 km/10 min" (>2 km straight, across the Wisła), Po Krakosku→Schindler
"0,5 km/10 min" (~1,2 km straight across the Wisła), Szalone Widelce→Kopiec
"0,8 km/10 min" (~3,7 km), Skałki Twardowskiego→Kopiec as a straight line
(no river crossing), Bulwary→Kopiec "0,8 km/10 min" (>4,5 km).

Pins below are the ones the plan carries (multi_city_attractions.xlsx and the
restaurants table).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

import pytest

from app.domain.planner import leg_physics as lp
from app.infrastructure.routing.haversine import haversine_km

PIN = {
    "Kopiec Kościuszki": (50.0548415, 19.8927559),
    "Katedra Wawelska": (50.0546371, 19.9354684),
    "Błonia Krakowskie": (50.0625208, 19.902403),
    "Muzeum Sztuki Współczesnej MOCAK": (50.0476242, 19.9615334),
    "Fabryka Emalia Oskara Schindlera": (50.0474296, 19.9615736),
    "Muzeum Obwarzanka": (50.0666362, 19.9408286),
    "Plac Bohaterów Getta": (50.0468999, 19.9548221),
    "Szalone Widelce": (50.0643181, 19.942157),
    "Restauracja Po Krakosku": (50.0484066, 19.9446114),
    "Skałki Twardowskiego": (50.0409886, 19.903969),
    "Bulwary Wiślane": (50.052, 19.9566),
    "Royal Curry": (50.0671611, 19.94338),
    "Rynek Główny w Krakowie": (50.0618971, 19.936756),
}
CTX = {"requested_city": "Kraków", "has_car": True, "travel_style": "balanced"}
SENIORS = {**CTX, "group_type": "seniors", "travel_style": "relax"}


def _leg(a, b, mode="walk", ctx=CTX, **kw):
    return lp.honest_leg(PIN[a], PIN[b], requested_mode=mode, context=ctx, **kw)


# --- pure physics on Mateo's pairs -------------------------------------------

def test_mocak_schindler_same_address_is_a_few_steps():
    r = _leg("Muzeum Sztuki Współczesnej MOCAK", "Fabryka Emalia Oskara Schindlera")
    assert r["straight_km"] < 0.03
    assert r["mode"] == "walk"
    assert r["km"] < 0.05 and r["minutes"] <= 2
    assert not lp.has_constant_signature(r["km"], r["minutes"])


@pytest.mark.parametrize("a,b,min_straight", [
    ("Kopiec Kościuszki", "Katedra Wawelska", 3.0),
    ("Katedra Wawelska", "Błonia Krakowskie", 2.5),
    ("Szalone Widelce", "Kopiec Kościuszki", 3.6),
    ("Bulwary Wiślane", "Kopiec Kościuszki", 4.5),
])
def test_long_legs_are_real_km_and_never_a_walk(a, b, min_straight):
    r = _leg(a, b)
    assert r["straight_km"] >= min_straight
    assert r["km"] >= r["straight_km"] * 1.3 - 0.01
    assert r["mode"] != "walk", r
    assert r["minutes"] >= 15
    assert not lp.has_constant_signature(r["km"], r["minutes"])


@pytest.mark.parametrize("a,b", [
    ("Muzeum Obwarzanka", "Plac Bohaterów Getta"),
    ("Restauracja Po Krakosku", "Fabryka Emalia Oskara Schindlera"),
    ("Skałki Twardowskiego", "Kopiec Kościuszki"),
])
def test_wisla_crossing_routes_through_a_bridge(a, b):
    assert lp.crosses_wisla(PIN[a], PIN[b])
    r = _leg(a, b)
    assert r["bridge"], r
    assert r["km"] > r["straight_km"] * 1.3
    assert len(r["path"]) == 3


def test_po_krakosku_to_schindler_is_honest_walk_across_the_river():
    r = _leg("Restauracja Po Krakosku", "Fabryka Emalia Oskara Schindlera")
    assert 1.1 < r["straight_km"] < 1.3
    assert r["mode"] == "walk" and 1.5 <= r["km"] <= 2.2
    assert 20 <= r["minutes"] <= 30


def test_skalki_to_kopiec_uses_most_zwierzyniecki():
    r = _leg("Skałki Twardowskiego", "Kopiec Kościuszki", mode="car")
    assert r["bridge"] == "Most Zwierzyniecki"
    assert r["km"] > 2.5  # 1.736 km straight, no swim across the Wisła


def test_same_bank_legs_have_no_bridge():
    assert not lp.crosses_wisla(PIN["Kopiec Kościuszki"], PIN["Katedra Wawelska"])
    assert not lp.crosses_wisla(PIN["Bulwary Wiślane"], PIN["Kopiec Kościuszki"])
    assert not lp.crosses_wisla(
        PIN["Muzeum Sztuki Współczesnej MOCAK"], PIN["Plac Bohaterów Getta"],
    )


def test_walk_threshold_is_shorter_for_seniors_and_relax():
    a, b = PIN["Royal Curry"], PIN["Katedra Wawelska"]  # 1.5 km straight → 1.95 km
    assert lp.honest_leg(a, b, requested_mode="walk", context=CTX)["mode"] == "walk"
    assert lp.walk_threshold_km(SENIORS) == 2.0
    assert lp.walk_threshold_km(CTX) == 2.5
    # Bulwary → Rynek: same bank, ~1.8 km straight → ~2.3 km on foot.
    assert not lp.crosses_wisla(PIN["Bulwary Wiślane"], PIN["Rynek Główny w Krakowie"])
    far = lp.honest_leg(
        PIN["Bulwary Wiślane"], PIN["Rynek Główny w Krakowie"],
        requested_mode="walk", context=SENIORS,
    )
    near = lp.honest_leg(
        PIN["Bulwary Wiślane"], PIN["Rynek Główny w Krakowie"],
        requested_mode="walk", context=CTX,
    )
    assert 2.0 < near["km"] <= 2.5 and near["mode"] == "walk"
    assert far["mode"] == "public_transport"
    assert lp.walk_minutes(1.0, SENIORS) > lp.walk_minutes(1.0, CTX)


def test_return_to_car_never_becomes_a_car_ride():
    r = _leg("Kopiec Kościuszki", "Katedra Wawelska", car_here=True,
             force_walk_or_transit=True)
    assert r["mode"] == "public_transport"
    r2 = _leg("Kopiec Kościuszki", "Katedra Wawelska", car_here=True)
    assert r2["mode"] == "car"


def test_no_pair_produces_a_constant_signature():
    names = list(PIN)
    for a in names:
        for b in names:
            if a == b:
                continue
            for mode in ("walk", "car"):
                r = _leg(a, b, mode=mode)
                assert not lp.has_constant_signature(r["km"], r["minutes"]), (a, b, r)


def test_river_polyline_passes_every_bridge():
    for name, la, lo, _car in lp.KRAKOW_BRIDGES:
        if name.startswith("A4"):
            continue
        near = min(
            haversine_km(la, lo, p[0], p[1]) for p in lp.KRAKOW_WISLA
        )
        assert near < 0.9, name


# --- seal on hop-ledger constants -------------------------------------------

def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository

    root = Path(__file__).resolve().parents[1]
    return PlanService(POIRepository(str(root / "data" / "zakopane.xlsx")))


def _attr(name, st, en):
    from app.domain.models.plan import AttractionItem, ItemType

    la, lo = PIN[name]
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION, poi_id=name, name=name,
        description_short="x", why_selected=["x"], start_time=st, end_time=en,
        duration_min=0, lat=la, lng=lo, city="Kraków", cost_estimate=0,
        address="x",
    )


def _hop(frm, to, st, en, km, dur, mode="walk", src="adjacent_walk"):
    from app.domain.models.plan import ItemType, TransitItem, TransitMode

    return TransitItem.model_construct(
        type=ItemType.TRANSIT, start_time=st, end_time=en, duration_min=dur,
        mode=TransitMode(mode), from_location=frm, to_location=to,
        distance_km=km, routing_source=src,
    )


def _ledger_day():
    from app.domain.models.plan import DayEndItem, DayStartItem

    return [
        DayStartItem(time="09:00"),
        _hop("Kraków", "Kopiec Kościuszki", "09:00", "09:15", 4.0, 15, "car", "estimated_road"),
        _attr("Kopiec Kościuszki", "09:15", "10:30"),
        _hop("Kopiec Kościuszki", "Katedra Wawelska", "10:30", "10:40", 0.8, 10),
        _attr("Katedra Wawelska", "10:40", "11:40"),
        _hop("Katedra Wawelska", "Kraków", "11:40", "11:50", 0.5, 10, "walk", "return_to_car"),
        _hop("Kraków", "Muzeum Sztuki Współczesnej MOCAK", "11:50", "12:05", 2.5, 15, "car", "estimated_road"),
        _attr("Muzeum Sztuki Współczesnej MOCAK", "12:05", "13:05"),
        _hop("Muzeum Sztuki Współczesnej MOCAK", "Fabryka Emalia Oskara Schindlera", "13:05", "13:15", 0.5, 10),
        _attr("Fabryka Emalia Oskara Schindlera", "13:15", "15:00"),
        DayEndItem(time="19:00"),
    ]


def _tv(it):
    t = getattr(it, "type", None)
    return str(getattr(t, "value", t))


def _hm(raw):
    h, m = str(raw).split(":")
    return int(h) * 60 + int(m)


def test_seal_rewrites_ledger_constants_from_pins():
    svc = _svc()
    out = svc._seal_fix369_real_legs(_ledger_day(), dict(CTX), day_num=1)
    legs = {(x.from_location, x.to_location): x for x in out if _tv(x) == "transit"}
    kk = legs[("Kopiec Kościuszki", "Katedra Wawelska")]
    assert kk.distance_km >= 3.9 and str(kk.mode.value) == "public_transport"
    back = legs[("Katedra Wawelska", "Kraków")]
    assert back.routing_source == "return_to_car"
    assert str(back.mode.value) == "walk"
    assert 1.4 < back.distance_km < 2.5  # Wawel → hub pin, not 0.5 km
    ms = legs[("Muzeum Sztuki Współczesnej MOCAK", "Fabryka Emalia Oskara Schindlera")]
    assert ms.distance_km < 0.05 and ms.duration_min <= 2
    for x in legs.values():
        assert not lp.has_constant_signature(x.distance_km, x.duration_min)
        assert x.geometry and len(x.geometry) >= 2
    # Longer legs never overlap the next block.
    timed = [x for x in out if getattr(x, "start_time", None)]
    for p, q in zip(timed, timed[1:]):
        assert _hm(p.end_time) <= _hm(q.start_time), (p, q)


def test_seal_is_krakow_only_and_wroclaw_stays_frozen():
    svc = _svc()
    day = _ledger_day()
    assert svc._seal_fix369_real_legs(day, {"requested_city": "Wrocław"}, day_num=1) is day
    assert svc._seal_fix369_real_legs(day, {"requested_city": "Zakopane"}, day_num=1) is day
    assert svc._seal_fix369_real_legs(day, {"requested_city": "Katowice"}, day_num=1) is day


def test_seal_leaves_unresolved_pins_alone():
    from app.domain.models.plan import DayEndItem, DayStartItem

    svc = _svc()
    day = [
        DayStartItem(time="09:00"),
        _attr("Katedra Wawelska", "09:10", "10:00"),
        _hop("Katedra Wawelska", "Nieznane Miejsce XYZ", "10:00", "10:10", 0.8, 10),
        DayEndItem(time="19:00"),
    ]
    assert svc._seal_fix369_real_legs(day, dict(CTX), day_num=1) is day


# --- validator --------------------------------------------------------------

def _audit(items, **extra):
    from app.domain.validators.client_invariants import audit_day

    ctx = {"requested_city": "Kraków", "audit_leg_distances": True, **extra}
    return [d for d in audit_day(items, day=1, context=ctx)
            if d.code == "distance_vs_coords_mismatch"]


def test_validator_flags_constants_under_and_over():
    hits = _audit(_ledger_day())
    reasons = {(d.meta["from"], d.meta["to"]): d.meta["reason"] for d in hits}
    assert reasons[("Kopiec Kościuszki", "Katedra Wawelska")] == "constant"
    assert reasons[("Katedra Wawelska", "Kraków")] == "constant"
    assert reasons[
        ("Muzeum Sztuki Współczesnej MOCAK", "Fabryka Emalia Oskara Schindlera")
    ] == "constant"
    under = [
        _attr("Kopiec Kościuszki", "09:00", "10:00"),
        _hop("Kopiec Kościuszki", "Katedra Wawelska", "10:00", "10:20", 1.2, 20),
        _attr("Katedra Wawelska", "10:20", "11:00"),
    ]
    assert [d.meta["reason"] for d in _audit(under)] == ["under"]
    over = [
        _attr("Muzeum Sztuki Współczesnej MOCAK", "09:00", "10:00"),
        _hop("Muzeum Sztuki Współczesnej MOCAK", "Fabryka Emalia Oskara Schindlera",
             "10:00", "10:20", 1.7, 20),
        _attr("Fabryka Emalia Oskara Schindlera", "10:20", "11:00"),
    ]
    assert [d.meta["reason"] for d in _audit(over)] == ["over"]


def test_validator_flags_unresolved_constant_and_passes_honest_legs():
    unresolved = [
        _attr("Katedra Wawelska", "09:10", "10:00"),
        _hop("Katedra Wawelska", "Nieznane Miejsce XYZ", "10:00", "10:10", 0.8, 10),
    ]
    assert [d.meta["reason"] for d in _audit(unresolved)] == ["unresolved_constant"]
    svc = _svc()
    sealed = svc._seal_fix369_real_legs(_ledger_day(), dict(CTX), day_num=1)
    assert _audit(sealed) == []


def test_validator_check_is_opt_in():
    from app.domain.validators.client_invariants import audit_day

    hits = audit_day(_ledger_day(), day=1, context={"requested_city": "Kraków"})
    assert not [d for d in hits if d.code == "distance_vs_coords_mismatch"]


def test_public_transport_moves_people_for_car_teleport_check():
    from app.domain.validators.client_invariants import audit_day

    day = [
        _hop("Kraków", "Kopiec Kościuszki", "09:00", "09:15", 4.0, 15, "car", "estimated_road"),
        _attr("Kopiec Kościuszki", "09:15", "10:30"),
        _hop("Kopiec Kościuszki", "Katedra Wawelska", "10:30", "10:52", 4.1, 22,
             "public_transport", "estimated_transit"),
        _attr("Katedra Wawelska", "10:52", "11:40"),
        _hop("Katedra Wawelska", "Kopiec Kościuszki", "11:40", "12:02", 4.1, 22,
             "public_transport", "return_to_car"),
        _hop("Kopiec Kościuszki", "Muzeum Sztuki Współczesnej MOCAK", "12:02", "12:30",
             9.0, 28, "car", "estimated_road"),
        _attr("Muzeum Sztuki Współczesnej MOCAK", "12:30", "13:30"),
    ]
    codes = [d.code for d in audit_day(day, day=1, context={"requested_city": "Kraków"})]
    assert "car_teleport" not in codes


# --- real generation (Mateo's JSONs) -----------------------------------------

_HERE = Path(__file__).resolve().parent
_JSON_DIR = _HERE.parents[1] / "json_miasta" / "Kraków"
_EXCEL = _HERE.parents[0] / "data" / "zakopane.xlsx"


@pytest.mark.parametrize("num", [2, 7, 10])
def test_generated_krakow_plans_carry_only_real_legs(num):
    path = _JSON_DIR / f"test-{num:02d}.json"
    if not path.exists() or not _EXCEL.exists():
        pytest.skip("Kraków fixtures are not present in this checkout")
    os.environ.setdefault("ORS_ENABLED", "false")
    from app.domain.models.trip_input import TripInput
    from app.domain.validators.client_invariants import audit_plan

    svc = _svc()
    payload = json.loads(path.read_text(encoding="utf-8"))
    with contextlib.redirect_stdout(io.StringIO()):
        plan = svc.generate_plan(TripInput(**payload))
    legs = [it for d in plan.days for it in d.items if _tv(it) == "transit"]
    assert legs
    for it in legs:
        assert not lp.has_constant_signature(it.distance_km, it.duration_min), (
            num, it.from_location, it.to_location, it.distance_km, it.duration_min,
        )
        assert it.routing_source not in ("adjacent_walk",)
    hits = [
        d for d in audit_plan(plan.days, context={
            "requested_city": "Kraków", "has_car": True,
            "audit_leg_distances": True,
        })
        if d.code == "distance_vs_coords_mismatch"
    ]
    assert not hits, [d.message for d in hits]
