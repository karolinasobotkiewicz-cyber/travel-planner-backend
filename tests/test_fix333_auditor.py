"""FIX #333 — auditor learns the third client mail.

The polyline the front end draws, the audience of a stop, the narrative the
guest reads, the Excel duration floor and the spacing between two meals.
Synthetic timelines only, no generate_plan.
"""
from __future__ import annotations

from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    DinnerBreakItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.domain.validators.client_invariants import audit_day

# Real Wrocław coordinates from the client mail.
RYNEK = (51.1106992, 17.0323662)
BASTION = (51.1048491, 17.0385071)
NEON = (51.1099655, 17.0245627)
GONDOLI = (51.1112136, 17.0465482)


def _attr(name, start, end, dur=60, *, pt=RYNEK, desc="Opis", why=("bo tak",)):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short=desc,
        why_selected=list(why),
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=pt[0],
        lng=pt[1],
        address="Wrocław",
        city="Wrocław",
        cost_estimate=0,
    )


def _tr(frm, to, start, end, *, km=1.0, dur=10, geom_from=None, geom_to=None):
    upd = {}
    if geom_from and geom_to:
        # GeoJSON keeps [lng, lat]; the twin field keeps [lat, lng].
        upd["geometry"] = [
            [geom_from[1], geom_from[0]], [geom_to[1], geom_to[0]],
        ]
        upd["geometry_latlng"] = [list(geom_from), list(geom_to)]
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
        **upd,
    )


def _sug(name, *, pt=RYNEK):
    return RestaurantSuggestion.model_construct(
        id=f"id-{name}", name=name, lat=pt[0], lng=pt[1],
        city="Wrocław", address="",
    )


def _lunch(start, end, dur, sugs=(), label="Lunch / przerwa regeneracyjna"):
    return LunchBreakItem.model_construct(
        type=ItemType.LUNCH_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=list(sugs), label=label, location_context="",
    )


def _dinner(start, end, dur, sugs=(), label="Kolacja"):
    return DinnerBreakItem.model_construct(
        type=ItemType.DINNER_BREAK,
        start_time=start, end_time=end, duration_min=dur,
        suggestions=list(sugs), label=label,
    )


def _codes(items, **kwargs):
    return {d.code for d in audit_day(items, **kwargs)}


def _ctx(**extra):
    base = {
        "day_start": "09:00",
        "day_end": "20:00",
        "requested_city": "Wrocław",
        "has_car": True,
    }
    base.update(extra)
    return base


# --- J9 D1: "transit from: Bastion Sakwowy rozpoczyna geometrię z Rynku" ---

def test_polyline_starting_at_the_previous_stop_is_a_geom_mismatch():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "09:00", "10:00", pt=RYNEK),
        _tr("Rynek we Wrocławiu", "Bastion Sakwowy", "10:00", "10:15",
            geom_from=RYNEK, geom_to=BASTION),
        _attr("Bastion Sakwowy", "10:15", "11:15", pt=BASTION),
        # The label says Bastion, the drawn line still starts at the Rynek.
        _tr("Bastion Sakwowy", "IDA kuchnia i wino", "11:15", "11:30",
            geom_from=RYNEK, geom_to=RYNEK),
        _lunch("11:30", "12:20", 50, [_sug("IDA kuchnia i wino")]),
        DayEndItem(time="12:20"),
    ]
    defects = [
        d for d in audit_day(items, day=1, context=_ctx())
        if d.code == "geom_from_mismatch"
    ]
    assert len(defects) == 1
    assert defects[0].meta["label"] == "Bastion Sakwowy"
    assert defects[0].meta["off_km"] > 0.6


def test_polyline_that_matches_its_own_labels_is_clean():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Galeria Neon Side", "09:00", "10:00", pt=NEON),
        _tr("Galeria Neon Side", "Zatoka Gondoli", "10:00", "10:20",
            geom_from=NEON, geom_to=GONDOLI),
        _attr("Zatoka Gondoli", "10:20", "11:20", pt=GONDOLI),
        DayEndItem(time="11:20"),
    ]
    codes = _codes(items, day=1, context=_ctx())
    assert "geom_from_mismatch" not in codes
    assert "geom_to_mismatch" not in codes


