"""FIX #335 - a planted stop belongs to the guest who got it.

The planting pool from #332 was the whole city filtered on distance and a
name denylist, so it handed a couple Park Mamuta, a solo guest Bobolandia and
everyone two bare names with no description. It also squeezed a 90 min
attraction into 30 and called 12:07 dinner.
"""
from __future__ import annotations

import os

os.environ.setdefault("ORS_ENABLED", "false")

from app.application.services.plan_service import PlanService
from app.domain.models.plan import (
    AttractionItem,
    DayEndItem,
    DayStartItem,
    DinnerBreakItem,
    FreeTimeItem,
    ItemType,
    LunchBreakItem,
    RestaurantSuggestion,
    TransitItem,
    TransitMode,
)
from app.infrastructure.repositories.poi_repository import POIRepository

WENA = (50.9329, 17.2924)
RYNEK = (51.1106992, 17.0323662)


def _svc():
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _attr(name, start, end, pt=RYNEK, dur=60):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"poi-{name}",
        name=name,
        description_short="Opis",
        why_selected=["bo warto"],
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=pt[0],
        lng=pt[1],
    )


def _tr(frm, to, start, end, km=1.0, dur=15):
    return TransitItem.model_construct(
        type=ItemType.TRANSIT,
        from_location=frm,
        to_location=to,
        start_time=start,
        end_time=end,
        duration_min=dur,
        distance_km=km,
        mode=TransitMode.CAR,
        routing_source="estimated_road",
    )


def _meal(cls, tv, start, end, name, pt=RYNEK, label="Posiłek"):
    return cls.model_construct(
        type=tv,
        start_time=start,
        end_time=end,
        duration_min=45,
        label=label,
        suggestions=[RestaurantSuggestion.model_construct(
            id=f"r-{name}", name=name, lat=pt[0], lng=pt[1],
            city="Wroclaw", address="",
        )],
    )


def _lunch(start, end, name, pt=RYNEK):
    return _meal(LunchBreakItem, ItemType.LUNCH_BREAK, start, end, name, pt)


def _dinner(start, end, name, pt=RYNEK):
    return _meal(DinnerBreakItem, ItemType.DINNER_BREAK, start, end, name, pt)


def _ft(start, end, label="Czas dla siebie"):
    return FreeTimeItem.model_construct(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=None,
        label=label,
        suggestions=[],
    )


# --- the audience gate the pool never had ---

PARK_MAMUTA = {
    "id": "poi_496",
    "name": "Park Mamuta",
    "kids_only": "yes",
    "target_groups": ["family_kids"],
    "type_of_attraction": "kids_attractions",
    "time_min": 90,
}
# Not on the FIX #197 name denylist, so only the type and the quiz decide.
SALA_ZABAW = {
    "id": "poi_777",
    "name": "Sala Zabaw Fikoland",
    "kids_only": "",
    "target_groups": ["all"],
    "type_of_attraction": "kids_attractions",
    "time_min": 60,
}
MUZEUM = {
    "id": "poi_485",
    "name": "Muzeum Narodowe",
    "kids_only": "",
    "target_groups": ["all"],
    "type_of_attraction": "museum",
    "time_min": 60,
    "time_max": 120,
}


def test_kids_only_poi_is_off_profile_for_a_couple():
    ctx = {"user": {"target_group": "couples", "preferences": ["museum_heritage"]}}
    assert _svc()._plant_poi_off_profile(PARK_MAMUTA, ctx) is True


def test_kids_only_poi_stays_available_for_a_family():
    ctx = {
        "user": {
            "target_group": "family_kids",
            "preferences": ["attractions_for_kids"],
        }
    }
    assert _svc()._plant_poi_off_profile(PARK_MAMUTA, ctx) is False


def test_kids_entertainment_is_off_profile_without_a_kids_preference():
    ctx = {"user": {"target_group": "couples", "preferences": ["museum_heritage"]}}
    assert _svc()._plant_poi_off_profile(SALA_ZABAW, ctx) is True


def test_kids_entertainment_is_fine_for_a_guest_who_asked_for_it():
    ctx = {
        "user": {
            "target_group": "couples",
            "preferences": ["museum_heritage", "theme_parks"],
        }
    }
    assert _svc()._plant_poi_off_profile(SALA_ZABAW, ctx) is False


def test_pixel_xl_stays_denied_for_a_couple_even_with_a_kids_preference():
    """FIX #197 keeps a hard name denylist per group; #335 does not undo it."""
    ctx = {
        "user": {
            "target_group": "couples",
            "preferences": ["theme_parks"],
        }
    }
    pixel = dict(SALA_ZABAW, id="poi_501", name="Pixel XL Wroclaw")
    assert _svc()._plant_poi_off_profile(pixel, ctx) is True


