"""FIX #279 — transit geometry after late retarget, even with ORS off."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.plan_client_audit import audit_transit_routing
from app.application.services.plan_service import PlanService, _fold_place_label
from app.domain.models.plan import AttractionItem, ItemType, TransitItem, TransitMode
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository


def _attr(name: str, st: str, en: str, *, lat: float, lng: float) -> AttractionItem:
    sh, sm = (int(x) for x in st.split(":"))
    eh, em = (int(x) for x in en.split(":"))
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=st,
        end_time=en,
        duration_min=eh * 60 + em - (sh * 60 + sm),
        lat=lat,
        lng=lng,
        address="",
        cost_estimate=0,
    )


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def test_fix279_fold_ostrow():
    assert _fold_place_label("Ostrów Tumski") == "ostrow tumski"


def test_fix279_retarget_wipes_then_finalize_restores():
    svc = _svc()
    movie = _attr("Movie Gate", "10:00", "11:00", lat=51.1079, lng=17.0385)
    ostrow = _attr("Ostrów Tumski", "11:20", "12:20", lat=51.1144, lng=17.0465)
    leg = TransitItem(
        type=ItemType.TRANSIT,
        mode=TransitMode.WALK,
        from_location="Konspira",
        to_location="Ostrów Tumski",
        start_time="11:00",
        end_time="11:20",
        duration_min=20,
        geometry=[[17.0, 51.1], [17.1, 51.2]],
        geometry_latlng=[[51.1, 17.0], [51.2, 17.1]],
        routing_source="estimated_walk",
    )
    retargeted = svc._retarget_all_legs_to_prev_stop(
        [movie, leg, ostrow], day_num=2,
    )
    trans = [x for x in retargeted if getattr(x, "type", None) == ItemType.TRANSIT]
    assert trans
    assert trans[0].from_location == "Movie Gate"
    assert trans[0].geometry is None
    assert trans[0].geometry_latlng is None

    stamped = svc._finalize_transit_geometry(
        retargeted,
        {},
        {"requested_city": "Wrocław", "has_car": True},
    )
    trans2 = [x for x in stamped if getattr(x, "type", None) == ItemType.TRANSIT]
    assert trans2
    geom = trans2[0].geometry or trans2[0].geometry_latlng
    assert geom and len(geom) >= 2
    issues = audit_transit_routing(stamped)
    assert not any("missing geometry" in i for i in issues)


def test_fix279_lookup_fuzzy_movie_gate():
    svc = _svc()
    hit = svc._lookup_coords(
        {"Movie Gate Wrocław": {"lat": 51.11, "lng": 17.04}},
        "Movie Gate",
    )
    assert hit == (51.11, 17.04)


def test_fix279_return_leg_has_geometry():
    svc = _svc()
    items = [
        _attr(
            "Laboratorium dr. Frankensteina",
            "11:00", "11:40",
            lat=50.589, lng=16.81,
        ),
    ]
    out = svc._ensure_far_excursion_return(
        items,
        {"requested_city": "Wrocław", "day_end": "20:00"},
        day_num=7,
    )
    trans = [x for x in out if getattr(x, "type", None) == ItemType.TRANSIT]
    assert trans
    assert trans[-1].geometry or trans[-1].geometry_latlng


@pytest.mark.slow
def test_fix279_wroclaw_json8_no_missing_geometry():
    json_path = (
        Path(__file__).resolve().parents[2] / "json_miasta" / "Wrocław" / "test-08.json"
    )
    if not json_path.is_file():
        pytest.skip("json_miasta/Wrocław/test-08.json missing")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    excel = Path("data") / "multi_city_attractions.xlsx"
    plan = PlanService(POIRepository(str(excel))).generate_plan(TripInput(**payload))
    issues: list[str] = []
    for day in plan.days:
        for msg in audit_transit_routing(day.items or []):
            if "missing geometry" in msg:
                issues.append(f"day{day.day}: {msg}")
    assert not issues, "; ".join(issues[:12])
