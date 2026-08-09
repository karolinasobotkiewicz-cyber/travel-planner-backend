"""FIX #258 — Warszawa: hours, MiniCiti age, Wedel copy, Fontann show window."""
from __future__ import annotations

from app.domain.planner.engine import is_open, visit_duration_hard_cap
from app.domain.planner.opening_hours_parser import is_poi_open_at_time
from app.domain.planner.poi_copy import build_fallback_copy
from app.domain.scoring.profile_poi_rules import should_deny_poi_for_profile
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.infrastructure.repositories.load_zakopane import _parse_seasonal_list


def test_fix258_multi_city_loads_seasonal_hours():
    pois = load_multi_city_poi("data/multi_city_attractions.xlsx", ["Warszawa"])
    by_name = {p["name"]: p for p in pois}
    wil = by_name.get("Muzeum Pałacu Króla Jana III w Wilanowie")
    assert wil is not None
    assert wil.get("opening_hours_seasonal")
    graw = by_name.get("Stacja Grawitacja")
    assert graw is not None
    assert graw.get("opening_hours_seasonal")


def test_fix258_monday_warsaw_museums_closed():
    # Monday 2026-02-09
    ctx = {"date": "2026-02-09", "year": 2026, "month": 2, "day": 9}
    for name in (
        "Muzeum Fabryki Norblina",
        "Muzeum Gazowni Warszawskiej",
        "Zamek Królewski",
    ):
        assert is_open(
            {"name": name, "opening_hours": None},
            12 * 60, 60, "winter", ctx,
        ) is False


def test_fix258_ogrody_zamku_not_hard_closed_monday():
    ctx = {"date": "2026-02-09", "year": 2026, "month": 2, "day": 9}
    assert is_open(
        {"name": "Ogrody Zamku Królewskiego", "opening_hours": None},
        12 * 60, 60, "winter", ctx,
    ) is True


def test_fix258_wawel_not_hard_closed_monday():
    ctx = {"date": "2026-02-09", "year": 2026, "month": 2, "day": 9}
    assert is_open(
        {"name": "Zamek Królewski na Wawelu", "opening_hours": None},
        12 * 60, 60, "winter", ctx,
    ) is True


def test_fix258_fontann_thursday_daytime_closed():
    # Thursday 2026-07-09 18:00 — client bug
    ctx = {"date": "2026-07-09", "year": 2026, "month": 7, "day": 9}
    assert is_open(
        {"name": "Multimedialny Park Fontann", "opening_hours": None},
        18 * 60, 30, "summer", ctx,
    ) is False


def test_fix258_fontann_saturday_show_window_ok():
    # Saturday 2026-07-11 21:30, 30 min show
    seasonal = _parse_seasonal_list(
        """[
  {
    date_from: 05-01,
    date_to: 07-31,
    mon: closed,
    tue: closed,
    wed: closed,
    thu: closed,
    fri: closed
    sat: 21:30-22:00,
    sun: 21:30-22:00
  }
]"""
    )
    assert seasonal
    assert is_poi_open_at_time(
        None, seasonal, (2026, 7, 11), 5, 21 * 60 + 30, 30,
    ) is True
    assert is_open(
        {
            "name": "Multimedialny Park Fontann",
            "opening_hours_seasonal": seasonal,
        },
        21 * 60 + 30, 30, "summer",
        {"date": "2026-07-11", "year": 2026, "month": 7, "day": 11},
    ) is True


def test_fix258_fontann_duration_cap_30():
    assert visit_duration_hard_cap(
        {"name": "Multimedialny Park Fontann"}, for_scheduling=True
    ) == 30


def test_fix258_grawitacja_before_10_closed():
    seasonal = _parse_seasonal_list(
        """{
  "date_from": "01-01",
  "date_to": "12-31",
  "mon": "10:00-22:00",
  "tue": "10:00-22:00",
  "wed": "10:00-22:00",
  "thu": "10:00-22:00",
  "fri": "10:00-22:00",
  "sat": "10:00-22:00",
  "sun": "10:00-22:00"
}"""
    )
    ctx = {"date": "2026-02-10", "year": 2026, "month": 2, "day": 10}
    assert is_open(
        {"name": "Stacja Grawitacja", "opening_hours_seasonal": seasonal},
        9 * 60, 60, "winter", ctx,
    ) is False
    assert is_open(
        {"name": "Stacja Grawitacja", "opening_hours_seasonal": seasonal},
        10 * 60, 60, "winter", ctx,
    ) is True


def test_fix258_miniciti_denied_for_age_5():
    poi = {"name": "Miniciti - edukacyjne miasto dzieci"}
    assert should_deny_poi_for_profile(
        poi, {"target_group": "family_kids", "children_age": 5},
    )
    assert not should_deny_poi_for_profile(
        poi, {"target_group": "family_kids", "children_age": 8},
    )


def test_fix258_wedel_copy_uses_aleja_wedla():
    desc, tip = build_fallback_copy(
        {
            "name": "Pijalnia Czekolady E.Wedel",
            "city": "Warszawa",
            "address": "aleja Wedla 5, 03-822 Warszawa, Poland",
            "description_short": "Interaktywne muzeum czekolady.",
        }
    )
    blob = f"{desc} {tip or ''}".lower()
    assert "aleja wedla" in blob or "alei wedla" in blob
    assert "szpitaln" not in blob or "nie przy ul. szpitalnej" in blob
