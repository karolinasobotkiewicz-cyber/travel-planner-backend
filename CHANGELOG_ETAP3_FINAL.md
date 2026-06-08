# Etap 3 — Changelog finalizacji (czerwiec 2026)

Podsumowanie dla klientki: co zostało dostarczone w silniku planowania Zakopane.

## Stabilność i jakość planu

- **Brak duplikatów POI** w jednym wyjeździe (trip-wide dedup)
- **Zone A → B → C** z sub-klastrami geograficznymi
- **Jeden kierunek na dzień** (Pieniny LUB Tatry Słowackie — bez mieszania)
- **Deterministyczny wybór** atrakcji (te same wejście → ten sam plan)
- **Lunch seniors/rodziny** w oknie 12:00–13:30
- **Transit continuity** — ciągłość czasowa i brak teleportacji

## Profile użytkownika

- Rodziny, seniorzy, cultural — poprawione scoringi i limity
- **Adventure + historia/podziemia** — szlaki nie dominują nad muzeami/jaskiniami
- **Preference coverage** w API — raport które preferencje pokryte

## FIX #186 — finalizacja Etapu 3 (czerwiec 2026)

| ID | Opis |
|----|------|
| A1 | **Gwarancja preferencji** — min. 1 atrakcja na każdą aktywną preferencję (bezpieczna zamiana słabej atrakcji) |
| A2 | **Ostrzeżenia API** `preference_not_covered` gdy preferencji nie da się pokryć |
| A3 | **Mniej pustego czasu** — agresywniejsze zapełnianie luk (12 min) na wyjazdach 4+ dni |
| A4 | **Test naturalności** — 10 JSON-ów klientki + regiony + test-07 bez ikon szlaków |

## FIX #187 — feedback klientki (czerwiec 2026)

| ID | Opis |
|----|------|
| #187a | **Brak dalekich wycieczek po długim szlaku** — po ≥3h hike żadnych POI Zone C / Pieniny / Słowacja tego samego dnia (Niedzica po 8h szlaku) |
| #187b | **Mniej pustego D7** — agresywniejszy afternoon backfill na ostatnim dniu wyjazdu 6–7 dni (ten sam `day_geo_region`) |

## Baza danych

- **95 POI** w `zakopane.xlsx` (wersja atrakcje5)
- **Zone C** — wycieczki Pieniny, Spisz, Słowacja z tagami `history_mystery`
- **2 jaskinie** w Kościelisku (Mroźna, Raptawicka) — `underground`

## Testy regresji (zawsze przed release)

```powershell
python test_lunch_continuity_klientka.py
python test_transit_continuity_klientka.py
python test_poi_database_coverage.py
python test_regression_phase7.py
python test_naturalness_klientka.py
python _check_dupes_client.py
```

## Znane ograniczenia (dane, nie bugi)

- Plan **7-dniowy** wymaga bogatej bazy — im więcej POI, tym lepsze dni 6–7
- **Inne miasta** (Kraków, Gdańsk…) — ten sam silnik, bez Zone C / Pienin (ścieżka uproszczona)
- Pełne **twarde reguły relax** (max 2h szlak) — osobny pakiet EXTRA

---

*Commit: FIX #186 | Zakopane travel planner backend Etap 3*
