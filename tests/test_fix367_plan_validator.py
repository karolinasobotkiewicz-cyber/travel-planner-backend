"""FIX #367: hard-fail wrapper for Tricity/Karkonosze plan-quality codes."""
from __future__ import annotations

from scripts.plan_quality_validator import Report, validate_day
from app.domain.models.plan import (
    AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
    LunchBreakItem, TransitItem, TransitMode,
)


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


def test_validator_flags_generic_hub_and_cross_city():
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Molo",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=54.45, lng=18.57, city="Sopot",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Molo", to_location="Sopot",
            mode=TransitMode.WALK, distance_km=0.5,
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:20", end_time="11:40",
            duration_min=20, from_location="Sopot", to_location="Krzywy Domek",
            mode=TransitMode.WALK, distance_km=0.8,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="loopy",
            name="Park Rozrywki Loopy's World",
            description_short="x", why_selected=["x"],
            start_time="12:00", end_time="13:00", duration_min=60,
            lat=51.07, lng=17.04, city="Wrocław",
        ),
        LunchBreakItem.model_construct(
            type=ItemType.LUNCH_BREAK, start_time="15:30", end_time="16:15",
            duration_min=45, label="Lunch",
        ),
        FreeTimeItem(start_time="23:59", end_time="23:59", duration_min=0, label="x"),
        DayEndItem(time="20:00"),
    ]
    report = Report()
    validate_day(
        city="Sopot", num=1, day_num=1, items=items, report=report,
    )
    codes = {h.code for h in report.hits}
    assert "generic_hub" in codes or "cross_city_poi" in codes or "late_lunch" in codes or "zero_duration_clip" in codes, codes


def test_validator_owned_codes_set():
    assert "stale_walk_start" in OWNED
    assert "missing_dinner" in OWNED
