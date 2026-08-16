"""FIX #276 — expanded Wrocław attractions + satellite restaurants."""
from __future__ import annotations

from app.application.services.plan_service import (
    _is_brzeg_stop_name,
    _is_olawa_stop_name,
    _is_wojslawice_stop_name,
    _is_zabkowice_stop_name,
    _WENA_DEFAULT_COORDS,
)
from app.domain.planner.city_copy import (
    WROCLAW_RESTAURANT_CITIES,
    filter_pois_by_city,
    poi_matches_city_filter,
    wroclaw_poi_load_cities,
)
from app.domain.planner.engine import (
    _meal_restaurant_geo_ok,
    poi_geo_region_key,
    visit_duration_hard_cap,
)
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi


def test_fix276_wroclaw_load_cities_include_satellites():
    cities = wroclaw_poi_load_cities("Wrocław")
    assert "Wrocław" in cities
    assert "Niemcza" in cities
    assert "Oława" in cities
    assert "Ząbkowice Śląskie" in cities
    assert wroclaw_poi_load_cities("Kraków") == ["Kraków"]


def test_fix276_satellite_filter_keeps_zabkowice_for_wroclaw_only():
    zab = {
        "name": "Krzywa Wieża w Ząbkowicach Śląskich",
        "city": "Kłodzko",
        "hub_city": "Kłodzko",
        "city_excel": "Ząbkowice Śląskie",
    }
    assert poi_matches_city_filter(zab, "Wrocław")
    assert poi_matches_city_filter(zab, "Kłodzko")
    assert not poi_matches_city_filter(zab, "Kraków")
    kept = filter_pois_by_city([zab, {"name": "Rynek", "city": "Kraków", "hub_city": "Kraków"}], "Wrocław")
    assert [p["name"] for p in kept] == ["Krzywa Wieża w Ząbkowicach Śląskich"]


def test_fix276_regions_and_stop_names():
    assert poi_geo_region_key({"name": "Rynek w Niemczy", "city": "Niemcza"}) == "region_wojslawice"
    assert poi_geo_region_key({"name": "Dolina Tatarska", "city": "Niemcza"}) == "region_wojslawice"
    assert poi_geo_region_key({"name": "Rynek w Oławie", "city": "Oława"}) == "region_olawa"
    assert poi_geo_region_key({"name": "Laboratorium Frankensteina"}) == "region_zabkowice"
    assert poi_geo_region_key({"name": "Zamek Piastów Śląskich w Brzegu"}) == "region_brzeg"
    assert _is_wojslawice_stop_name("Baszta Miejska w Niemczy")
    assert _is_olawa_stop_name("Muzeum Motoryzacji Wena")
    assert _is_zabkowice_stop_name("Krzywa Wieża w Ząbkowicach Śląskich")
    assert _is_brzeg_stop_name("Zamek Piastów Śląskich w Brzegu")
    assert abs(_WENA_DEFAULT_COORDS[0] - 50.9329) < 0.01


def test_fix276_meal_stays_local():
    niemcza = {"name": "Rynek w Niemczy", "city": "Niemcza"}
    olawa = {"name": "Rynek w Oławie", "city": "Oława"}
    wro_rest = {"name": "Taste", "city": "Wrocław"}
    niem_rest = {"name": "Pod Łabędziem", "city": "Niemcza"}
    olawa_rest = {"name": "MotoBar", "city": "Oława"}
    assert _meal_restaurant_geo_ok(niem_rest, niemcza, {})
    assert not _meal_restaurant_geo_ok(wro_rest, niemcza, {})
    assert _meal_restaurant_geo_ok(olawa_rest, olawa, {})
    assert not _meal_restaurant_geo_ok(wro_rest, olawa, {})


def test_fix276_restaurant_cities():
    assert "Niemcza" in WROCLAW_RESTAURANT_CITIES
    assert "Oława" in WROCLAW_RESTAURANT_CITIES
    assert "Ząbkowice Śląskie" in WROCLAW_RESTAURANT_CITIES


def test_fix276_excel_new_pois_and_no_dupes():
    pois = load_multi_city_poi("data/multi_city_attractions.xlsx", wroclaw_poi_load_cities("Wrocław"))
    names = [p.get("name") or "" for p in pois]
    low = [n.lower() for n in names]
    for must in (
        "baszta miejska w niemczy",
        "dolina tatarska",
        "rynek w niemczy",
        "rynek w oławie",
        "izba muzealna ziemi oławskiej",
        "zamek piastów śląskich w brzegu",
        "bungee wrocław",
        "arboretum wojsławice",
        "muzeum motoryzacji wena",
    ):
        assert any(must in n for n in low), must
    krzywa = [n for n in low if "krzywa wieża" in n and "ząbkow" in n]
    assert len(krzywa) == 1
    botanic = [p for p in pois if "ogród botaniczny" in (p.get("name") or "").lower()]
    assert botanic
    lat = float(botanic[0].get("lat") or 0)
    assert 51.0 < lat < 51.2
    iluzja = [p for p in pois if "iluzji" in (p.get("name") or "").lower()]
    assert iluzja
    assert 51.0 < float(iluzja[0].get("lat") or 0) < 51.2


def test_fix276_caps_untouched():
    assert visit_duration_hard_cap({"name": "Kolejkowo"}, for_scheduling=True) == 60
    assert visit_duration_hard_cap({"name": "Panorama Racławicka"}, for_scheduling=True) == 30
