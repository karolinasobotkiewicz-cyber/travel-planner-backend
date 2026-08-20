"""FIX #280 — Wrocław json8 round 2: day_end truth, returns, gaps, duplicates.

Client report this round:
  1. day_end must never precede the real end of the plan (D3 16:35 vs dinner
     18:00–19:00) and must not linger hours past it either (D1 20:00 vs 15:39).
  2. D1 shows no drive back Ślęza → Wrocław after Topacz.
  3. D2 stacks two free_time blocks after dinner, one labelled "w środku dnia".
  4. D3 walk leg carries routing_source=estimated_road.
  5. D4 misses Wrocław → Oława and leaves gaps between free_time blocks.
  6. D6 gives 3 h to the Niemcza market square and hides Niemcza → Wrocław.
  7. D7 has nothing between 13:30 and 19:00 and repeats one restaurant twice.
"""
from __future__ import annotations

from app.application.services.plan_service import (
    PlanService,
    _fold_place_label,
    _is_near_satellite_stop_name,
    _is_olawa_stop_name,
    _satellite_market_square_cap,
)
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

CTX = {
    "num_days": 7,
    "day_start": "09:00",
    "day_end": "20:00",
    "requested_city": "Wrocław",
    "season": "winter",
}


def _svc() -> PlanService:
    return PlanService.__new__(PlanService)


def _attr(name, start, end, dur, *, lat=51.11, lng=17.03):
    return AttractionItem.model_construct(
        type=ItemType.ATTRACTION,
        poi_id=f"id-{name}",
        name=name,
        description_short="",
        start_time=start,
        end_time=end,
        duration_min=dur,
        lat=lat,
        lng=lng,
        address="",
        cost_estimate=0,
    )


def _ft(start, end, dur, label="Czas dla siebie"):
    return FreeTimeItem(
        type=ItemType.FREE_TIME,
        start_time=start,
        end_time=end,
        duration_min=dur,
        label=label,
        suggestions=[],
    )


def _meal(cls, tv, start, end, dur, name, *, lat=51.11, lng=17.03):
    return cls.model_construct(
        type=tv,
        start_time=start,
        end_time=end,
        duration_min=dur,
        suggestions=[
            RestaurantSuggestion.model_construct(
                name=name, lat=lat, lng=lng, cuisine_type="", meal_type="all",
            )
        ],
    )


def _lunch(start, end, dur, name, **kw):
    return _meal(LunchBreakItem, ItemType.LUNCH_BREAK, start, end, dur, name, **kw)


def _dinner(start, end, dur, name, **kw):
    return _meal(DinnerBreakItem, ItemType.DINNER_BREAK, start, end, dur, name, **kw)


def _transit(start, end, dur, frm, to, mode, src):
    return TransitItem(
        type=ItemType.TRANSIT,
        start_time=start,
        end_time=end,
        duration_min=dur,
        mode=mode,
        from_location=frm,
        to_location=to,
        routing_source=src,
    )


def _day_end_time(items) -> str | None:
    for it in items:
        if getattr(it, "type", None) == ItemType.DAY_END:
            return it.time
    return None


def _last_item_end(items) -> str | None:
    last = None
    for it in items:
        if getattr(it, "type", None) in (ItemType.DAY_START, ItemType.DAY_END):
            continue
        en = getattr(it, "end_time", None)
        if en and (last is None or en > last):
            last = en
    return last


# --- 1. day_end tells the truth in both directions -------------------------


def test_day_end_never_precedes_dinner():
    """Client D3: day_end=16:35 while dinner ran 18:00–19:00."""
    items = [
        DayStartItem(time="09:00"),
        _attr("Aquapark", "10:15", "12:15", 120),
        _lunch("14:21", "15:01", 40, "Olimpijska"),
        _ft("17:05", "18:00", 55),
        _dinner("18:00", "19:00", 60, "Mała Grecja"),
        DayEndItem(time="16:35"),
    ]
    out = _svc()._reconcile_day_end_marker(items, CTX, day_num=3)
    assert _day_end_time(out) == "19:00"
    assert _day_end_time(out) == _last_item_end(out)


