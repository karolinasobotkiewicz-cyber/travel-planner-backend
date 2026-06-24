"""FIX #214 regression — Karkonosze client feedback (trails, hub days, coverage)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.planner.engine import (
    should_exclude_trail_for_user,
    is_quick_stop_poi,
    _is_culture_led_trip,
)
from app.domain.planner.city_copy import build_cluster_hub_day_pools, normalize_city_name
from app.domain.router.trip_type_router import TripTypeRouter
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, TripLengthInput, DailyTimeWindow, BudgetInput,
)
from datetime import date


def _minimal_trip(city="Karpacz", region_type="city"):
    return TripInput(
        location=LocationInput(city=city, country="Poland", region_type=region_type),
        group=GroupInput(type="solo", size=1, crowd_tolerance=3),
        trip_length=TripLengthInput(days=3, start_date=date(2026, 2, 20)),
        daily_time_window=DailyTimeWindow(),
        budget=BudgetInput(),
        preferences=["nature_landscape"],
    )


def _poi(name, tags=None, **kw):
    d = {"name": name, "tags": tags or [], "tags_excel": tags or []}
    d.update(kw)
    return d


def _trail(name, dur=120, **kw):
    return _poi(name, tags=["hiking", "mountain_trails"], type="trail", time_max=dur, **kw)


def test_karkonosze_router_trails_on():
    router = TripTypeRouter()
    cfg = router.detect_trip_type(_minimal_trip())
    assert cfg["use_trails"] is True, "Karpacz city request must enable trails"
    assert cfg["region"] == "Karkonosze"
    assert len(cfg.get("cities", [])) >= 3


def test_trail_not_blocked_adventure_active():
    user = {
        "preferences": ["active_sport", "history_mystery"],
        "travel_style": "adventure",
        "target_group": "friends",
    }
    trail = _trail("Szlak do Wodospadu Kamieńczyka", dur=90)
    assert not should_exclude_trail_for_user(trail, user, start_time_min=660)
    assert not _is_culture_led_trip(user["preferences"])


def test_trail_blocked_culture_led():
    user = {
        "preferences": ["museum_heritage", "history_mystery", "underground"],
        "travel_style": "adventure",
    }
    trail = _trail("Szlak na Śnieżkę", dur=300)
    assert should_exclude_trail_for_user(trail, user, start_time_min=660)


def test_coverage_karkonosze_false_positives():
    cases = [
        ("nature_landscape", "Punkt Widokowy Orlinek", ["scenic_viewpoint"], False),
        ("nature_landscape", "Muzeum Ziemi Juna", ["geology_exhibits"], False),
        ("nature_landscape", "Wodospad Kamieńczyka", ["waterfall", "mountain_waterfall"], True),
        ("relaxation", "Ski Arena Szrenica", ["ski", "sports_venue"], False),
        ("relaxation", "Zakręt Śmierci", ["scenic_viewpoint"], False),
        ("relaxation", "Termy Cieplickie", ["thermal_pools", "spa"], True),
        ("water_attractions", "Huta Julia", ["industrial_heritage"], False),
        ("water_attractions", "Wodospad Szklarki", ["waterfall"], True),
    ]
    fails = []
    for pref, name, tags, expected in cases:
        got = poi_covers_preference_report(_poi(name, tags), pref)
        if got != expected:
            fails.append(f"{pref}/{name}: got {got}, expected {expected}")
    assert not fails, "\n".join(fails)


def test_quick_stop_kosc_deptak():
    assert is_quick_stop_poi(_poi("Wzgórze Kościuszki", ["historic_viewpoint_mound"]))
    assert is_quick_stop_poi(_poi("Centrum - Deptak w Karpaczu", ["deptak", "promenade"]))


def test_short_trip_hub_days():
    pois = []
    for city in ("Karpacz", "Szklarska Poręba", "Jelenia Góra"):
        for i in range(5):
            pois.append(_poi(f"{city} POI {i}", city=city, hub_city=city))
    pools, _, hubs = build_cluster_hub_day_pools(
        pois, num_days=3, base_city="Szklarska Poręba", cluster_cities=["Karpacz", "Szklarska Poręba", "Jelenia Góra"]
    )
    base_norm = normalize_city_name("Szklarska Poręba")
    base_days = sum(1 for h in hubs if normalize_city_name(h) == base_norm)
    assert base_days >= 2, f"expected >=2 days in Szklarska, got {base_days}: {hubs}"


if __name__ == "__main__":
    test_karkonosze_router_trails_on()
    test_trail_not_blocked_adventure_active()
    test_trail_blocked_culture_led()
    test_coverage_karkonosze_false_positives()
    test_quick_stop_kosc_deptak()
    test_short_trip_hub_days()
    print("FIX #214: 6/6 tests passed")
