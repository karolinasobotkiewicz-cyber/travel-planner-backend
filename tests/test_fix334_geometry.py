"""FIX #334 - the polyline starts where the label says it starts.

`_finalize_transit_geometry` runs before the guardian heals the day, so every
hop origin the heal rewrote kept a line drawn out of the previous stop. The
client read that as "transit from: Bastion Sakwowy rozpoczyna geometrie w
wspolrzednych Rynku" (J9 D1, J9 D2, J10 D2, J8 D6, J1 D2).
"""
from __future__ import annotations

import os

os.environ.setdefault("ORS_ENABLED", "false")

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.infrastructure.repositories.poi_repository import POIRepository
from app.infrastructure.routing.haversine import haversine_km

RYNEK = (51.1106992, 17.0323662)
BASTION = (51.1048491, 17.0385071)
NEON = (51.1099655, 17.0245627)
GONDOLI = (51.1112136, 17.0465482)
BOTANICZNY = (51.108056, 17.073056)


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _attr(name, start, end, pt):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"poi-{name}",
        name=name,
        description_short="Opis",
        start_time=start,
        end_time=end,
        duration_min=None,
        lat=pt[0],
        lng=pt[1],
    )


def _tr(frm, to, start, end, *, geom_from, geom_to, km=1.0, dur=15):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=TransitMode.WALK,
        routing_source="estimated_walk",
        geometry=[
            [geom_from[1], geom_from[0]], [geom_to[1], geom_to[0]],
        ],
        geometry_latlng=[list(geom_from), list(geom_to)],
    )


def _lunch(start, end, name, pt):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start,
        end_time=end,
        duration_min=None,
        label="Lunch",
        suggestions=[RestaurantSuggestion.model_construct(
            id=f"r-{name}", name=name, lat=pt[0], lng=pt[1],
            city="Wroclaw", address="",
        )],
        location_context="",
    )


def _ends(leg):
    gll = leg.geometry_latlng
    return (
        (float(gll[0][0]), float(gll[0][1])),
        (float(gll[-1][0]), float(gll[-1][1])),
    )


def _ctx():
    return {"requested_city": "Wroclaw", "day_end": "20:00"}


def test_leg_drawn_from_the_previous_stop_is_restamped_onto_its_label():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wroclawiu", "09:00", "10:00", RYNEK),
        _tr("Rynek we Wroclawiu", "Bastion Sakwowy", "10:00", "10:15",
            geom_from=RYNEK, geom_to=BASTION),
        _attr("Bastion Sakwowy", "10:15", "11:15", BASTION),
        # The heal renamed this origin; the polyline still leaves the Rynek.
        _tr("Bastion Sakwowy", "IDA kuchnia i wino", "11:15", "11:30",
            geom_from=RYNEK, geom_to=RYNEK),
        _lunch("11:30", "12:20", "IDA kuchnia i wino", BASTION),
        DayEndItem(time="12:20"),
    ]
    out = _svc()._seal_transit_geometry_to_timeline(items, _ctx(), day_num=1)
    leg = [
        x for x in out
        if x.type == ItemType.TRANSIT
        and x.from_location == "Bastion Sakwowy"
    ][0]
    start, end = _ends(leg)
    assert haversine_km(start[0], start[1], BASTION[0], BASTION[1]) <= 0.05
    assert haversine_km(end[0], end[1], BASTION[0], BASTION[1]) <= 0.05


def test_honest_leg_keeps_its_polyline_untouched():
    original = _tr(
        "Galeria Neon Side", "Zatoka Gondoli", "10:00", "10:20",
        geom_from=NEON, geom_to=GONDOLI,
    )
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Galeria Neon Side", "09:00", "10:00", NEON),
        original,
        _attr("Zatoka Gondoli", "10:20", "11:20", GONDOLI),
        DayEndItem(time="11:20"),
    ]
    out = _svc()._seal_transit_geometry_to_timeline(items, _ctx(), day_num=2)
    leg = [x for x in out if x.type == ItemType.TRANSIT][0]
    assert _ends(leg) == _ends(original)


def test_leg_out_of_the_botanic_garden_no_longer_leaves_the_rynek():
    """Client J10 D2: Ogrod Botaniczny -> Chinkalnia starts at the Rynek."""
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wroclawiu", "09:00", "10:00", RYNEK),
        _tr("Rynek we Wroclawiu", "Ogrod Botaniczny", "10:00", "10:20",
            geom_from=RYNEK, geom_to=BOTANICZNY),
        _attr("Ogrod Botaniczny", "10:20", "11:50", BOTANICZNY),
        _tr("Ogrod Botaniczny", "Chinkalnia", "11:50", "12:10",
            geom_from=RYNEK, geom_to=RYNEK),
        _lunch("12:10", "13:00", "Chinkalnia", RYNEK),
        DayEndItem(time="13:00"),
    ]
    out = _svc()._seal_transit_geometry_to_timeline(items, _ctx(), day_num=2)
    leg = [
        x for x in out
        if x.type == ItemType.TRANSIT and x.to_location == "Chinkalnia"
    ][0]
    start, _end = _ends(leg)
    off = haversine_km(start[0], start[1], BOTANICZNY[0], BOTANICZNY[1])
    assert off <= 0.05, f"leg still starts {off:.2f} km from the garden"


def test_hub_origin_resolves_to_the_city_centre_and_is_left_alone():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wroclaw centrum", "Bastion Sakwowy", "09:00", "09:20",
            geom_from=RYNEK, geom_to=BASTION),
        _attr("Bastion Sakwowy", "09:20", "10:20", BASTION),
        DayEndItem(time="10:20"),
    ]
    out = _svc()._seal_transit_geometry_to_timeline(items, _ctx(), day_num=1)
    leg = [x for x in out if x.type == ItemType.TRANSIT][0]
    start, end = _ends(leg)
    # Wroclaw centre is the Rynek, so the drawn line was already honest.
    assert haversine_km(start[0], start[1], RYNEK[0], RYNEK[1]) <= 1.0
    assert haversine_km(end[0], end[1], BASTION[0], BASTION[1]) <= 0.05


def test_leg_without_any_polyline_gets_one_from_the_timeline():
    leg = TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location="Bastion Sakwowy",
        to_location="Galeria Neon Side",
        start_time="10:15",
        end_time="10:35",
        duration_min=20,
        distance_km=1.4,
        mode=TransitMode.WALK,
        routing_source="estimated_walk",
    )
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Bastion Sakwowy", "09:00", "10:15", BASTION),
        leg,
        _attr("Galeria Neon Side", "10:35", "11:35", NEON),
        DayEndItem(time="11:35"),
    ]
    out = _svc()._seal_transit_geometry_to_timeline(items, _ctx(), day_num=1)
    sealed = [x for x in out if x.type == ItemType.TRANSIT][0]
    start, end = _ends(sealed)
    assert haversine_km(start[0], start[1], BASTION[0], BASTION[1]) <= 0.05
    assert haversine_km(end[0], end[1], NEON[0], NEON[1]) <= 0.05
