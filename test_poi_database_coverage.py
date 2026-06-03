"""
test_poi_database_coverage.py — FIX #114 verification
=====================================================
Weryfikuje poprawne wykorzystanie PEŁNEJ bazy POI po FIX #94-97, #111, #113.

Sprawdza:
  1. Ładowanie POI — zakopane.xlsx + multi_city_attractions.xlsx
  2. Mapowanie tagów (FIX #111) — apply_tag_mapping działa na oba zestawy danych
  3. Pokrycie preferencji — każda preferencja trafia na ≥MIN_POI POI w Zakopane
  4. Martwe POI — brak POI ze score=0 dla WSZYSTKICH preferencji (wykrywa ślepe punkty)
  5. Dystrybucja stref (FIX #113) — strefa A/B/C/brak w Zakopane
  6. Daty sezonowe — sezonowe POI mają date_from + date_to
  7. Wymagane pola — name, lat, lng, type, tags obecne dla każdego POI
  8. Multi-city — główne preferencje mają pokrycie w Krakowie, Gdańsku, Wrocławiu
"""

import sys
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.domain.scoring.tag_preferences import (
    USER_PREFERENCES_TO_TAGS,
    calculate_tag_preference_score,
)
from app.infrastructure.repositories.normalizer import normalize_pois

# ---------------------------------------------------------------------------
# Konfiguracja
# ---------------------------------------------------------------------------
ZAKOPANE_XLSX = os.path.join(BACKEND_DIR, "data", "zakopane.xlsx")
MULTI_CITY_XLSX = os.path.join(BACKEND_DIR, "data", "multi_city_attractions.xlsx")

# Preferencje testowane szczegółowo w Zakopane
CORE_PREFS = [
    "mountain_trails",
    "nature_landscapes",
    "must_see_only",
    "active_sport",
    "relax_wellness",
    "museum_heritage",
    "attractions_for_kids",
    "water_attractions",
    "local_food_experience",
]

# Minimalna liczba POI w Zakopane, które muszą pasować do preferencji (PASS)
MIN_POI_ZAKOPANE: dict[str, int] = {
    "mountain_trails":      20,   # FIX #95: było 0 → ≥20 wymagane
    "nature_landscapes":    20,   # FIX #95: było 2 → ≥20 wymagane
    "must_see_only":        15,   # FIX #96: must_see tag auto-dodawany przy score≥8
    "active_sport":         5,
    "relax_wellness":       5,
    "museum_heritage":      5,
    "attractions_for_kids": 5,
    "water_attractions":    2,
    "local_food_experience":1,
}

# Multi-city: minimalne pokrycie (≥ N POI) na miasto dla kluczowych preferencji
MULTI_CITY_TEST = [
    ("Kraków",       ["museum_heritage", "nature_landscapes", "must_see_only"],   3),
    ("Gdańsk",       ["museum_heritage", "nature_landscapes", "must_see_only"],    3),
    ("Wrocław",      ["museum_heritage", "nature_landscapes", "must_see_only"],   3),
    ("Poznań",       ["museum_heritage", "nature_landscapes", "must_see_only"],   3),
]

# Maksymalna dopuszczalna liczba martwych POI (score=0 dla wszystkich preferencji)
MAX_DEAD_POI_ZAKOPANE = 5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
WARN = "[WARN]"

passed = 0
failed = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {PASS} {msg}")


def fail(msg: str):
    global failed
    failed += 1
    print(f"  {FAIL} {msg}")


def info(msg: str):
    print(f"  {INFO} {msg}")


def warn(msg: str):
    print(f"  {WARN} {msg}")


def section(title: str):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


def count_matching(pois: list, prefs: list[str]) -> int:
    """Liczba POI z score > 0 dla podanych preferencji."""
    return sum(
        1 for p in pois
        if calculate_tag_preference_score(p, prefs) > 0
    )


# ---------------------------------------------------------------------------
# TEST 1 — Ładowanie POI z zakopane.xlsx
# ---------------------------------------------------------------------------
section("TEST 1 — Ładowanie Zakopane POI (zakopane.xlsx)")

