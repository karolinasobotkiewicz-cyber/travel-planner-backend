"""FIX #225 (29.06.2026) — client feedback for Kraków.

Covers:
- City flagships (Wawel/Rynek/Mariacka/Sukiennice) boosted across ALL profiles.
- Family icons (Smok/Wawel/Ogród Doświadczeń/Park Jordana/Zoo) boosted for family_kids.
- Secondary POIs demoted (Muzeum Obwarzanka, Fabryka Wódki, Be Happy, Kopiec Krakusa...).
- Ojców / Wieliczka far-region keys to stop map-hopping in one day.
- Flagship duration floor in attraction-item builder.
- Coverage miscredits removed (Nowa Huta, Park Decjusza, Lustrzany Labirynt).
"""

from app.domain.planner.engine import (
    poi_geo_region_key,
    _CITY_FLAGSHIP_NAME_MARKERS,
    _FAMILY_ICON_MARKERS,
    _UNIVERSAL_FILLER_NAME_MARKERS,
    _FAR_GEO_REGIONS,
)
from app.domain.scoring.preference_coverage import poi_covers_preference_report


def _poi(name, **kw):
    base = {"name": name, "tags": kw.pop("tags", [])}
    base.update(kw)
    return base


def test_ojcow_region_clustering():
    assert poi_geo_region_key(_poi("Maczuga Herkulesa")) == "region_ojcow"
    assert poi_geo_region_key(_poi("Zamek w Pieskowej Skale")) == "region_ojcow"
    assert poi_geo_region_key(_poi("Jaskinia Ciemna")) == "region_ojcow"
    assert "region_ojcow" in _FAR_GEO_REGIONS


def test_wieliczka_region_distinct_from_ojcow():
    assert poi_geo_region_key(_poi("Kopalnia Soli Wieliczka")) == "region_wieliczka"
    # Wieliczka and Maczuga are different regions → not mixed in one day.
    assert poi_geo_region_key(_poi("Maczuga Herkulesa")) != poi_geo_region_key(
        _poi("Kopalnia Soli Wieliczka")
    )


def test_krakow_flagships_in_markers():
    for nm in ("zamek królewski na wawelu", "rynek główny w krakowie",
               "bazylika mariacka", "mnk sukiennice", "planty krakowskie",
               "bulwary wiślane"):
        assert any(m in nm for m in _CITY_FLAGSHIP_NAME_MARKERS), nm


def test_wieza_ratuszowa_removed_from_flagships():
    assert not any(m in "wieża ratuszowa" for m in _CITY_FLAGSHIP_NAME_MARKERS)


def test_family_icons_present():
    for nm in ("pomnik smoka wawelskiego", "ogród doświadczeń im. lema",
               "park jordana", "ogród zoologiczny w krakowie"):
        assert any(m in nm for m in _FAMILY_ICON_MARKERS), nm


def test_secondary_pois_demoted_as_filler():
    for nm in ("muzeum obwarzanka", "fabryka wódki w krakowie",
               "be happy museum w krakowie", "kopiec krakusa",
               "lustrzany labirynt", "pałac krzysztofory"):
        assert any(m in nm for m in _UNIVERSAL_FILLER_NAME_MARKERS), nm


def test_coverage_miscredits_removed():
    nowa_huta = _poi("Nowa Huta", tags=["socialist_realism_architecture"])
    assert poi_covers_preference_report(nowa_huta, "water_attractions") is False
    assert poi_covers_preference_report(nowa_huta, "local_food_experience") is False
    assert poi_covers_preference_report(nowa_huta, "relaxation") is False

    decjusza = _poi("Park Decjusza", tags=["landscaped_park_walks"])
    assert poi_covers_preference_report(decjusza, "active_sport") is False
    assert poi_covers_preference_report(decjusza, "history_mystery") is False

    maze = _poi("Lustrzany Labirynt", tags=["mirror_maze_experience"])
    assert poi_covers_preference_report(maze, "museum_heritage") is False
    assert poi_covers_preference_report(maze, "relaxation") is False