def test_day_end_follows_an_afternoon_finish():
    """Client D1: real content ended 15:39 but day_end stayed 20:00."""
    items = [
        DayStartItem(time="09:00"),
        _attr("Rynek we Wrocławiu", "09:38", "11:38", 120),
        _attr("Muzeum Topacz", "13:47", "14:47", 60),
        _ft("14:47", "15:17", 30),
        _ft("15:17", "15:39", 22),
        DayEndItem(time="20:00"),
    ]
    out, note = _svc()._finalize_client_day_invariants(items, CTX, day_num=1)
    end = _day_end_time(out)
    assert end is not None and end < "16:30"
    assert end == _last_item_end(out)
    assert note and "spokojniej" in note.lower()


def test_day_end_untouched_on_a_full_day():
    items = [
        DayStartItem(time="09:00"),
        _attr("ZOO Wrocław", "09:00", "11:36", 156),
        _lunch("13:17", "13:57", 40, "Pod przykrywką"),
        _attr("Ostrów Tumski", "17:10", "18:15", 65),
        _dinner("19:20", "20:00", 40, "Konspira"),
        DayEndItem(time="20:00"),
    ]
    out, note = _svc()._finalize_client_day_invariants(items, CTX, day_num=2)
    assert _day_end_time(out) == "20:00"
    assert note is None


# --- 2. the drive home from an excursion ----------------------------------


def test_near_satellite_gets_a_drive_home():
    """Client D1: no return Ślęza → Wrocław after Topacz."""
    assert _is_near_satellite_stop_name("Muzeum Motoryzacji i Techniki Zamek Topacz")
    items = [
        _attr("Muzeum Topacz", "13:47", "14:47", 60, lat=51.0341, lng=16.9913),
    ]
    out = _svc()._ensure_far_excursion_return(items, CTX, day_num=1)
    legs = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert legs, "expected a drive back to the hub"
    assert "wrocław" in (legs[-1].to_location or "").lower()
    assert legs[-1].start_time == "14:47"


def test_return_starts_after_a_local_lunch():
    """Client D4/D6: the return must follow the last stop, lunch included."""
    items = [
        _attr("Muzeum Motoryzacji Wena", "09:44", "11:14", 90,
              lat=50.9329, lng=17.2924),
        _lunch("13:09", "13:49", 40, "MotoBar", lat=50.9430, lng=17.2956),
    ]
    out = _svc()._ensure_far_excursion_return(items, CTX, day_num=4)
    legs = [it for it in out if getattr(it, "type", None) == ItemType.TRANSIT]
    assert legs and legs[-1].start_time == "13:49"
    assert legs[-1].from_location == "MotoBar"


def test_no_drive_home_invented_past_the_window():
    """A 20-min stub ending 20:20 is worse than showing no leg at all."""
    items = [
        _attr("Zamek w Ząbkowicach Śląskich", "16:46", "18:01", 75,
              lat=50.5865, lng=16.8075),
        _dinner("19:00", "20:00", 60, "Mała Grecja", lat=50.589, lng=16.810),
    ]
    out = _svc()._ensure_far_excursion_return(items, CTX, day_num=3)
    for it in out:
        if getattr(it, "type", None) != ItemType.TRANSIT:
            continue
        assert (it.end_time or "") <= "20:00"


# --- 3. one named block per gap -------------------------------------------


def test_adjacent_free_time_becomes_one_block():
    """Client D2: 19:00–19:27 and 19:27–20:00 read as two blocks."""
    items = [
        _dinner("18:00", "19:00", 60, "Konspira"),
        _ft("19:00", "19:27", 27, "Oddech w środku dnia"),
        _ft("19:27", "20:00", 33, "Czas dla siebie"),
    ]
    out = _svc()._merge_abutting_free_time_hard(items, day_num=2, max_gap=6)
    blocks = [it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME]
    assert len(blocks) == 1
    assert blocks[0].start_time == "19:00" and blocks[0].end_time == "20:00"


def test_free_time_split_by_a_sliver_still_merges():
    items = [
        _ft("19:00", "19:27", 27),
        _ft("19:31", "20:00", 29),
    ]
    out = _svc()._merge_abutting_free_time_hard(items, day_num=2, max_gap=6)
    assert len([
        it for it in out if getattr(it, "type", None) == ItemType.FREE_TIME
    ]) == 1


