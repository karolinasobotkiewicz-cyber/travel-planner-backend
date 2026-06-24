"""FIX #213 regression — client city feedback (coverage, scoring guards)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.domain.scoring.preference_coverage import (
    poi_covers_preference_report,
    preference_coverage_adequate,
    is_strong_nature_coverage_poi,
)
from app.domain.planner.engine import (
    is_water_attraction_poi,
    travel_time_minutes,
    poi_repeat_cluster_key,
)


def _poi(name, tags=None, **kw):
    d = {"name": name, "tags": tags or [], "tags_excel": tags or []}
    d.update(kw)
    return d


def test_coverage_false_positives():
    cases = [
        ("nature_landscape", "Planty Krakowskie", ["historic_city_park"], False),
        ("nature_landscape", "Maczuga Herkulesa", ["scenic_valley_landmark"], False),
        ("nature_landscape", "Muzeum Zywego Motyla", ["butterfly_exhibit_room"], False),
        ("nature_landscape", "Kopiec Kosciuszki", ["historic_viewpoint_mound"], True),
        ("active_sport", "Browar Stu Mostow", ["brewery", "craft_beer"], False),
        ("active_sport", "Pijalnia Czekolady E.Wedel", ["chocolate_tasting"], False),
        ("water_attractions", "Muzeum Lotnictwa Polskiego", ["aviation_history"], False),
        ("water_attractions", "Lazienki Krolewskie", ["park_complex", "water_features"], False),
        ("water_attractions", "Bulwary Wislane", ["riverside_walk"], False),
        ("museum_heritage", "Katedra Wroclawska", ["gothic_cathedral"], False),
        ("museum_heritage", "Muzeum Narodowe", ["art_museum"], True),
        ("history_mystery", "Katedra Wroclawska", ["gothic_cathedral", "cathedral_area"], True),
    ]
    fails = []
    for pref, name, tags, expected in cases:
        p = _poi(name, tags)
        got = poi_covers_preference_report(p, pref)
        if got != expected:
            fails.append(f"{pref}/{name}: got {got}, expected {expected}")
    assert not fails, "\n".join(fails)


def test_coverage_adequacy_threshold():
    planty = _poi("Planty Krakowskie", ["historic_city_park"])
    motyl = _poi("Muzeum Motyla", ["butterfly_exhibit_room"])
    assert not preference_coverage_adequate("nature_landscape", [planty])
    assert not preference_coverage_adequate("nature_landscape", [planty, motyl])
    kopiec = _poi("Kopiec Kosciuszki", ["historic_viewpoint_mound"])
    bulwar = _poi("Bulwary Wislane", ["riverside_walk", "vistula_river_walks"])
    assert is_strong_nature_coverage_poi(kopiec)
    assert is_strong_nature_coverage_poi(bulwar)
    assert preference_coverage_adequate("nature_landscape", [kopiec, bulwar])


def test_water_poi_guard():
    assert not is_water_attraction_poi(_poi("Browar Mariacki", ["brewery"]))
    assert not is_water_attraction_poi(_poi("Muzeum Lotnictwa", ["aircraft_collection"]))


def test_city_walk_transit():
    ctx = {"has_car": True, "signals": {"cluster_type": "standalone_city"}, "region_type": "city"}
    a = {"lat": 50.0614, "lng": 19.9366, "name": "A"}
    b = {"lat": 50.0470, "lng": 19.9610, "name": "B"}  # ~2.5 km
    t = travel_time_minutes(a, b, {**ctx, "trip_type": "city_tourism"})
    assert 25 <= t <= 40, f"expected walk ~30min, got {t}"


def test_krakow_cluster_key():
    assert poi_repeat_cluster_key("Wawel") == "cluster_krakow_core"
    assert poi_repeat_cluster_key("Podziemia Rynku") == "cluster_krakow_core"
    assert poi_repeat_cluster_key("Muzeum Tatrzanskie") != "cluster_krakow_core"


if __name__ == "__main__":
    test_coverage_false_positives()
    test_coverage_adequacy_threshold()
    test_water_poi_guard()
    test_city_walk_transit()
    test_krakow_cluster_key()
    print("FIX #213: 5/5 tests passed")
