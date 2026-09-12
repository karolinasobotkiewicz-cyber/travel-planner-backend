"""FIX #330 - kilometres from the coordinates, minutes from the Excel.

Client: "planner twierdzi, ze z Muzeum Swiat Iluzji do Hydropolis jest 0,096 km
i 2 min pieszo", "Hydropolis - The Cork: podaje 0,862 km, a to 2,1 km",
"Rynek - Taste: 5,79 km samochodem, mimo ze leza blisko siebie w centrum",
"Browar Stu Mostow - Konspira: 48 metrow, a to zupelnie rozne czesci miasta",
"Rynek przez 115 minut jest slabym fillerem dla rodziny z 8-latkiem".
"""
from __future__ import annotations

import os

os.environ.setdefault("ORS_ENABLED", "false")

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    TransitItem,
    TransitMode,
)
from app.domain.validators.client_invariants import audit_day
from app.infrastructure.repositories.poi_repository import POIRepository

# Rynek we Wroclawiu, Hydropolis, Browar Stu Mostow.
RYNEK = (51.1100, 17.0313)
HYDRO = (51.1035, 17.0572)
BROWAR = (51.1240, 17.0405)


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _attr(name, start, end, pt, pid="poi-1", time_max=None):
    it = AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=pid,
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=None,
        lat=pt[0],
        lng=pt[1],
    )
    it.duration_min = time_max
    return it


def _hop(frm, to, start, end, km, mode=TransitMode.WALK):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=None,
        distance_km=km,
        mode=mode,
        routing_source="estimated_walk",
    )


def _day(*items):
    return list(items)


# --------------------------------------------------------------- auditor


def _hop_defects(items):
    return [
        d for d in audit_day(items, day=1, context={"city": "Wroclaw"})
        if d.code == "hop_vs_coords"
    ]


def test_auditor_flags_a_leg_shorter_than_the_straight_line():
    """0.096 km between two points 1.8 km apart is not a rounding error."""
    items = _day(
        _attr("Hydropolis", "09:00", "10:30", HYDRO),
        _hop("Hydropolis", "Rynek we Wroclawiu", "10:30", "10:32", 0.096),
        _attr("Rynek we Wroclawiu", "10:32", "11:10", RYNEK, pid="poi-2"),
    )
    got = _hop_defects(items)
    assert len(got) == 1
    assert got[0].meta["declared_km"] == 0.096
    assert got[0].meta["real_km"] > 1.5


def test_auditor_flags_a_leg_far_longer_than_the_straight_line():
    """5.79 km by car between two central points is a detour nobody drives."""
    items = _day(
        _attr("Rynek we Wroclawiu", "09:00", "10:00", RYNEK),
        _hop(
            "Rynek we Wroclawiu", "Taste", "10:00", "10:18", 5.79,
            mode=TransitMode.CAR,
        ),
        _attr("Taste", "10:18", "11:00", (51.1124, 17.0330), pid="poi-2"),
    )
    got = _hop_defects(items)
    assert len(got) == 1
    assert got[0].meta["declared_km"] == 5.79


def test_auditor_accepts_a_road_slightly_longer_than_the_straight_line():
    """Streets bend; a plausible detour is not a defect."""
    items = _day(
        _attr("Rynek we Wroclawiu", "09:00", "10:00", RYNEK),
        _hop("Rynek we Wroclawiu", "Browar Stu Mostow", "10:00", "10:20", 2.1,
             mode=TransitMode.CAR),
        _attr("Browar Stu Mostow", "10:20", "11:00", BROWAR, pid="poi-2"),
    )
    assert _hop_defects(items) == []


# ---------------------------------------------------------------- engine


def _reconciled(items, has_car=True):
    out = _svc()._reconcile_leg_distances(
        items, day_num=1, context={"city": "Wroclaw", "has_car": has_car},
    )
    return [x for x in out if x.type == ItemType.TRANSIT][0]