def test_evening_block_is_not_labelled_mid_day():
    items = [
        _dinner("18:00", "19:00", 60, "Konspira"),
        _ft("19:00", "20:00", 60, "Oddech w środku dnia"),
    ]
    out = _svc()._relabel_free_time_by_slot(items, CTX, day_num=2)
    label = next(
        it.label for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
    )
    assert "środku dnia" not in _fold_place_label(label).replace("srodku", "środku")
    assert "srodku dnia" not in _fold_place_label(label)


def test_morning_block_is_not_labelled_mid_day():
    """Client D2: 09:00–09:35 'Oddech w środku dnia'."""
    items = [
        DayStartItem(time="09:00"),
        _ft("09:00", "09:35", 35, "Oddech w środku dnia"),
        _attr("ZOO Wrocław", "09:35", "11:36", 121),
    ]
    out = _svc()._relabel_free_time_by_slot(items, CTX, day_num=2)
    label = next(
        it.label for it in out
        if getattr(it, "type", None) == ItemType.FREE_TIME
    )
    folded = _fold_place_label(label)
    assert "srodku dnia" not in folded
    assert "popoludniow" not in folded


def test_short_lunch_is_stretched_to_40():
    """Client D4: lunch only 25 min."""
    items = [
        _attr("Rynek w Oławie", "12:19", "12:49", 30, lat=50.94, lng=17.29),
        _lunch("14:08", "14:33", 25, "Przystanek ze smakiem",
               lat=50.94, lng=17.29),
        _transit("14:33", "15:18", 45, "Przystanek ze smakiem",
                 "Wrocław centrum", TransitMode.CAR, "estimated_road"),
        DayEndItem(time="15:18"),
    ]
    out = _svc()._enforce_minimum_lunch_duration(items, day_num=4)
    lunch = next(
        it for it in out
        if getattr(it, "type", None) == ItemType.LUNCH_BREAK
    )
    assert lunch.duration_min >= 40
    trans = next(
        it for it in out if getattr(it, "type", None) == ItemType.TRANSIT
    )
    assert trans.start_time >= lunch.end_time


def test_wena_is_an_olawa_stop():
    assert _is_olawa_stop_name("Muzeum Motoryzacji Wena")
    from app.domain.planner.engine import poi_geo_region_key
    assert poi_geo_region_key({"name": "Muzeum Motoryzacji Wena", "city": "Wrocław"}) == "region_olawa"


def test_repeat_olawa_day_is_stripped():
    """Client D7: Wena again after an Oława day, with no Wrocław drive."""
    items = [
        DayStartItem(time="09:00"),
        _attr("Muzeum Motoryzacji Wena", "09:00", "10:30", 90,
              lat=50.9329, lng=17.2924),
        DayEndItem(time="10:30"),
    ]
    out, _ = _svc()._finalize_client_day_invariants(
        items,
        {**CTX, "blocked_satellite_kinds": {"olawa"}},
        day_num=7,
        pool=[],
        coord_map={},
    )
    names = [
        getattr(it, "name", "") for it in out
        if getattr(it, "type", None) == ItemType.ATTRACTION
    ]
    assert not any("Wena" in (n or "") for n in names)


def test_every_gap_gets_a_name():
    """Client D4: 14:40–15:02 free, then nothing until 16:02."""
    items = [
        DayStartItem(time="09:00"),
        _attr("Muzeum Motoryzacji Wena", "09:44", "11:14", 90),
        _lunch("13:09", "13:49", 40, "MotoBar"),
        _attr("Rynek w Oławie", "16:02", "17:02", 60),
        DayEndItem(time="17:02"),
    ]
    out = _svc()._name_all_remaining_holes_final(items, CTX, day_num=4)
    covered = sorted(
        (it.start_time, it.end_time) for it in out
        if getattr(it, "type", None) not in (
            ItemType.DAY_START, ItemType.DAY_END,
        )
    )
    cursor = "09:00"
    for start, end in covered:
        assert start <= cursor or start == cursor, f"gap before {start}"
        cursor = max(cursor, end)
    assert cursor == "17:02"


# --- 4. transit mode / routing_source coherence ---------------------------