def test_polyline_ending_far_from_its_destination_is_flagged():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Galeria Neon Side", "09:00", "10:00", pt=NEON),
        _tr("Galeria Neon Side", "Zatoka Gondoli", "10:00", "10:20",
            geom_from=NEON, geom_to=RYNEK),
        _attr("Zatoka Gondoli", "10:20", "11:20", pt=GONDOLI),
        DayEndItem(time="11:20"),
    ]
    assert "geom_to_mismatch" in _codes(items, day=1, context=_ctx())


def test_hub_labels_carry_no_poi_coordinates_and_are_skipped():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _tr("Wrocław centrum", "Bastion Sakwowy", "09:00", "09:20",
            geom_from=RYNEK, geom_to=BASTION),
        _attr("Bastion Sakwowy", "09:20", "10:20", pt=BASTION),
        DayEndItem(time="10:20"),
    ]
    assert "geom_from_mismatch" not in _codes(items, day=1, context=_ctx())


# --- J4 D3: the ride goes to Emily, the lunch is signed Renesans ---

def test_ride_to_one_restaurant_and_a_meal_named_another_is_flagged():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hala Targowa", "09:00", "10:00"),
        _tr("Hala Targowa", "Emily. Italian Stories", "10:00", "10:15"),
        _lunch("10:15", "11:05", 50, [_sug("Renesans. Restauracja")]),
        DayEndItem(time="11:05"),
    ]
    assert "hop_to_vs_meal" in _codes(items, day=3, context=_ctx())


def test_ride_to_the_restaurant_it_serves_is_clean():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hala Targowa", "09:00", "10:00"),
        _tr("Hala Targowa", "Emily. Italian Stories", "10:00", "10:15"),
        _lunch("10:15", "11:05", 50, [_sug("Emily. Italian Stories")]),
        DayEndItem(time="11:05"),
    ]
    assert "hop_to_vs_meal" not in _codes(items, day=3, context=_ctx())


# --- J8 D5: Kosmopark and Dom Krasnali with no description, no why_selected ---

def test_stop_without_description_or_reason_is_empty_narrative():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Kosmopark Wrocław", "09:00", "10:00", desc="", why=()),
        DayEndItem(time="10:00"),
    ]
    defects = [
        d for d in audit_day(items, day=5, context=_ctx())
        if d.code == "empty_narrative"
    ]
    assert len(defects) == 1
    assert "description_short" in defects[0].meta["missing"]
    assert "why_selected" in defects[0].meta["missing"]


def test_missing_reason_alone_is_still_empty_narrative():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Dom Krasnali", "09:00", "10:00", desc="Opis jest", why=()),
        DayEndItem(time="10:00"),
    ]
    assert "empty_narrative" in _codes(items, day=5, context=_ctx())


def test_described_stop_is_clean():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hydropolis", "09:00", "10:00"),
        DayEndItem(time="10:00"),
    ]
    assert "empty_narrative" not in _codes(items, day=1, context=_ctx())


# --- J2/J3/J8: Park Mamuta and Bobolandia for a couple / for friends ---

def _kids_meta(name, **extra):
    from app.domain.validators.client_invariants import _fold
    entry = {"target_groups": ["family_kids"], "kids_only": "yes"}
    entry.update(extra)
    return {_fold(name): entry}


def test_kids_only_stop_for_a_couple_is_flagged():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Park Mamuta", "09:00", "10:00"),
        DayEndItem(time="10:00"),
    ]
    ctx = _ctx(group_type="couples", poi_meta=_kids_meta("Park Mamuta"))
    assert "kids_only_for_adults" in _codes(items, day=1, context=ctx)


def test_kids_only_stop_for_a_family_is_fine():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Park Mamuta", "09:00", "10:00"),
        DayEndItem(time="10:00"),
    ]
    ctx = _ctx(group_type="family_kids", poi_meta=_kids_meta("Park Mamuta"))
    assert "kids_only_for_adults" not in _codes(items, day=1, context=ctx)


