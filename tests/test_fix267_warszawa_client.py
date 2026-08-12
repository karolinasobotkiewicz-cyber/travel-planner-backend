"""FIX #267 — Warszawa client retest: dupes, addresses, underground, floors."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.services.plan_service import PlanService, _fix_late_lunch
from app.domain.models.plan import ItemType
from app.domain.planner.engine import is_underground_poi, visit_duration_hard_cap
from app.domain.scoring.family_fit import restaurant_matches_target_group
from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.scoring.profile_poi_rules import poi_trip_repeat_key
from app.infrastructure.repositories import POIRepository
from app.infrastructure.repositories.normalizer import normalize_poi


def _svc() -> PlanService:
    return PlanService(POIRepository(str(Path("data") / "multi_city_attractions.xlsx")))


def test_fix267_zamek_and_wilanow_trip_repeat_keys():
    assert poi_trip_repeat_key("Zamek Królewski") == "waw_zamek_krolewski"
    assert poi_trip_repeat_key("Muzeum Pałacu Króla Jana III w Wilanowie") == "waw_wilanow"


def test_fix267_cross_day_zamek_stripped():
    def _attr(name: str, st: str, en: str, dur: int):
        return SimpleNamespace(
            type=ItemType.ATTRACTION,
            name=name,
            start_time=st,
            end_time=en,
            duration_min=dur,
            poi_id=None,
            lat=52.24,
            lng=21.01,
        )

    days = [
        SimpleNamespace(
            day=1, quality_badges=None, date=None, weekday=None,
            items=[_attr("Zamek Królewski", "10:00", "11:00", 60)],
        ),
        SimpleNamespace(
            day=2, quality_badges=None, date=None, weekday=None,
            items=[
                _attr("Zamek Królewski", "10:00", "11:00", 60),
                _attr("Łazienki Królewskie", "12:00", "13:30", 90),
            ],
        ),
    ]
    out = _svc()._strip_cross_day_trip_repeats(days)
    d2_names = [getattr(it, "name", "") for it in (out[1].items or [])]
    assert "Zamek Królewski" not in d2_names
    assert any("Łazienki" in n for n in d2_names)


def test_fix267_browary_address_forced():
    poi = normalize_poi(
        {
            "Name": "Browary Warszawskie",
            "City": "Warszawa",
            "address": "Koszykowa 63, 00-667 Warszawa",
            "lat": 52.22,
            "lng": 21.01,
            "time_min": 60,
            "time_max": 120,
        },
        0,
    )
    assert "koszykowa" not in (poi.get("address") or "").lower()
    assert "grzybowska" in (poi.get("address") or "").lower()


def test_fix267_wedel_address_szpitalna():
    poi = normalize_poi(
        {
            "Name": "Pijalnia Czekolady E.Wedel",
            "City": "Warszawa",
            "address": "aleja Wedla 5, 03-822 Warszawa",
            "lat": 52.25,
            "lng": 21.05,
            "time_min": 45,
            "time_max": 75,
        },
        0,
    )
    assert "szpitalna" in (poi.get("address") or "").lower()
    assert "aleja wedla" not in (poi.get("address") or "").lower()


def test_fix267_browary_and_zamek_caps():
    assert visit_duration_hard_cap(
        {"name": "Browary Warszawskie"}, for_scheduling=True,
    ) == 90
    assert visit_duration_hard_cap(
        {"name": "Zamek Królewski"}, for_scheduling=True,
    ) == 120


def test_fix267_cytadela_is_underground():
    poi = {"name": "Muzeum X Pawilonu Cytadeli Warszawskiej", "tags": []}
    assert is_underground_poi(poi)
    assert poi_covers_preference_report(poi, "underground")


def test_fix267_solo_accepts_seniors_restaurants():
    assert restaurant_matches_target_group(
        {"name": "Bar Mleczny", "target_groups": ["seniors"]},
        {"target_group": "solo"},
    )
    assert restaurant_matches_target_group(
        {"name": "Bistro", "target_groups": ["couples", "friends"]},
        {"target_group": "solo"},
    )


def test_fix267_late_lunch_pulled():
    lunch = SimpleNamespace(
        type=ItemType.LUNCH_BREAK,
        start_time="14:48",
        end_time="15:28",
        duration_min=40,
    )
    out = _fix_late_lunch([lunch], latest_min=14 * 60 + 30)
    assert out[0].start_time == "12:30"