def test_walk_leg_cannot_claim_road_routing():
    """Client D3: Hala → Muzeum Pana Tadeusza was walk + estimated_road."""
    items = [
        _transit("13:01", "13:17", 16, "Hala Stulecia",
                 "Muzeum Pana Tadeusza", TransitMode.WALK, "estimated_road"),
        _transit("14:00", "14:45", 45, "Muzeum", "Wrocław centrum",
                 TransitMode.CAR, "estimated_walk"),
    ]
    out = _svc()._normalize_transit_mode_source(items, day_num=3)
    assert out[0].routing_source == "estimated_walk"
    assert out[1].routing_source == "estimated_road"


def test_ors_sources_are_left_alone():
    items = [
        _transit("13:01", "13:17", 16, "A", "B", TransitMode.WALK, "ors"),
        _transit("14:00", "14:45", 45, "B", "C", TransitMode.CAR, "cache"),
    ]
    out = _svc()._normalize_transit_mode_source(items, day_num=3)
    assert [it.routing_source for it in out] == ["ors", "cache"]


def test_stretched_walk_leg_is_rebuilt_from_distance():
    """A 55-min walk between neighbours 200 m apart is a bug, not a stroll."""
    coords = {
        "laboratorium dr. frankensteina": {"lat": 50.5883, "lng": 16.8091},
        "rynek w ząbkowicach śląskich": {"lat": 50.5895, "lng": 16.8110},
    }
    items = [
        _transit("15:51", "16:46", 55, "Laboratorium dr. Frankensteina",
                 "Rynek w Ząbkowicach Śląskich", TransitMode.WALK,
                 "estimated_walk"),
    ]
    out = _svc()._sanitize_walk_leg_durations(items, coords, day_num=3)
    assert out[0].duration_min < 15
    assert out[0].end_time == "16:46", "arrival must stay put"


def test_plausible_city_walk_is_untouched():
    coords = {
        "taste": {"lat": 51.1107, "lng": 17.0324},
        "hydropolis": {"lat": 51.1035, "lng": 17.0572},
    }
    items = [
        _transit("12:46", "13:22", 36, "Taste", "Hydropolis",
                 TransitMode.WALK, "estimated_walk"),
    ]
    out = _svc()._sanitize_walk_leg_durations(items, coords, day_num=1)
    assert out[0].duration_min == 36


# --- 5. satellite market squares and duplicate tables ---------------------


def test_market_square_caps():
    """Client D6: 3 h for the Niemcza market square."""
    assert _satellite_market_square_cap("Rynek w Niemczy") == 75
    assert _satellite_market_square_cap("Rynek w Ząbkowicach Śląskich") == 75
    assert _satellite_market_square_cap("Rynek we Wrocławiu") is None
    assert _satellite_market_square_cap("Rynek Główny") is None
    assert _satellite_market_square_cap("Stary Rynek") is None
    assert _satellite_market_square_cap("Hala Stulecia") is None


def test_three_hour_market_square_is_capped():
    items = [_attr("Rynek w Niemczy", "10:55", "13:55", 180)]
    out = _svc()._cap_satellite_market_squares(items, day_num=6)
    assert out[0].duration_min == 75 and out[0].end_time == "12:10"


def test_same_restaurant_twice_drops_the_dinner():
    """Client D7: "ta sama restauracja jest dwa razy"."""
    items = [
        _lunch("14:21", "15:18", 57, "Mała Grecja"),
        _attr("Rynek w Ząbkowicach Śląskich", "15:26", "16:41", 75),
        _transit("18:53", "19:00", 7, "Rynek w Ząbkowicach Śląskich",
                 "Mała Grecja", TransitMode.WALK, "estimated_walk"),
        _dinner("19:00", "20:00", 60, "Mała Grecja"),
    ]
    out = _svc()._drop_duplicate_meal_stop(items, day_num=7)
    names = [
        (getattr(s, "name", "") or "")
        for it in out
        for s in (getattr(it, "suggestions", None) or [])
    ]
    assert names.count("Mała Grecja") == 1
    assert not any(
        getattr(it, "type", None) == ItemType.DINNER_BREAK for it in out
    )
    assert not any(
        getattr(it, "type", None) == ItemType.TRANSIT
        and (it.to_location or "") == "Mała Grecja"
        for it in out
    )