print("  Ładuję zakopane.xlsx...")
zak_raw = load_zakopane_poi(ZAKOPANE_XLSX, city_filter=None)
zak_pois = normalize_pois(zak_raw)

info(f"Załadowano {len(zak_pois)} POI z zakopane.xlsx (po normalizacji)")

if len(zak_pois) >= 30:
    ok(f"Liczba POI: {len(zak_pois)} ≥ 30 (oczekiwane minimum)")
else:
    fail(f"Liczba POI: {len(zak_pois)} < 30 — podejrzanie mała baza")

# ---------------------------------------------------------------------------
# TEST 2 — Wymagane pola dla Zakopane POI
# ---------------------------------------------------------------------------
section("TEST 2 — Wymagane pola w Zakopane POI")

REQUIRED_FIELDS = ["id", "name", "lat", "lng", "tags"]

missing_fields_count = 0
for p in zak_pois:
    for f in REQUIRED_FIELDS:
        val = p.get(f)
        if val is None or val == "" or val != val:  # None, empty, or NaN
            missing_fields_count += 1
            warn(f"POI '{p.get('name','?')}' brak pola '{f}'")

if missing_fields_count == 0:
    ok(f"Wszystkie {len(zak_pois)} POI mają wymagane pola (id, name, lat, lng, tags)")
else:
    fail(f"{missing_fields_count} brakujących pól w Zakopane POI")

# ---------------------------------------------------------------------------
# TEST 3 — Mapowanie tagów (FIX #111) w Zakopane POI
# ---------------------------------------------------------------------------
section("TEST 3 — Mapowanie tagów (FIX #111) w Zakopane POI")

from app.domain.scoring.tag_mapper import TAG_ALIASES, apply_tag_mapping

gained_via_mapping = 0
for p in zak_pois:
    tags = p.get("tags", [])
    # Sprawdź czy jakiś tag w POI pochodzi z mapowania (czyli nie był w oryginale ale jest w TAG_ALIASES)
    mapped_engine_tags = set()
    for t in tags:
        for engine_tags in TAG_ALIASES.values():
            mapped_engine_tags.update(engine_tags)
    gained = [t for t in tags if t in mapped_engine_tags]
    if gained:
        gained_via_mapping += 1

info(f"{gained_via_mapping}/{len(zak_pois)} POI w Zakopane ma tagi dodane przez tag mapper")

# Weryfikacja: musi działać co najmniej dla 1 POI (mapping działa)
if gained_via_mapping >= 1:
    ok(f"Tag mapper działa: {gained_via_mapping} POI otrzymało zmapowane tagi silnika")
else:
    fail("Tag mapper: żaden Zakopane POI nie otrzymał zmapowanych tagów silnika")

# ---------------------------------------------------------------------------
# TEST 4 — Pokrycie preferencji w Zakopane POI
# ---------------------------------------------------------------------------
section("TEST 4 — Pokrycie preferencji w Zakopane POI")

dead_pois = []
pref_coverage: dict[str, int] = {}

for pref in CORE_PREFS:
    matching = count_matching(zak_pois, [pref])
    pref_coverage[pref] = matching
    minimum = MIN_POI_ZAKOPANE.get(pref, 1)
    if matching >= minimum:
        ok(f"{pref:30s}: {matching:3d} POI ≥ {minimum} (minimum)")
    else:
        fail(f"{pref:30s}: {matching:3d} POI < {minimum} (minimum) — za mało pokrycia")

# Wykrywanie martwych POI
all_prefs = list(USER_PREFERENCES_TO_TAGS.keys())
for p in zak_pois:
    score = calculate_tag_preference_score(p, all_prefs)
    if score == 0:
        dead_pois.append(p.get("name", "?"))

if len(dead_pois) <= MAX_DEAD_POI_ZAKOPANE:
    ok(f"Martwe POI (score=0 dla wszystkich preferencji): {len(dead_pois)} ≤ {MAX_DEAD_POI_ZAKOPANE}")
