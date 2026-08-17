"""FIX #277 — client Excel for remaining cities + satellite lunch."""
from __future__ import annotations

from app.domain.config.destination_clusters import DestinationClusters
from app.domain.planner.city_copy import (
    hub_poi_load_cities,
    hub_restaurant_cities,
    poi_matches_city_filter,
    wroclaw_poi_load_cities,
)
from app.domain.planner.engine import _meal_restaurant_geo_ok, poi_geo_region_key
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi


def test_fix277_hub_load_lists():
    krk = hub_poi_load_cities("Kraków")
    assert "Wieliczka" in krk and "Bochnia" in krk
    poz = hub_poi_load_cities("Poznań")
    assert "Gniezno" in poz and "Lednogóra" in poz
    waw = hub_poi_load_cities("Warszawa")
    assert "Sochaczew" in waw and "Żelazowa Wola" in waw
    assert "Gniezno" in hub_restaurant_cities("Poznań")
    assert "Sochaczew" in hub_restaurant_cities("Warszawa")
    assert "Zabrze" in hub_restaurant_cities("Katowice")
    assert "Brzeg" in hub_restaurant_cities("Wrocław")
    assert wroclaw_poi_load_cities("Kraków") == ["Kraków"]


def test_fix277_gzm_includes_dabrowa():
    assert "Dąbrowa Górnicza" in DestinationClusters.GZM["cities"]
    assert DestinationClusters.is_cluster_city("Dąbrowa Górnicza")


def test_fix277_regions_and_local_lunch():
    assert poi_geo_region_key({"name": "Ostrów Lednicki", "city": "Lednogóra"}) == "region_lednica"
    assert poi_geo_region_key({"name": "Dom Urodzenia Fryderyka Chopina", "city": "Żelazowa Wola"}) == "region_sochaczew"
    assert poi_geo_region_key({"name": "Zamek w Wiśniczu", "city": "Nowy Wiśnicz"}) == "region_wieliczka"
    poz_rest = {"name": "Ratuszowa", "city": "Poznań"}
    gniez_rest = {"name": "Młyn Restauracja Gniezno", "city": "Gniezno"}
    led = {"name": "Ostrów Lednicki", "city": "Lednogóra"}
    assert not _meal_restaurant_geo_ok(poz_rest, led, {})
    waw_rest = {"name": "Taste", "city": "Warszawa"}
    soch = {"name": "Muzeum Kolei Wąskotorowej", "city": "Sochaczew"}
    soch_rest = {"name": "Food Factory Sochaczew", "city": "Sochaczew"}
    assert _meal_restaurant_geo_ok(soch_rest, soch, {})
    assert not _meal_restaurant_geo_ok(waw_rest, soch, {})
    assert _meal_restaurant_geo_ok(gniez_rest, {"name": "Katedra w Gnieźnie", "city": "Gniezno"}, {})


def test_fix277_filter_keeps_satellites():
    poi = {"name": "Rynek w Bochni", "city": "Bochnia", "city_excel": "Bochnia", "hub_city": "Kraków"}
    assert poi_matches_city_filter(poi, "Kraków")
    assert not poi_matches_city_filter(poi, "Warszawa")


def test_fix277_excel_new_pois_no_dupes():
    poz = load_multi_city_poi("data/multi_city_attractions.xlsx", hub_poi_load_cities("Poznań"))
    names = " | ".join((p.get("name") or "").lower() for p in poz)
    assert "pręgierz" in names or "pregierz" in names
    assert "ostrów lednicki" in names or "ostrow lednicki" in names
    waw = load_multi_city_poi("data/multi_city_attractions.xlsx", hub_poi_load_cities("Warszawa"))
    wnames = " | ".join((p.get("name") or "").lower() for p in waw)
    assert "hala koszyki" in wnames
    assert "sochaczew" in wnames
    krk = load_multi_city_poi("data/multi_city_attractions.xlsx", hub_poi_load_cities("Kraków"))
    knames = " | ".join((p.get("name") or "").lower() for p in krk)
    assert "rynek w bochni" in knames
    kat = load_multi_city_poi(
        "data/multi_city_attractions.xlsx",
        ["Katowice", "Gliwice", "Zabrze", "Chorzów", "Tychy", "Dąbrowa Górnicza"],
    )
    katn = " | ".join((p.get("name") or "").lower() for p in kat)
    assert "giszowiec" in katn
    assert "pogoria" in katn
    wro = load_multi_city_poi("data/multi_city_attractions.xlsx", wroclaw_poi_load_cities("Wrocław"))
    botanic = [p for p in wro if "ogród botaniczny uniwersytetu wrocław" in (p.get("name") or "").lower()]
    assert botanic and 51.0 < float(botanic[0].get("lat") or 0) < 51.2
    krzywa = [p.get("name") for p in wro if "krzywa wieża" in (p.get("name") or "").lower()]
    assert len(krzywa) == 1
