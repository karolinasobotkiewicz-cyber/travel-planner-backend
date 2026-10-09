"""FIX #369 P2: the car has a real position for the whole day (Kraków UAT 2026-10-09).

Mateo's mail: returns to the car into generic "Kraków" (J1 D2 "start był na
Plantach, brak parkingu", J2 D1–3, J6 D2, J8 D1–2, J9 D3, J10 D2), car rides
that start where the car never was (J1 D1 Kopiec→Katedra "teleport"), and loops
that fetch the car for nothing (J1 D1 back to Kopiec and Błonia again, J7 D1
"znów autem na kopiec tylko na wolny czas", J9 D1 Kopiec again for free time,
J4 D4 double return Plac Bohaterów Getta→Smok, J9 D3 Wieża Ratuszowa→Barbakan
"po auto"→Rynek).

Model: the car spends the night at the car park nearest the start point, every
car ride runs parking → parking (krakow_parking, real OSM car parks), people
walk back to wherever the car stands, and the car is fetched only for a hop
that is not walkable and when fetching it is not a detour.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

import pytest

from app.domain.planner import krakow_parking as kp
from app.domain.planner import leg_physics as lp

PIN = {
    "Kopiec Kościuszki": (50.0548415, 19.8927559),
    "Katedra Wawelska": (50.0546371, 19.9354684),
    "Zamek Królewski na Wawelu": (50.0541115, 19.935423),
    "Pomnik Smoka Wawelskiego": (50.0530183, 19.9335845),
    "Błonia Krakowskie": (50.0625208, 19.902403),
    "Bulwary Wiślane": (50.052, 19.9566),
    "Plac Bohaterów Getta": (50.0468999, 19.9548221),
    "Fabryka Emalia Oskara Schindlera": (50.0474296, 19.9615736),
    "Restauracja Po Krakosku": (50.0484066, 19.9446114),
    "Szalone Widelce": (50.0643181, 19.942157),
    "plac Jana Matejki": (50.066574, 19.9420796),
    "Muzeum Obwarzanka": (50.0666362, 19.9408286),
    "Park Wodny Kraków": (50.0892456, 19.9828089),
    "Wieża Ratuszowa": (50.0615295, 19.9364793),
    "Barbakan": (50.0654718, 19.9416613),
    "Rynek Główny w Krakowie": (50.0618971, 19.936756),
    "Skałki Twardowskiego": (50.0409886, 19.903969),
    "Muzeum Narodowe w Krakowie": (50.0603322, 19.9238092),
}
CTX = {"requested_city": "Kraków", "has_car": True, "travel_style": "balanced"}
RELAX = {**CTX, "travel_style": "relax"}
SENIORS = {**CTX, "travel_style": "relax", "group_type": "seniors"}
P0 = str(kp.start_parking(lp.KRAKOW_HUB)["name"])


# --- curated parking table ---------------------------------------------------

def test_parking_table_is_real_and_sourced():
    names = [p["name"] for p in kp.KRAKOW_PARKINGS]
    assert len(names) == len(set(names)) and len(names) >= 20
    for p in kp.KRAKOW_PARKINGS:
        assert str(p["source"]).startswith("OSM way "), p
        assert 49.95 < float(p["lat"]) < 50.13 and 19.80 < float(p["lng"]) < 20.10, p
        assert kp.is_parking_label(str(p["name"]))
        assert kp.parking_point(str(p["name"])) == (float(p["lat"]), float(p["lng"]))


def test_parking_labels_never_collide_with_poi_names():
    """Validators match names by substring: a label must not read as a POI."""
    from app.domain.validators.client_invariants import _names_match

    for p in kp.KRAKOW_PARKINGS:
        for poi in PIN:
            assert not _names_match(str(p["name"]), poi), (p["name"], poi)
        for hub in ("Kraków", "Kraków centrum", "Centrum"):
            assert not _names_match(str(p["name"]), hub), p["name"]


@pytest.mark.parametrize("poi,parking,max_km", [
    ("Kopiec Kościuszki", "Parking pl. Paula McCartneya (pod Kopcem)", 0.15),
    ("Fabryka Emalia Oskara Schindlera", "Parking Zabłocie (ul. Przemysłowa)", 0.2),
    ("Katedra Wawelska", "Parking plac Na Groblach (pod Wawelem)", 0.4),
    ("Błonia Krakowskie", "Parking ul. Piastowska 18", 0.2),
    ("Park Wodny Kraków", "Parking ul. Dobrego Pasterza", 0.3),
    ("Plac Bohaterów Getta", "Parking Podgórze (ul. Na Zjeździe)", 0.15),
])
def test_nearest_parking_for_mateo_pois(poi, parking, max_km):
    p, km = kp.nearest_parking(PIN[poi])
    assert p["name"] == parking and km <= max_km


def test_every_plan_stop_has_a_parking_within_walking_range():
    for name, pt in PIN.items():
        _p, km = kp.nearest_parking(pt)
        assert km < 0.9, name


# --- seal on Mateo's days -----------------------------------------------------

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


def _hop(frm, to, st, en, km, dur, mode="walk", src="estimated_walk"):
    from app.domain.models.plan import ItemType, TransitItem, TransitMode

    return TransitItem.model_construct(
        type=ItemType.TRANSIT, start_time=st, end_time=en, duration_min=dur,
        mode=TransitMode(mode), from_location=frm, to_location=to,
        distance_km=km, routing_source=src,
    )


def _free(st, en, label="Czas dla siebie"):
    from app.domain.models.plan import FreeTimeItem, ItemType

    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME, start_time=st, end_time=en,
        duration_min=_hm(en) - _hm(st), label=label, description="x",
    )


def _day(*items, start="09:00", end="20:00"):
    from app.domain.models.plan import DayEndItem, DayStartItem

    return [DayStartItem(time=start), *items, DayEndItem(time=end)]


def _tv(it):
    t = getattr(it, "type", None)
    return str(getattr(t, "value", t))


def _hm(raw):
    h, m = str(raw).split(":")
    return int(h) * 60 + int(m)


def _legs(items):
    return [x for x in items if _tv(x) == "transit"]


def _mode(x):
    return str(getattr(x.mode, "value", x.mode))


def _car_audit(items, **extra):
    from app.domain.validators.client_invariants import audit_day

    ctx = {"requested_city": "Kraków", "has_car": True, "audit_car_model": True,
           "audit_leg_distances": True, **extra}
    return [d for d in audit_day(items, day=1, context=ctx)
            if d.code in ("generic_car_return", "car_position_mismatch",
                          "car_teleport", "distance_vs_coords_mismatch",
                          "from_mismatch", "missing_hop", "self_hop",
                          "phantom_lead", "dangling_hop")]


def _assert_car_model(items, ctx=CTX):
    """Every ride is parking → parking from where the car stands; no loops."""
    car = P0
    people = None
    for x in _legs(items):
        assert not lp.has_constant_signature(x.distance_km, x.duration_min), x
        if _mode(x) == "car":
            assert kp.is_parking_label(x.to_location), x.to_location
            if car != P0 or x.from_location != "Kraków":
                assert x.from_location == car, (x.from_location, car)
            car = x.to_location
        elif x.routing_source == "return_to_car":
            assert x.to_location == car, (x.to_location, car)
            assert kp.is_parking_label(x.to_location)
        people = x.to_location
    assert people is not None
    from tests.test_fix369_p2_car_parking import car_loops
    assert not car_loops(items, ctx), car_loops(items, ctx)
    assert not _car_audit(items), [d.message for d in _car_audit(items)]
    timed = [x for x in items if getattr(x, "start_time", None)]
    for p, q in zip(timed, timed[1:]):
        assert _hm(p.end_time) <= _hm(q.start_time), (p, q)


def test_j1_d1_kopiec_katedra_blonia_loop_is_one_honest_car_chain():
    """J1 D1: Kopiec→Katedra 0,8 km + back to Kopiec + Błonia again (loop)."""
    day = _day(
        _hop("Kraków", "Kopiec Kościuszki", "09:00", "09:20", 4.0, 20, "car", "estimated_road"),
        _attr("Kopiec Kościuszki", "09:20", "10:30"),
        _hop("Kopiec Kościuszki", "Katedra Wawelska", "10:30", "10:40", 0.8, 10),
        _attr("Katedra Wawelska", "10:40", "11:40"),
        _hop("Katedra Wawelska", "Błonia Krakowskie", "11:40", "11:50", 0.8, 10),
        _attr("Błonia Krakowskie", "11:50", "12:30"),
        _hop("Błonia Krakowskie", "Kopiec Kościuszki", "12:30", "12:40", 0.5, 10, "walk", "return_to_car"),
        _hop("Kopiec Kościuszki", "Błonia Krakowskie", "12:40", "12:50", 2.0, 10, "car", "estimated_road"),
        _free("12:50", "13:30"),
    )
    out = _svc()._seal_fix369_car_parking(day, dict(CTX), day_num=1)
    _assert_car_model(out)
    cars = [x for x in _legs(out) if _mode(x) == "car"]
    assert cars[0].to_location == "Parking pl. Paula McCartneya (pod Kopcem)"
    assert cars[1].from_location == "Parking pl. Paula McCartneya (pod Kopcem)"
    assert cars[1].to_location == "Parking plac Na Groblach (pod Wawelem)"
    # No ride back to Kopiec after Błonia (nothing is visited there).
    assert all("Kopc" not in x.to_location for x in cars[2:])


@pytest.mark.parametrize("case", ["J1 D2", "J2 D1", "J6 D2", "J8 D1", "J9 D3", "J10 D2"])
def test_generic_krakow_return_targets_the_real_parking(case):
    """'powrót po auto do „Kraków” 0,5 km/10 min' → walk to the actual car park."""
    day = _day(
        _hop("Kraków", "plac Jana Matejki", "09:00", "09:07", 0.4, 7),
        _attr("plac Jana Matejki", "09:07", "09:40"),
        _hop("plac Jana Matejki", "Kraków", "09:40", "09:50", 0.5, 10, "walk", "return_to_car"),
        _hop("Kraków", "Park Wodny Kraków", "09:50", "10:10", 5.4, 20, "car", "estimated_road"),
        _attr("Park Wodny Kraków", "10:10", "12:40"),
    )
    out = _svc()._seal_fix369_car_parking(day, dict(CTX), day_num=1)
    _assert_car_model(out)
    back = [x for x in _legs(out) if x.routing_source == "return_to_car"]
    assert [b.to_location for b in back] == [P0]
    assert all(b.to_location != "Kraków" for b in back)
    car = [x for x in _legs(out) if _mode(x) == "car"]
    assert (car[0].from_location, car[0].to_location) == (P0, "Parking ul. Dobrego Pasterza")
    assert car[0].distance_km > 5


def test_j4_d4_smok_double_return_becomes_a_walk():
    """J4 D4: Katedra and Smok are next to each other — never fetch the car."""
    day = _day(
        _hop("Kraków", "Plac Bohaterów Getta", "09:00", "09:12", 3.0, 12, "car", "estimated_road"),
        _attr("Plac Bohaterów Getta", "09:12", "09:40"),
        _hop("Plac Bohaterów Getta", "Pomnik Smoka Wawelskiego", "09:40", "09:50", 0.8, 10, "car", "estimated_road"),
        _attr("Pomnik Smoka Wawelskiego", "09:50", "10:10"),
        _hop("Pomnik Smoka Wawelskiego", "Plac Bohaterów Getta", "10:10", "10:20", 0.5, 10, "walk", "return_to_car"),
        _hop("Plac Bohaterów Getta", "Pomnik Smoka Wawelskiego", "10:20", "10:30", 2.0, 10, "car", "estimated_road"),
        _hop("Pomnik Smoka Wawelskiego", "Katedra Wawelska", "10:30", "10:40", 0.5, 10, "walk", "return_to_car"),
        _attr("Katedra Wawelska", "10:40", "11:40"),
    )
    out = _svc()._seal_fix369_car_parking(day, dict(CTX), day_num=1)
    _assert_car_model(out)
    legs = {(x.from_location, x.to_location): x for x in _legs(out)}
    assert _mode(legs[("Pomnik Smoka Wawelskiego", "Katedra Wawelska")]) == "walk"
    assert sum(1 for x in _legs(out) if x.routing_source == "return_to_car") <= 1


def test_j9_d3_wieza_barbakan_rynek_is_walked():
    """J9 D3: Wieża Ratuszowa → Barbakan 'po auto' → Rynek — all on foot."""
    day = _day(
        _hop("Kraków", "Wieża Ratuszowa", "09:00", "09:08", 0.6, 8),
        _attr("Wieża Ratuszowa", "09:08", "09:40"),
        _hop("Wieża Ratuszowa", "Barbakan", "09:40", "09:50", 0.5, 10, "walk", "return_to_car"),
        _hop("Barbakan", "Rynek Główny w Krakowie", "09:50", "10:00", 0.8, 10, "car", "estimated_road"),
        _attr("Rynek Główny w Krakowie", "10:00", "10:40"),
        _hop("Rynek Główny w Krakowie", "Barbakan", "10:40", "10:50", 0.5, 10),
        _attr("Barbakan", "10:50", "11:20"),
        start="09:00",
    )
    out = _svc()._seal_fix369_car_parking(day, dict(RELAX), day_num=1)
    assert all(_mode(x) == "walk" for x in _legs(out)), [
        (x.from_location, x.to_location, _mode(x)) for x in _legs(out)
    ]
    assert not any(x.routing_source == "return_to_car" for x in _legs(out))
    _assert_car_model(out, RELAX)


@pytest.mark.parametrize("case,first,ctx", [
    ("J7 D1", "Szalone Widelce", CTX),
    ("J9 D1", "Bulwary Wiślane", RELAX),
])
def test_kopiec_free_time_ride_is_gone(case, first, ctx):
    """J7 D1 / J9 D1: after Kopiec → Katedra, 'znów autem na kopiec' for free time."""
    day = _day(
        _hop("Kraków", first, "09:00", "09:10", 0.8, 10),
        _attr(first, "09:10", "10:00"),
        _hop(first, "Kopiec Kościuszki", "10:00", "10:10", 0.8, 10),
        _attr("Kopiec Kościuszki", "10:10", "11:10"),
        _hop("Kopiec Kościuszki", "Katedra Wawelska", "11:10", "11:20", 0.5, 10),
        _attr("Katedra Wawelska", "11:20", "12:20"),
        _hop("Katedra Wawelska", "Kopiec Kościuszki", "12:20", "12:30", 0.5, 10, "walk", "return_to_car"),
        _hop("Kopiec Kościuszki", "Kopiec Kościuszki", "12:30", "12:40", 0.0, 10, "car", "estimated_road"),
        _free("12:40", "14:00"),
    )
    out = _svc()._seal_fix369_car_parking(day, dict(ctx), day_num=1)
    _assert_car_model(out, ctx)
    cars = [x for x in _legs(out) if _mode(x) == "car"]
    kopiec = "Parking pl. Paula McCartneya (pod Kopcem)"
    assert sum(1 for x in cars if x.to_location == kopiec) == 1
    # The day ends at Katedra: nothing drives back up the hill.
    assert _legs(out)[-1].to_location == "Katedra Wawelska"


def test_j8_d2_walkable_day_never_moves_the_car():
    """J8 D1–2: centre-only day — walk from the start, no fake return to 'Kraków'."""
    day = _day(
        _hop("Kraków", "Muzeum Obwarzanka", "09:00", "09:10", 0.5, 10),
        _attr("Muzeum Obwarzanka", "09:10", "10:30"),
        _hop("Muzeum Obwarzanka", "Kraków", "10:30", "10:40", 0.5, 10, "walk", "return_to_car"),
        _hop("Kraków", "Szalone Widelce", "10:40", "10:50", 0.8, 10, "car", "estimated_road"),
        _attr("Szalone Widelce", "10:50", "11:30"),
        _hop("Szalone Widelce", "Rynek Główny w Krakowie", "11:30", "11:40", 0.5, 10),
        _attr("Rynek Główny w Krakowie", "11:40", "12:30"),
    )
    out = _svc()._seal_fix369_car_parking(day, dict(CTX), day_num=1)
    assert all(_mode(x) == "walk" for x in _legs(out))
    assert not any(x.routing_source == "return_to_car" for x in _legs(out))
    _assert_car_model(out)


def test_far_car_is_left_parked_and_people_ride_transit():
    """Car at Kopiec, people walked on via Błonia to MNK: no trek back to it."""
    day = _day(
        _hop("Kraków", "Kopiec Kościuszki", "09:00", "09:20", 4.0, 20, "car", "estimated_road"),
        _attr("Kopiec Kościuszki", "09:20", "10:30"),
        _hop("Kopiec Kościuszki", "Błonia Krakowskie", "10:30", "10:50", 1.4, 20),
        _attr("Błonia Krakowskie", "10:50", "11:30"),
        _hop("Błonia Krakowskie", "Muzeum Narodowe w Krakowie", "11:30", "12:00", 2.0, 30),
        _attr("Muzeum Narodowe w Krakowie", "12:00", "13:00"),
        _hop("Muzeum Narodowe w Krakowie", "Park Wodny Kraków", "13:00", "13:30", 9.0, 30, "car", "estimated_road"),
        _attr("Park Wodny Kraków", "13:40", "15:00"),
    )
    out = _svc()._seal_fix369_car_parking(day, dict(CTX), day_num=1)
    _assert_car_model(out)
    last = [x for x in _legs(out) if x.to_location == "Park Wodny Kraków"][-1]
    assert last.from_location == "Muzeum Narodowe w Krakowie"
    assert _mode(last) == "public_transport"
    assert not any(x.routing_source == "return_to_car" for x in _legs(out))


def test_seal_is_krakow_and_car_only():
    svc = _svc()
    day = _day(
        _hop("Kraków", "Kopiec Kościuszki", "09:00", "09:20", 4.0, 20, "car", "estimated_road"),
        _attr("Kopiec Kościuszki", "09:20", "10:30"),
    )
    for city in ("Wrocław", "Zakopane", "Katowice"):
        assert svc._seal_fix369_car_parking(day, {"requested_city": city, "has_car": True}, day_num=1) is day
    assert svc._seal_fix369_car_parking(day, {**CTX, "has_car": False}, day_num=1) is day


# --- validator -----------------------------------------------------------------

def test_validator_flags_generic_return_and_car_position():
    bad = _day(
        _hop("Kraków", "Parking ul. Szpitalna", "09:00", "09:05", 0.3, 5, "walk"),
        _hop("Parking ul. Szpitalna", "Parking pl. Paula McCartneya (pod Kopcem)", "09:05", "09:25", 5.6, 20, "car", "estimated_road"),
        _hop("Parking pl. Paula McCartneya (pod Kopcem)", "Kopiec Kościuszki", "09:25", "09:27", 0.1, 2),
        _attr("Kopiec Kościuszki", "09:27", "10:30"),
        _hop("Kopiec Kościuszki", "Kraków", "10:30", "10:40", 0.5, 10, "walk", "return_to_car"),
        _hop("Kraków", "Katedra Wawelska", "10:40", "10:55", 5.5, 15, "car", "estimated_road"),
        _attr("Katedra Wawelska", "10:55", "11:55"),
        _hop("Katedra Wawelska", "Pomnik Smoka Wawelskiego", "11:55", "11:58", 0.2, 3, "walk", "return_to_car"),
        _attr("Pomnik Smoka Wawelskiego", "12:00", "12:20"),
        _hop("Pomnik Smoka Wawelskiego", "Parking Zabłocie (ul. Przemysłowa)", "12:20", "12:50", 2.6, 30, "walk", "return_to_car"),
    )
    codes = [d.code for d in _car_audit(bad)]
    assert codes.count("generic_car_return") == 2   # "Kraków" and a POI
    assert "car_position_mismatch" in codes          # car from "Kraków" while at Kopiec
    msgs = " ".join(d.message for d in _car_audit(bad) if d.code == "car_position_mismatch")
    assert "Zabłocie" in msgs                         # walking to a car that is not there


def test_validator_flags_car_teleport_from_a_stop():
    """J1 D1 'teleport': the car leaves from a stop the people walked to."""
    bad = _day(
        _hop("Kraków", "Katedra Wawelska", "09:00", "09:20", 1.6, 20),
        _attr("Katedra Wawelska", "09:20", "10:20"),
        _hop("Katedra Wawelska", "Parking pl. Paula McCartneya (pod Kopcem)", "10:20", "10:40", 4.8, 20, "car", "estimated_road"),
        _hop("Parking pl. Paula McCartneya (pod Kopcem)", "Kopiec Kościuszki", "10:40", "10:42", 0.1, 2),
        _attr("Kopiec Kościuszki", "10:42", "11:40"),
    )
    assert "car_position_mismatch" in [d.code for d in _car_audit(bad)]


def test_validator_car_checks_are_opt_in():
    from app.domain.validators.client_invariants import audit_day

    bad = _day(
        _attr("Kopiec Kościuszki", "09:27", "10:30"),
        _hop("Kopiec Kościuszki", "Kraków", "10:30", "10:40", 0.5, 10, "walk", "return_to_car"),
        _hop("Kraków", "Katedra Wawelska", "10:40", "10:55", 5.5, 15, "car", "estimated_road"),
        _attr("Katedra Wawelska", "10:55", "11:55"),
    )
    codes = {d.code for d in audit_day(bad, day=1, context={"requested_city": "Kraków"})}
    assert not codes & {"generic_car_return", "car_position_mismatch"}


# --- helper shared with the gate-style counts ---------------------------------

def car_loops(day_items, ctx):
    """Kopiec-type loops: the car is fetched for a hop that is walkable, or a
    ride ends where nothing is visited before the next ride / day end."""
    from app.domain.validators import client_invariants as ci

    items = list(day_items or [])
    thr = lp.walk_threshold_km(ctx)
    out = []
    first_car = True
    for idx, it in enumerate(items):
        if not ci._is_transit(it) or "car" not in ci._mode(it):
            continue
        a = b = None
        for x in reversed(items[:idx]):
            if ci._stop_name(x) and ci._coords(x):
                a = (ci._stop_name(x), ci._coords(x))
                break
        nxt_car = next(
            (j for j in range(idx + 1, len(items))
             if ci._is_transit(items[j]) and "car" in ci._mode(items[j])),
            len(items),
        )
        for x in items[idx + 1:nxt_car]:
            if ci._stop_name(x):
                b = (ci._stop_name(x), ci._coords(x))
                break
        frm = getattr(it, "from_location", "")
        to = getattr(it, "to_location", "")
        if b is None:
            out.append(f"ride to nowhere {frm} -> {to}")
        elif a is not None and b[1] is not None and not first_car:
            km = lp.leg_km(a[1], b[1], "walk", city="Kraków")[0]
            if km <= thr:
                out.append(f"car fetched for walkable {a[0]} -> {b[0]} ({km:.2f} km walk)")
        first_car = False
    return out


# --- real generation (Mateo's 10 Kraków JSONs) ---------------------------------

_HERE = Path(__file__).resolve().parent
_JSON_DIR = _HERE.parents[1] / "json_miasta" / "Kraków"
_EXCEL = _HERE.parents[0] / "data" / "zakopane.xlsx"


@pytest.mark.parametrize("num", list(range(1, 11)))
def test_generated_krakow_plans_follow_the_car(num):
    path = _JSON_DIR / f"test-{num:02d}.json"
    if not path.exists() or not _EXCEL.exists():
        pytest.skip("Kraków fixtures are not present in this checkout")
    os.environ.setdefault("ORS_ENABLED", "false")
    from app.domain.models.trip_input import TripInput
    from app.domain.validators.client_invariants import audit_plan

    payload = json.loads(path.read_text(encoding="utf-8"))
    with contextlib.redirect_stdout(io.StringIO()):
        plan = _svc().generate_plan(TripInput(**payload))
    ctx = {
        "requested_city": "Kraków", "has_car": True,
        "travel_style": payload.get("travel_style"),
        "group_type": (payload.get("group") or {}).get("type"),
        "audit_leg_distances": True, "audit_car_model": True,
    }
    generic = mismatch = 0
    loops: list = []
    for d in audit_plan(plan.days, context=ctx):
        generic += d.code == "generic_car_return"
        mismatch += d.code in ("car_position_mismatch", "car_teleport")
    for day in plan.days:
        loops += [f"D{day.day} {x}" for x in car_loops(day.items, ctx)]
        for it in day.items:
            if _tv(it) != "transit":
                continue
            if _mode(it) == "car":
                assert kp.is_parking_label(it.to_location), (num, day.day, it.to_location)
            if it.routing_source == "return_to_car":
                assert kp.is_parking_label(it.to_location), (num, day.day, it.to_location)
    assert (generic, mismatch, loops) == (0, 0, []), (num, generic, mismatch, loops)