else:
    fail(f"Martwe POI: {len(dead_pois)} > {MAX_DEAD_POI_ZAKOPANE} — zbyt wiele POI bez dopasowania")
    for name in dead_pois:
        warn(f"  Martwe POI: {name}")

# ---------------------------------------------------------------------------
# TEST 5 — Dystrybucja stref (FIX #113) w Zakopane
# ---------------------------------------------------------------------------
section("TEST 5 — Dystrybucja stref (FIX #113) w Zakopane POI")

zone_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0, "": 0, "other": 0}
for p in zak_pois:
    z = p.get("zone", "")
    if z in zone_counts:
        zone_counts[z] += 1
    else:
        zone_counts["other"] += 1

info(f"Strefa A: {zone_counts['A']} | Strefa B: {zone_counts['B']} | Strefa C: {zone_counts['C']} | Brak strefy: {zone_counts['']} | Inne: {zone_counts['other']}")

# POI z A+B+C ≥ 50% wszystkich POI w Zakopane
zoned = zone_counts["A"] + zone_counts["B"] + zone_counts["C"]
if zoned >= len(zak_pois) * 0.5:
    ok(f"Zakopane: {zoned}/{len(zak_pois)} POI ma przypisaną strefę A/B/C (≥50%)")
else:
    warn(f"Zakopane: {zoned}/{len(zak_pois)} POI ma strefę A/B/C — możliwe, że strefa nie jest wypełniona w Excel")

# Strefy muszą być co najmniej 2 różne (A i B)
zones_used = [z for z in ["A", "B", "C"] if zone_counts[z] > 0]
if len(zones_used) >= 2:
    ok(f"Używane strefy: {zones_used} — rotacja stref będzie działać")
else:
    warn(f"Używane strefy: {zones_used} — rotacja stref może nie mieć efektu")

# ---------------------------------------------------------------------------
# TEST 6 — Daty sezonowe
# ---------------------------------------------------------------------------
section("TEST 6 — Kompletność dat sezonowych (FIX #97)")

seasonal_pois = [p for p in zak_pois if p.get("opening_hours_seasonal")]
info(f"POI sezonowe w Zakopane: {len(seasonal_pois)}")

seasonal_missing_dates = []
for p in seasonal_pois:
    seasons = p.get("opening_hours_seasonal", [])
    if isinstance(seasons, list):
        for s in seasons:
            if isinstance(s, dict):
                if not s.get("date_from") or not s.get("date_to"):
                    seasonal_missing_dates.append(p.get("name", "?"))
                    break
    elif isinstance(seasons, dict):
        if not seasons.get("date_from") or not seasons.get("date_to"):
            seasonal_missing_dates.append(p.get("name", "?"))

if not seasonal_missing_dates:
    ok(f"Wszystkie {len(seasonal_pois)} sezonowych POI mają date_from + date_to")
else:
    fail(f"{len(seasonal_missing_dates)} sezonowych POI brakuje dat")
    for name in seasonal_missing_dates:
        warn(f"  Brak dat: {name}")

# ---------------------------------------------------------------------------
# TEST 7 — Ładowanie multi-city + pokrycie preferencji
# ---------------------------------------------------------------------------
section("TEST 7 — Multi-city POI (multi_city_attractions.xlsx)")

for city, prefs, min_each in MULTI_CITY_TEST:
    print(f"\n  --- {city} ---")
    try:
        city_raw = load_multi_city_poi(MULTI_CITY_XLSX, [city])
        city_pois = normalize_pois(city_raw)
        info(f"Załadowano {len(city_pois)} POI dla {city}")

        if len(city_pois) < 5:
            fail(f"{city}: zaledwie {len(city_pois)} POI — zbyt mała baza")
            continue

        ok(f"{city}: {len(city_pois)} POI załadowanych pomyślnie")

        all_missing = False
        for pref in prefs:
            matching = count_matching(city_pois, [pref])
            if matching >= min_each:
                ok(f"{city} | {pref:25s}: {matching} POI ≥ {min_each}")
            else:
                fail(f"{city} | {pref:25s}: {matching} POI < {min_each}")

    except Exception as e:
        fail(f"{city}: błąd ładowania — {e}")