def test_a_museum_is_on_profile_for_everyone():
    ctx = {"user": {"target_group": "solo", "preferences": ["museum_heritage"]}}
    assert _svc()._plant_poi_off_profile(MUZEUM, ctx) is False


# --- the Excel floor decides the visit ---

def test_visit_length_comes_from_the_excel_floor():
    assert _svc()._plant_visit_minutes({"time_min": 90}) == 90


def test_time_max_caps_the_excel_floor():
    assert _svc()._plant_visit_minutes({"time_min": 90, "time_max": 60}) == 60


def test_missing_duration_data_falls_back_to_40_minutes():
    assert _svc()._plant_visit_minutes({}) == 40


# --- nobody eats dinner at 12:07 ---

def test_short_day_dinner_waits_for_the_evening_instead_of_noon():
    """It used to pull the meal to `after_min + 10`, i.e. 12:07 (client J4)."""
    out = _svc()._plant_short_day_dinner(
        [_attr("Bastion Sakwowy", "09:00", "11:57")],
        {"day_end": "18:00"},
        after_min=11 * 60 + 57,
        from_name="Bastion Sakwowy",
        from_pt=RYNEK,
        window_end=18 * 60,
        day_num=4,
    )
    assert out is not None
    dinners = [x for x in out if x.type == ItemType.DINNER_BREAK]
    assert dinners and dinners[0].start_time == "17:15"


def test_short_day_dinner_is_refused_when_the_window_forces_noon():
    out = _svc()._plant_short_day_dinner(
        [_attr("Baszta Miejska w Niemczy", "09:00", "11:41")],
        {"day_end": "13:00"},
        after_min=11 * 60 + 41,
        from_name="Baszta Miejska w Niemczy",
        from_pt=RYNEK,
        window_end=13 * 60,
        day_num=7,
    )
    assert out is None


def test_short_day_dinner_lands_in_the_evening_when_it_can():
    out = _svc()._plant_short_day_dinner(
        [_attr("Bastion Sakwowy", "09:00", "16:45")],
        {"day_end": "20:00"},
        after_min=16 * 60 + 45,
        from_name="Bastion Sakwowy",
        from_pt=RYNEK,
        window_end=20 * 60,
        day_num=4,
    )
    assert out is not None
    dinners = [
        x for x in out if x.type == ItemType.DINNER_BREAK
    ]
    assert dinners and dinners[0].start_time >= "16:55"


# --- a day with nothing left closes instead of parking the guest ---

def _ctx():
    return {"requested_city": "Wroclaw", "day_end": "18:00"}


def test_stranded_dinner_is_dropped_and_the_day_closes_early():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:30"),
        _attr("Hala Targowa", "09:39", "10:16"),
        _attr("Bastion Sakwowy", "11:27", "11:57"),
        _ft("11:57", "17:08"),
        _tr("Bastion Sakwowy", "House of Spices", "17:08", "17:15"),
        _dinner("17:15", "18:00", "House of Spices"),
        DayEndItem(time="18:00"),
    ]
    out, closed = _svc()._close_day_when_nothing_left(items, _ctx(), day_num=4)
    assert closed is True
    assert not [x for x in out if x.type == ItemType.DINNER_BREAK]
    ends = [x for x in out if x.type == ItemType.DAY_END]
    assert ends and ends[0].time == "11:57"


def test_closing_the_day_keeps_the_drive_home():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Muzeum Motoryzacji Wena", "11:02", "12:32", WENA),
        _lunch("12:52", "13:32", "INCANTO Restauracja", WENA),
        _tr("INCANTO Restauracja", "Wroclaw centrum", "13:32", "14:17", km=37.0),
        _ft("14:17", "16:58"),
        _dinner("17:15", "18:00", "Przystanek ze smakiem"),
        DayEndItem(time="18:00"),
    ]
    out, closed = _svc()._close_day_when_nothing_left(items, _ctx(), day_num=6)
    assert closed is True
    homeward = [
        x for x in out
        if x.type == ItemType.TRANSIT and x.to_location == "Wroclaw centrum"
    ]
    assert homeward, "the return drive must survive the early close"
    ends = [x for x in out if x.type == ItemType.DAY_END]
    assert ends and ends[0].time == "14:17"


def test_a_full_day_keeps_its_dinner_two_hours_after_the_last_museum():
    items = [
        DayStartItem(type=ItemType.DAY_START, time="09:00"),
        _attr("Hala Targowa", "09:10", "10:10"),
        _lunch("13:00", "13:45", "Konspira"),
        _attr("Hydropolis", "14:00", "16:00"),
        _dinner("18:00", "18:45", "IDA kuchnia i wino"),
        DayEndItem(time="18:45"),
    ]
    out, closed = _svc()._close_day_when_nothing_left(items, _ctx(), day_num=1)
    assert closed is False
    assert [x for x in out if x.type == ItemType.DINNER_BREAK]
