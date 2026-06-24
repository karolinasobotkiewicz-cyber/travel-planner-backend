"""FIX #215 regression — Kotlina Kłodzka client feedback."""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from app.domain.scoring.preference_coverage import poi_covers_preference_report
from app.domain.router.trip_type_router import TripTypeRouter
from app.domain.models.trip_input import (
    TripInput, LocationInput, GroupInput, TripLengthInput, DailyTimeWindow, BudgetInput,
)


def _poi(name, tags=None, **kw):
    d = {"name": name, "tags": tags or [], "tags_excel": tags or []}
    d.update(kw)
    return d


def _trip(city="Polanica-Zdrój"):
    return TripInput(
        location=LocationInput(city=city, country="Poland", region_type="city"),
        group=GroupInput(type="solo", size=1, crowd_tolerance=3),
        trip_length=TripLengthInput(days=3, start_date=date(2026, 2, 20)),
        daily_time_window=DailyTimeWindow(),
        budget=BudgetInput(),
        preferences=["nature_landscape"],
    )


def test_kotlina_router_cluster_pool():
    cfg = TripTypeRouter().detect_trip_type(_trip("Kłodzko"))
    assert cfg["trip_type"] == "cluster"
    assert cfg["region"] == "Kotlina Kłodzka"
    assert len(cfg.get("cities", [])) == 3


def test_coverage_kotlina_false_positives():
    cases = [
        ("nature_landscape", "Park Szachowy", ["park", "nature"], False),
        ("nature_landscape", "Ekocentrum Parku Narodowego Gór Stołowych", ["national_park_education_center"], False),
        ("nature_landscape", "Muzeum Minerałów", ["mineral_collection"], False),
        ("nature_landscape", "Szczeliniec Wielki", ["table_mountains_peak", "iconic_hiking_destination"], True),
        ("nature_landscape", "Błędne Skały", ["labyrinth_rock_formations"], True),
        ("nature_landscape", "Twierdza Srebrna Góra", ["mountain_fortress_complex"], False),
        ("active_sport", "Manufaktura Szkła Barbara", ["craft_workshop"], False),
        ("active_sport", "Park Linowy Kudowa", ["forest_rope_courses"], True),
        ("kids_attractions", "Kaplica Czaszek", ["ossuary_chapel"], False),
        ("kids_attractions", "Rynek w Lądku-Zdroju", ["historic_town_square"], False),
        ("kids_attractions", "Muzeum Zabawek", ["historic_toy_collection"], True),
    ]
    fails = []
    for pref, name, tags, expected in cases:
        got = poi_covers_preference_report(_poi(name, tags), pref)
        if got != expected:
            fails.append(f"{pref}/{name}: got {got}, expected {expected}")
    assert not fails, "\n".join(fails)


if __name__ == "__main__":
    test_kotlina_router_cluster_pool()
    test_coverage_kotlina_false_positives()
    print("FIX #215: 2/2 tests passed")