def test_kids_entertainment_against_a_culture_quiz_is_profile_mismatch():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Pixel XL Wrocław", "09:00", "10:00"),
        DayEndItem(time="10:00"),
    ]
    ctx = _ctx(
        group_type="couples",
        preferences=["museum_heritage", "relaxation"],
        poi_meta=_kids_meta(
            "Pixel XL Wrocław",
            target_groups=["all"],
            kids_only="",
            type_of_attraction="kids_attractions",
        ),
    )
    assert "profile_mismatch" in _codes(items, day=1, context=ctx)


def test_kids_entertainment_for_a_guest_who_asked_for_it_is_fine():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Pixel XL Wrocław", "09:00", "10:00"),
        DayEndItem(time="10:00"),
    ]
    ctx = _ctx(
        group_type="couples",
        preferences=["museum_heritage", "attractions_for_kids"],
        poi_meta=_kids_meta(
            "Pixel XL Wrocław",
            target_groups=["all"],
            kids_only="",
            type_of_attraction="kids_attractions",
        ),
    )
    assert "profile_mismatch" not in _codes(items, day=1, context=ctx)


# --- J1 D3: "Loopy's World tylko 30 min – może być spokojnie na 90 min" ---

def test_visit_far_below_the_excel_floor_is_flagged():
    from app.domain.validators.client_invariants import _fold
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Park Rozrywki Loopy's World", "09:00", "09:30", 30),
        DayEndItem(time="09:30"),
    ]
    ctx = _ctx(poi_meta={
        _fold("Park Rozrywki Loopy's World"): {"time_min": 90, "time_max": 120},
    })
    defects = [
        d for d in audit_day(items, day=3, context=ctx)
        if d.code == "under_time_min"
    ]
    assert len(defects) == 1
    assert defects[0].meta["time_min"] == 90


def test_visit_close_to_the_excel_floor_is_accepted():
    from app.domain.validators.client_invariants import _fold
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Park Rozrywki Loopy's World", "09:00", "10:10", 70),
        DayEndItem(time="10:10"),
    ]
    ctx = _ctx(poi_meta={
        _fold("Park Rozrywki Loopy's World"): {"time_min": 90, "time_max": 120},
    })
    assert "under_time_min" not in _codes(items, day=3, context=ctx)


# --- J8 D6: lunch to 13:52, "Kolacja" at 14:37. J8 D7: dinner at 11:40 ---

def test_dinner_45_minutes_after_lunch_is_not_a_second_meal():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Motoryzacji Wena", "09:00", "13:12"),
        _lunch("13:12", "13:52", 40, [_sug("INCANTO Restauracja")]),
        _tr("INCANTO Restauracja", "Wrocław centrum", "13:52", "14:37",
            km=37.0, dur=45),
        _dinner("14:37", "15:22", 45, [_sug("Konspira")]),
        DayEndItem(time="15:22"),
    ]
    codes = _codes(items, day=6, context=_ctx())
    assert "meal_too_close" in codes
    assert "early_dinner" in codes


def test_dinner_before_noon_on_a_full_window_is_early_dinner():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Bastion Sakwowy", "09:00", "10:00", pt=BASTION),
        _tr("Bastion Sakwowy", "Muzeum Narodowe", "10:00", "10:15",
            geom_from=BASTION, geom_to=BASTION),
        _attr("Muzeum Narodowe", "10:15", "11:40", 85, pt=BASTION),
        _dinner("11:40", "12:25", 45, [_sug("Konspira")]),
        DayEndItem(time="12:25"),
    ]
    assert "early_dinner" in _codes(items, day=7, context=_ctx())


def test_dinner_at_18_with_lunch_at_13_is_clean():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Rynek we Wrocławiu", "09:00", "13:00", 240),
        _lunch("13:00", "13:45", 45, [_sug("Konspira")]),
        _attr("Hydropolis", "14:00", "17:30", 210),
        _dinner("18:00", "18:50", 50, [_sug("IDA kuchnia i wino")]),
        DayEndItem(time="18:50"),
    ]
    codes = _codes(items, day=1, context=_ctx())
    assert "meal_too_close" not in codes
    assert "early_dinner" not in codes
