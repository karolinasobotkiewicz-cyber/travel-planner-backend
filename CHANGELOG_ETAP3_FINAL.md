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

## FIX #188 — inne miasta (czerwiec 2026)

| ID | Opis |
|----|------|
| #188a | **Neutralne sugestie** — Krupówki/Tatry/góralska tylko dla `is_zakopane_trip` |
| #188b | **Filtr miasta** — diacritic-safe guard na każdej ścieżce ładowania POI |
| #188c | **Gap-fill per-day** — pula strefowa dnia + `contexts[day_num]` zamiast globalnej puli |
| #188d | **Domyślny `is_zakopane_trip=False`** w engine (bezpieczniejszy default) |

### Dla klientki — uzupełnienia w Excelu (`multi_city_attractions.xlsx`)

**Zrobione w repo (FIX #188 data):** poprawione `City` + współrzędne m.in. Muzeum Iluzji Wrocław, Ogród Botaniczny UWr, GoJump Wrocław, Fontanna Multimedialna Wrocław, 7× `Warsaw`→`Warszawa`, 7× puste `City` w Krakowie, usunięte 11 pustych stub-wierszy.

**Zaimportowane w FIX #189** — plik klientki `Planer - miasta atrakcje6.xlsx` (kolumna `Zone` + `Hub`).

## FIX #191 — inne miasta: dni + raport preferencji (czerwiec 2026)

| ID | Opis |
|----|------|
| #191a | **FIX #112** — redukcja dni tylko dla Zakopanego (min. strefa); Warszawa/Kraków używają całej puli POI |
| #191b | **`tags_excel`** — surowe tagi z Excela oddzielnie od tagów scoringowych |
| #191c | **Strict `preference_coverage`** — raport API po tagach Excela + denylist (Most ≠ nature, Bulwary ≠ local_food) |

## FIX #190 — finalne poprawki Zakopanego (czerwiec 2026)

| ID | Opis |
|----|------|
| #190a | **Po szlaku 3h+** — tylko relaks (termy/spa); blokada Niedzicy / Zone C / zwiedzania |
| #190b | **Jaskinie** — tagi `cave`/`underground` OK; coverage wymaga prawdziwej jaskini; boost scoringu |
| #190c | **Natura + muzeum + historia** — max 2 muzea/dzień, boost natury gdy muzea dominują |
| #190d | **JSON8** — max 2 scenic/dzień (wierchy, polany, kolejki); gap-fill w plan_service |

## FIX #189 — Zone A/B/C dla wszystkich miast (czerwiec 2026)

| ID | Opis |
|----|------|
| #189a | **Import atrakcje6** — 721 wierszy / 16 arkuszy → `multi_city_attractions.xlsx` (716) + `zakopane.xlsx` (95) |
| #189b | **Kolumna `Hub`** — arkusz = hub wyjazdu; Zone C (np. Energylandia/Zator, Suntago, Ojców) ładuje się mimo `City` = miejscowość satelitarna |
| #189c | **`poi_matches_city_filter`** — filtr po `City` **lub** `Hub` (FIX #188 + Zone C) |
| #189d | **Poprawki City przy imporcie** — Wrocław GPS, `Warsaw`→`Warszawa`, NaN→Hub; Kraków-only fixes scoped per arkusz (Bulwary Wiślane Warszawa ≠ Kraków) |

**Zone po imporcie:** A=511, B=124, C=81. Przykłady Zone C: Warszawa 5, Kraków 6, Wrocław 4, Gdańsk 8, Zakopane 17.

**Dla klientki — nadal warto pilnować:** poprawne `City`, spójne nazewnictwo (`Warszawa` nie `Warsaw`), tagi w jednej komórce (bez `\n` w Excelu).

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
- **Inne miasta** — Zone C działa od FIX #189 (wymaga kolumny `Zone` w Excelu klientki)
- Pełne **twarde reguły relax** (max 2h szlak) — osobny pakiet EXTRA

---

*Commit: FIX #186 | Zakopane travel planner backend Etap 3*