def test_engine_rewrites_a_leg_shorter_than_the_straight_line():
    items = _day(
        _attr("Hydropolis", "09:00", "10:30", HYDRO),
        _hop("Hydropolis", "Rynek we Wroclawiu", "10:30", "10:32", 0.096),
        _attr("Rynek we Wroclawiu", "10:32", "11:10", RYNEK, pid="poi-2"),
    )
    leg = _reconciled(items)
    assert leg.distance_km > 1.8
    # Over 2.2 km with a car is a ride, same rule as _honest_transit_physics.
    assert leg.mode == TransitMode.CAR
    assert leg.duration_min >= 8
    assert leg.end_time > "10:32"


def test_engine_rewrites_an_overstated_leg_and_walks_it():
    """1 km apart means a walk, not 5.79 km of driving."""
    items = _day(
        _attr("Rynek we Wroclawiu", "09:00", "10:00", RYNEK),
        _hop(
            "Rynek we Wroclawiu", "Taste", "10:00", "10:18", 5.79,
            mode=TransitMode.CAR,
        ),
        _attr("Taste", "10:18", "11:00", (51.1124, 17.0330), pid="poi-2"),
    )
    leg = _reconciled(items)
    assert leg.distance_km < 1.2
    assert leg.mode == TransitMode.WALK
    assert _hop_defects([items[0], leg, items[2]]) == []


def test_engine_leaves_an_honest_leg_untouched():
    items = _day(
        _attr("Rynek we Wroclawiu", "09:00", "10:00", RYNEK),
        _hop("Rynek we Wroclawiu", "Browar Stu Mostow", "10:00", "10:20", 2.1,
             mode=TransitMode.CAR),
        _attr("Browar Stu Mostow", "10:20", "11:00", BROWAR, pid="poi-2"),
    )
    leg = _reconciled(items)
    assert leg.distance_km == 2.1
    assert leg.duration_min is None


def test_engine_keeps_a_long_leg_on_foot_without_a_car():
    items = _day(
        _attr("Hydropolis", "09:00", "10:30", HYDRO),
        _hop("Hydropolis", "Browar Stu Mostow", "10:30", "10:32", 0.05),
        _attr("Browar Stu Mostow", "10:32", "11:10", BROWAR, pid="poi-2"),
    )
    leg = _reconciled(items, has_car=False)
    assert leg.mode == TransitMode.WALK


# ------------------------------------------------------------ visit caps


def _capped(items, **ctx):
    base = {"city": "Wroclaw", "poi_pool": ctx.pop("pool", [])}
    base.update(ctx)
    out = _svc()._cap_visit_durations(items, base, day_num=1)
    return [x for x in out if x.type == ItemType.ATTRACTION][0]


def test_visit_is_capped_by_the_excel_time_max():
    """Most Grunwaldzki carries time_max=40 and was given 90 minutes."""
    pool = [{"id": "poi-9", "name": "Most Grunwaldzki", "time_max": 40}]
    items = _day(_attr("Most Grunwaldzki", "09:00", "10:30", RYNEK, pid="poi-9"))
    assert _capped(items, pool=pool).end_time == "09:40"


def test_a_square_is_capped_at_an_hour():
    items = _day(_attr("Rynek we Wroclawiu", "09:00", "10:55", RYNEK))
    assert _capped(items).end_time == "10:00"


def test_a_square_is_capped_at_forty_minutes_for_a_family_with_a_child():
    """Client J1 D2: 115 min on the market square with an eight-year-old."""
    items = _day(_attr("Rynek we Wroclawiu", "09:00", "10:55", RYNEK))
    got = _capped(items, group_type="family_kids", children_age=[8])
    assert got.end_time == "09:40"


def test_a_museum_within_its_time_max_is_untouched():
    pool = [{"id": "poi-1", "name": "Hydropolis", "time_max": 120}]
    items = _day(_attr("Hydropolis", "09:00", "10:30", HYDRO))
    assert _capped(items, pool=pool).end_time == "10:30"