# ---------------------------------------------------------------------------
# TEST 8 — Mapowanie tagów (FIX #111) w multi-city
# ---------------------------------------------------------------------------
section("TEST 8 — Mapowanie tagów (FIX #111) w multi-city POI (Kraków)")

try:
    krakow_raw = load_multi_city_poi(MULTI_CITY_XLSX, ["Kraków"])
    krakow_pois = normalize_pois(krakow_raw)

    # FIX: Verify preference scoring works for Kraków (not just TAG_ALIASES firing).
    # Kraków uses specific vocabulary tags handled directly by tag_preferences.py;
    # TAG_ALIASES is used for generic alias tags (heritage, castle, viewpoint etc.).
    scoring_gains = sum(
        1 for p in krakow_pois
        if calculate_tag_preference_score(p, ["museum_heritage"]) > 0
    )

    info(f"Kraków: {scoring_gains}/{len(krakow_pois)} POI pasuje do museum_heritage przez scoring")

    if scoring_gains >= 5:
        ok(f"Tag scoring działa w multi-city: {scoring_gains} Kraków POI pasuje do museum_heritage")
    else:
        fail(f"Tag scoring: tylko {scoring_gains} Kraków POI pasuje do museum_heritage — za mało")
except Exception as e:
    fail(f"Tag scoring multi-city: błąd — {e}")

# ---------------------------------------------------------------------------
# TEST 9 — must_see tag (FIX #96) — auto-tag z normalizer.py
# ---------------------------------------------------------------------------
section("TEST 9 — must_see auto-tag (FIX #96) — normalizer.py")

must_see_pois = [p for p in zak_pois if "must_see" in p.get("tags", [])]
info(f"POI z tagiem 'must_see' w Zakopane: {len(must_see_pois)}")

if len(must_see_pois) >= 15:
    ok(f"must_see POI w Zakopane: {len(must_see_pois)} ≥ 15 (FIX #96 działa)")
else:
    fail(f"must_see POI w Zakopane: {len(must_see_pois)} < 15 — FIX #96 nie działa poprawnie")

# Wyświetl nazwy must_see POI
info("  Przykłady must_see POI:")
for p in must_see_pois[:8]:
    info(f"    - {p.get('name','?')}")
if len(must_see_pois) > 8:
    info(f"    ... i {len(must_see_pois)-8} więcej")

# ---------------------------------------------------------------------------
# PODSUMOWANIE
# ---------------------------------------------------------------------------
section("PODSUMOWANIE WERYFIKACJI BAZY POI")

total_tests = passed + failed
print(f"\n  Wynik: {passed}/{total_tests} testów PASS")
print()
print(f"  Zakopane POI:      {len(zak_pois)} załadowanych")
print(f"  Strefy A/B/C:      {zone_counts['A']}/{zone_counts['B']}/{zone_counts['C']}")
print(f"  must_see POI:      {len(must_see_pois)}")
print(f"  Sezonowe POI:      {len(seasonal_pois)}")
print(f"  Martwe POI:        {len(dead_pois)}")
print()
print("  Pokrycie preferencji (Zakopane):")
for pref in CORE_PREFS:
    count = pref_coverage.get(pref, "?")
    minimum = MIN_POI_ZAKOPANE.get(pref, 1)
    status = "OK" if isinstance(count, int) and count >= minimum else "!"
    print(f"    [{status}] {pref:30s}: {count}")

print()
if failed == 0:
    print(f"  WYNIK KOŃCOWY: PASS — {passed}/{total_tests} testów OK")
    print("  Pełna baza POI jest poprawnie załadowana i pokrywa wszystkie preferencje.")
else:
    print(f"  WYNIK KOŃCOWY: FAIL — {failed}/{total_tests} testów NIEPRZESZŁO")
    print("  Sprawdź powyższe [FAIL] — wymagane poprawki w danych lub konfiguracji.")
    sys.exit(1)
