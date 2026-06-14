# Wiedza operacyjna — FIX #198–#201 (czerwiec 2026)

> Dokument wewnętrzny dla zespołu / AI context.  
> Ostatnia aktualizacja: **8 czerwca 2026**  
> Deploy: `main` @ `fc74f03`

---

## Stan testów regresji (OBOWIĄZKOWE przed każdym merge)

| Test | Plik | Wynik |
|------|------|-------|
| Zakopane baseline | `test_naturalness_klientka.py` | **10/10** |
| Multi-city | `test_multi_city_density.py` | **10/10** |

Uruchomienie (Windows PowerShell):

```powershell
cd travel-planner-backend
$env:PYTHONIOENCODING='utf-8'
python test_naturalness_klientka.py
python test_multi_city_density.py
```

---

## Mapa commitów FIX #198–#201

| FIX | Commit | Temat |
|-----|--------|-------|
| #198 | `a282bd1` | GPS POI po normalizacji, coverage, free_time |
| #199 | `07b3e02` | Parking GPS, urban transity, coverage, komunikaty miast |
| #200 | `3521b30` | Transity do nieistniejących POI, strict coverage, hub→city, cluster gap-fill |
| #201 | `fc74f03` | Cluster hub days, must_see, family_kids trails, explainability, dinner/day_end |

---

## FIX #198 — GPS i normalizacja POI

**Przyczyna pustych `lat/lng/address` w API:** `normalize_poi()` czytał kolumny `Lat`/`City`, loader zapisywał `lat`/`city` → merge zerował współrzędne.

**Pliki:**
- `app/infrastructure/repositories/normalizer.py`
- `app/infrastructure/repositories/load_multi_city.py`
- `app/application/services/plan_service.py`
- `app/domain/scoring/preference_coverage.py`

**Reguła:** Po zmianie loadera zawsze sprawdź JSON odpowiedzi — `lat`, `lng`, `address` nie mogą być null dla POI z Excela.

---

## FIX #199 — Parking i transity urban

- `ParkingInfo` — fallback `lat/lng` z POI gdy brak parkingu
- Wyłączenie 20-min bufora parkingu (15+5) dla `region_type=urban` / city tourism
- Coverage: deny `photo_spot`, `panoramic_view` dla `nature_landscape`
- Warning `long_trip_variety` per miasto (nie hardcoded Zakopane)

**Pliki:** `plan_service.py`, `preference_coverage.py`

---

## FIX #200 — Transity, coverage, cluster fill

| Problem klientki | Rozwiązanie |
|------------------|-------------|
| Transit do POI spoza planu | `_validate_transit_endpoints()` — usuwa transity z nieznanym `from`/`to` |
| „Previous location” | Gap-fill: `from_location` = nazwa poprzedniej atrakcji |
| Luki 10–20 min po transicie | Snap atrakcji do `transit.end_time` |
| Parking „Brak danych” | Urban: „Parking w okolicy atrakcji” + GPS fallback |
| Spodek/Rynek jako museum/nature | Strict coverage gates w `poi_covers_preference_report()` |
| Kraków + Ogród Wrocławski | `poi_matches_city_filter`: hub > błędne `City` |
| Adventure → same szlaki | Culture-led adventure: kara za viewpointy |
| Puste dni 6–7 w klastrze | Do 5 passów gap-fill dla cluster 5+ dni |

**Pliki:** `plan_service.py`, `city_copy.py`, `engine.py`, `load_multi_city.py`, `preference_coverage.py`

---

## FIX #201 — Cluster, scoring, explainability, kolacja

### 1. Cluster — dni regionalne (hub pools)

Gdy `is_cluster` i brak zone pools → `build_cluster_hub_day_pools()`:

- Grupuje POI po `hub` (fallback: `city`)
- Rotuje dni między hubami (Gdynia/Sopot/Gdańsk, Polanica/Kłodzko/Kudowa…)
- Dłuższe pobyty: więcej dni na huby z większą liczbą POI

**Plik:** `app/domain/planner/city_copy.py` → `build_cluster_hub_day_pools()`  
**Integracja:** `plan_service.py` (~linia 1381)