def test_distinct_restaurants_are_kept():
    items = [
        _lunch("13:17", "13:57", 40, "Pod przykrywką"),
        _dinner("19:20", "20:00", 40, "Konspira"),
    ]
    out = _svc()._drop_duplicate_meal_stop(items, day_num=2)
    assert len(out) == 2


# --- 6. no dead morning before the first stop ----------------------------


def test_empty_morning_is_pulled_forward():
    """Client D7: 09:00–10:43 free_time before the drive even started."""
    items = [
        DayStartItem(time="09:00"),
        _ft("09:00", "10:43", 103),
        _transit("10:43", "11:58", 75, "Wrocław",
                 "Krzywa Wieża", TransitMode.CAR, "estimated_road"),
        _attr("Krzywa Wieża", "12:14", "13:14", 60),
        _lunch("14:21", "15:18", 57, "Mała Grecja"),
        DayEndItem(time="20:00"),
    ]
    out = _svc()._pull_day_forward_to_start(items, CTX, day_num=7)
    first = next(
        it for it in out
        if getattr(it, "type", None) == ItemType.TRANSIT
    )
    assert first.start_time == "09:00"
    assert not any(
        getattr(it, "type", None) == ItemType.FREE_TIME
        and it.start_time == "09:00"
        for it in out
    )
    attr = next(
        it for it in out if getattr(it, "type", None) == ItemType.ATTRACTION
    )
    assert attr.start_time >= "10:00", "sights must not open before 10:00"


def test_morning_stays_put_when_the_first_stop_is_early():
    items = [
        DayStartItem(time="09:00"),
        _attr("ZOO Wrocław", "09:00", "11:36", 156),
        DayEndItem(time="11:36"),
    ]
    out = _svc()._pull_day_forward_to_start(items, CTX, day_num=2)
    assert [getattr(it, "start_time", None) for it in out] == [
        None, "09:00", None,
    ]


def test_olawa_name_variants_group_together():
    """"Rynek w Oławie" never matched the old exact-form marker."""
    assert _is_olawa_stop_name("Rynek w Oławie")
    assert _is_olawa_stop_name("Izba Muzealna Ziemi Oławskiej")
    assert _is_olawa_stop_name("Muzeum Motoryzacji Wena")
    assert not _is_olawa_stop_name("Rynek we Wrocławiu")


def test_zabkowice_inflected_name_groups():
    from app.application.services.plan_service import _timeline_satellite_kind
    assert _timeline_satellite_kind("Rynek w Ząbkowicach Śląskich") == "zabkowice"
    assert _timeline_satellite_kind("Słoneczny Park Wodny w Ząbkowicach Śląskich") == "zabkowice"
    assert _timeline_satellite_kind("Laboratorium dr. Frankensteina") == "zabkowice"


# --- 7. the pass as a whole is idempotent --------------------------------


def test_finalize_is_idempotent():
    items = [
        DayStartItem(time="09:00"),
        _transit("09:00", "10:15", 75, "Wrocław", "Baszta Miejska w Niemczy",
                 TransitMode.CAR, "estimated_road"),
        _attr("Baszta Miejska w Niemczy", "10:15", "10:50", 35,
              lat=50.725, lng=16.852),
        _attr("Rynek w Niemczy", "10:55", "13:55", 180,
              lat=50.7174, lng=16.8348),
        _lunch("14:00", "14:40", 40, "Pod Łabędziem",
               lat=50.7174, lng=16.8348),
        DayEndItem(time="20:00"),
    ]
    svc = _svc()
    once, note1 = svc._finalize_client_day_invariants(items, CTX, day_num=6)
    twice, note2 = svc._finalize_client_day_invariants(once, CTX, day_num=6)
    shape = lambda seq: [  # noqa: E731
        (
            str(getattr(getattr(it, "type", None), "value", "")),
            getattr(it, "start_time", None) or getattr(it, "time", None),
            getattr(it, "end_time", None),
        )
        for it in seq
    ]
    assert shape(once) == shape(twice)
    assert note1 == note2
    assert _day_end_time(twice) == _last_item_end(twice)
