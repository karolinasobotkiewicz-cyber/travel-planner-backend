"""FIX #238 — client feedback 22.07.2026.

Covers:
  * routing_source never null and never raw 'haversine' on drives (issues 3 & 4)
  * no attraction ends exactly when the next (different location) begins (issue 5)
  * seasonal attractions never survive into an off-season day (issue 6)
"""
from __future__ import annotations

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    ItemType,
    ParkingInfo,
    ParkingType,
    TicketInfo,
    TransitItem,
    TransitMode,
)
from app.domain.planner.time_utils import time_to_minutes


def _svc() -> PlanService:
    return PlanService(poi_repository=None)


def _attr(name: str, start: str, end: str, lat: float, lng: float) -> AttractionItem:
    return AttractionItem(
        type=ItemType.ATTRACTION,
        poi_id=f"p_{name}",
        name=name,
        start_time=start,
        end_time=end,
        duration_min=time_to_minutes(end) - time_to_minutes(start),
        description_short="t",
        lat=lat,
        lng=lng,
        address="a",
        city="Wrocław",
        cost_estimate=0,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0),
        parking=ParkingInfo(name="P", walk_time_min=5, parking_type=ParkingType.FREE),
    )


def _transit(frm: str, to: str, start: str, end: str, mode: TransitMode) -> TransitItem:
    return TransitItem(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=time_to_minutes(end) - time_to_minutes(start),
        mode=mode,
    )


# ---------------------------------------------------------------------------
# Issue 3 & 4 — routing_source
# ---------------------------------------------------------------------------
def test_enrich_transit_resolves_coords_from_attraction_items():
    """Transit endpoints missing from poi_coords are resolved from the day's items."""
    svc = _svc()
    items = [
        _attr("A", "10:00", "11:00", 50.06, 19.94),
        _transit("A", "B", "11:00", "11:20", TransitMode.CAR),
        _attr("B", "11:20", "12:20", 50.09, 19.99),
    ]
    # poi_coords intentionally EMPTY — must fall back to attraction coords.
    out = svc._enrich_transits_with_routing(items, {}, {"has_car": True})
    tr = next(it for it in out if it.type == ItemType.TRANSIT)
    assert tr.routing_source is not None
    assert tr.routing_source != "haversine"
    assert tr.geometry  # straight-line geometry attached


def test_enrich_transit_never_null_even_without_coords():
    """A hotel/label leg with no resolvable coords still gets a non-null source."""
    svc = _svc()
    items = [
        _transit("Hotel", "A", "09:00", "09:15", TransitMode.CAR),
        _attr("A", "09:15", "10:15", 50.06, 19.94),
    ]
    out = svc._enrich_transits_with_routing(items, {}, {"has_car": True})
    tr = next(it for it in out if it.type == ItemType.TRANSIT)
    assert tr.routing_source == "estimated_road"


def test_enrich_walk_transit_source_non_null():
    svc = _svc()
    items = [_transit("Hotel", "A", "09:00", "09:10", TransitMode.WALK)]
    out = svc._enrich_transits_with_routing(items, {}, {"has_car": True})
    assert out[0].routing_source == "estimated_walk"


# ---------------------------------------------------------------------------
# Issue 5 — no zero-gap between different-location attractions
# ---------------------------------------------------------------------------
def test_no_zero_gap_between_distant_attractions():
    svc = _svc()
    # A ends exactly when B starts, yet they are ~4 km apart.
    items = [
        _attr("A", "10:00", "11:00", 50.06, 19.94),
        _attr("B", "11:00", "12:00", 50.09, 19.99),
    ]
    poi_coords = {
        "A": {"name": "A", "lat": 50.06, "lng": 19.94},
        "B": {"name": "B", "lat": 50.09, "lng": 19.99},
    }
    ctx = {"has_car": True, "day_end": "20:00"}
    out = svc._ensure_transits_between_attractions(items, poi_coords, ctx)

    transits = [it for it in out if it.type == ItemType.TRANSIT]
    assert len(transits) == 1, "expected a transit injected between A and B"

    attr_a = next(it for it in out if getattr(it, "name", "") == "A")
    attr_b = next(it for it in out if getattr(it, "name", "") == "B")
    # B must no longer start at the exact minute A ends.
    assert time_to_minutes(attr_b.start_time) > time_to_minutes(attr_a.end_time)
    # The transit fills the newly created gap.
    tr = transits[0]
    assert time_to_minutes(tr.start_time) == time_to_minutes(attr_a.end_time)
    assert time_to_minutes(tr.end_time) <= time_to_minutes(attr_b.start_time)


def test_shift_items_from_moves_tail_forward():
    svc = _svc()
    items = [
        _attr("A", "10:00", "11:00", 50.06, 19.94),
        _attr("B", "11:00", "12:00", 50.09, 19.99),
    ]
    out = svc._shift_items_from(items, 1, 15)
    assert out[0].start_time == "10:00"  # untouched
    assert out[1].start_time == "11:15"
    assert out[1].end_time == "12:15"


# ---------------------------------------------------------------------------
# Issue 6 — seasonal filtering
# ---------------------------------------------------------------------------
def _winter_ctx():
    # (year, month, day, weekday) — January = deep winter.
    return {"date": (2026, 1, 15, 3)}


def test_poi_out_of_season_summer_only_in_winter():
    svc = _svc()
    summer_poi = {
        "id": "s1",
        "name": "Rejs statkiem",
        "season_fit": {"winter": 0, "spring": 0, "summer": 1, "autumn": 0},
    }
    assert svc._poi_out_of_season(summer_poi, _winter_ctx()) is True


def test_poi_in_season_all_year():
    svc = _svc()
    year_round = {
        "id": "y1",
        "name": "Muzeum",
        "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1},
    }
    assert svc._poi_out_of_season(year_round, _winter_ctx()) is False


def test_strip_out_of_season_removes_summer_attraction_in_winter():
    svc = _svc()
    items = [
        _attr("Muzeum", "10:00", "11:00", 50.06, 19.94),
        _attr("Rejs statkiem", "11:30", "12:30", 50.09, 19.99),
    ]
    poi_by_id = {
        "p_Muzeum": {
            "id": "p_Muzeum",
            "name": "Muzeum",
            "season_fit": {"winter": 1, "spring": 1, "summer": 1, "autumn": 1},
        },
        "p_Rejs statkiem": {
            "id": "p_Rejs statkiem",
            "name": "Rejs statkiem",
            "season_fit": {"winter": 0, "spring": 0, "summer": 1, "autumn": 0},
        },
    }
    out = svc._strip_out_of_season_attractions(items, (2026, 1, 15, 3), poi_by_id)
    names = [getattr(it, "name", "") for it in out if it.type == ItemType.ATTRACTION]
    assert "Muzeum" in names
    assert "Rejs statkiem" not in names