**Limitacja:** Hel/Rewa wymagają osobnych wartości `hub` w Excelu — silnik nie wymyśli podregionu bez danych.

### 2. must_see / core / premium

`is_quick_stop_poi()` — denylista krótkich postojów foto:
- Pomnik Bamberków, Brama Chlebnicka, Fontanna Neptuna, Ulica Długa, deptaki, Plac Zdrojowy…

Stosowane w:
- `engine.py` — brak iconic boost przy `must_see >= 8`
- `quality_checker.py` — brak badge `must_see` / `core_attraction` / `premium_experience`

### 3. family_kids Kłodzko (children_age ≤ 5)

Twarde wykluczenie:
- `type == trail`
- Nazwy: Czarna Góra, Jawornik, Trojak, Śnieżka, Karkonosze, szlaki…
- Zachowany FIX #125: `time_min > 90` → exclude

**Plik:** `engine.py` (filtr kandydatów)

### 4. why_selected vs preference_coverage

`_explain_preference_match()` używa `poi_covers_preference_report()` — ten sam gate co API coverage.

„Relaxing activity (matches your style)” tylko gdy:
- `travel_style == relax` **ORAZ**
- `relaxation` jest w `user.preferences`

**Plik:** `explainability.py`

### 5. underground / water coverage

- `is_underground_poi()` — rozszerzone tagi i markery nazw (kopalnie, sztolnie, jaskinie)
- `is_water_attraction_poi()` — wodospady, termy, aquaparki (tagi + nazwa)
- `preference_coverage.py` — fallback `is_water_attraction_poi` dla `water_attractions`
- `plan_service._compute_preference_coverage()` — spójne użycie helperów

### 6. day_end + kolacja

`_enforce_dinner_before_day_end()` — po afternoon top-up (#196):
- Obcina `dinner_break` do `day_end`
- Usuwa atrakcje/transity/free_time dodane **po** `dinner_break`

**Plik:** `plan_service.py`

---

## Co NIE naprawiamy w silniku (wina danych Excel)

| Problem | Akcja klientki |
|---------|----------------|
| Fontanna Multimedialna `City=Warsaw` | Poprawić na Wrocław |
| Spodek `must_see=10`, tagi bez museum | Obniżyć score lub poprawić tagi |
| Długi Targ / Bamberki jako core | Obniżyć `must_see` / `priority_level` |
| Hel/Rewa jako osobne dni | Dodać kolumnę `hub` |
| Unknown tags w Excelu | Dodać do `tag_preferences.py` lub poprawić w Excelu |

Baza multi-city: **684 POI** (`data/multi_city_attractions.xlsx`).

---

## Kolejne iteracje (FIX #202+)

1. **Routing per podregion** — dojazd Gdańsk→Hel jako osobny dzień (wymaga hubów + logiki driving)
2. **Głębsza kalibracja must_see** — synchronizacja Excel `Must see score` z badge API
3. **Rozszerzenie `tag_preferences.py`** — wiele POI ma unknown tags (logi loadera)
4. **Twarde reguły travel_style** — opcjonalnie, osobna warstwa (klientka pytała 01.06)

---

## Kluczowe pliki (szybka nawigacja)

```
app/application/services/plan_service.py   # orchestracja, gap-fill, transity, dinner
app/domain/planner/engine.py               # scoring, filtry, underground/water
app/domain/planner/city_copy.py            # hub pools, filtry miast
app/domain/planner/explainability.py       # why_selected
app/domain/planner/quality_checker.py      # badges POI/dnia
app/domain/scoring/preference_coverage.py  # strict coverage API
app/infrastructure/repositories/load_multi_city.py
app/infrastructure/repositories/normalizer.py
```

---

## Zasady regresji (NIE PSUĆ)

- FIX #193: po szlaku 5h+ tylko termy/free_time
- FIX #195/196: afternoon top-up + heal timeline
- FIX #197: normalizacja multi-city, city cap 6
- Zakopane 10/10 — warunek akceptacji każdej zmiany globalnej
