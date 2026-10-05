"""FIX #367: Tricity smoke gate — hard-fail owned validator codes on synthetic day.

Full 10-JSON city audit stays optional (slow). This gate seals the defect classes
without reopening Wroclaw / Zakopane / existing KRK/KAT/POZ gates.
"""
from __future__ import annotations

from app.domain.models.plan import (
    AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
)
from scripts.plan_quality_validator import Report, validate_day

OWNED = {
    "stale_walk_start",
    "implausible_walk",
    "generic_hub",
    "cross_city_poi",
    "duplicate_coords_poi",
    "missing_dinner",
    "late_lunch",
    "day_past_window",
    "zero_duration_clip",
    "aba_return_loop",
}


def test_trojmiasto_validator_codes_detect_synthetic_defects():
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Neptun",
            description_short="x", why_selected=["x"],
            start_time="09:30", end_time="10:30", duration_min=60,
            lat=54.3486, lng=18.6532, city="Gdańsk",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Neptun", to_location="Gdańsk",
            mode=TransitMode.WALK, distance_km=0.5,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="loopy",
            name="Park Rozrywki Loopy's World",
            description_short="x", why_selected=["x"],
            start_time="12:00", end_time="13:00", duration_min=60,
            lat=51.07, lng=17.04, city="Wrocław",
        ),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(city="Gdańsk", num=1, day_num=1, items=items, report=report)
    owned_hits = [h for h in report.hits if h.code in OWNED]
    # Gate passes when the validator *can* see the defect classes on a dirty day.
    assert owned_hits, report.hits
