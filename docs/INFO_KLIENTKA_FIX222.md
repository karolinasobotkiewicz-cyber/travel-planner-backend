## FIX #222 (28.06.2026) — feedback klientki: Wrocław, Warszawa, Kraków, Katowice, Poznań

**Główny problem:** preferencje realizowane głównie dnia 1, potem uniwersalne atrakcje; nadal za dużo Free Time.

**Baza:** `data/multi_city_attractions.xlsx` (kopia `multi_city_attractions (1).xlsx` od klientki).

---

## Zmiany

### 1. Równomierne rozłożenie preferencji (cały pobyt)

- `compute_prefs_needed_today()` — każdego dnia wymusza brakujące preferencje (nie tylko dzień 1).
- `trip_pref_days` — śledzenie dni z trafieniem per preferencja.
- Scoring **+95–155** za POI pokrywające „needed today” pref; **-85** za filler bez dopasowania; **-60** quick-stop gdy prefs wciąż potrzebne.
- Relax nie dominuje, gdy inne prefs wciąż wymagane (**-50**).

### 2. Free Time

- Cap merge miasta: **60 min** (było 90).
- `_strip_leading_free_time()` — usuwa FT przed pierwszą atrakcją (brak „godziny wolna” na start dnia).
- FIX #106: zawsze pomijaj FT tuż po `day_start` (gap-fill zamiast pustego bloku).

### 3. Micro-POI / ranking

- Rozszerzone `_HARD_QUICK_STOP_MARKERS` (Grabowy Labirynt, City Golf, Browar Stu Mostów, Most Świętokrzyski, Syrenka, Obwarzanki, Geologiczne, Nikiszowiec, Spodek, Rynek Jeżycki, Plac Wolności, Holiday Park…).
- `_CITY_FLAGSHIP_NAME_MARKERS` — boost Wawel, Łazienki, POLIN, PKiN, Hydropolis, Hala Stulecia itd. przy `cultural` / `museum_heritage`.
- Zoo **-90** poza family/kids przy profilu cultural/history.

### 4. Coverage (fałszywe dopasowania)

Deny w `preference_coverage.py` m.in.:
- Wedel → nie `museum_heritage`
- Geologiczne, Podziemia, Wieliczka, Schindler, Fabryka Wódki → nie `nature_landscape` / `relaxation`
- Kopiec Powstania, Muzeum Śląskie, Rogalowe Muzeum → nie water/food/relax miscredit
- Plac Wolności, Rynek Jeżycki → nie `museum_heritage`

### 5. Target group (family_kids)

Deny: Bastion Sakwowy, Neon Side, Most Świętokrzyski, Muzeum Powstania, Plac Europejski, Czartoryskich, Laser Tag (age ≤6 w scoringu **-200**).

### 6. Czas wizyt

- `choose_duration`: min typu museum **45**, park **40**, landmark **45**; floor **25 min** dla non-quick-stop.
- `LUNCH_LATEST`: **14:00** (było 14:30).

### 7. Budżet

- Gap-fill: hard filter koszt POI > `daily_limit` (np. Bungee przy 500 zł/dzień).

### 8. Sezonowość

- Zima: deny ponton, spływ, złotniki, flisack (Spływy Złotniki w lutym).

### 9. Klaster Wrocław Szczytnicki

- `cluster_wroclaw_szczytnicki`: Botaniczny → Pergola → Ogród Japoński → Hala Stulecia — boost gdy klaster już w planie.

---

## Pliki

| Plik | Zmiana |
|------|--------|
| `app/domain/planner/engine.py` | spread prefs, scoring, duration, lunch, cluster |
| `app/application/services/plan_service.py` | FT cap 60, strip morning FT, budget gap-fill |
| `app/domain/scoring/preference_coverage.py` | coverage denies |
| `app/domain/scoring/family_fit.py` | family_kids denies |
| `app/domain/filters/seasonality.py` | winter pontoon deny |
| `data/multi_city_attractions.xlsx` | baza klientki |
| `tests/test_fix222_client_feedback.py` | unit tests |

---

## Test plan (retest klientki)

1. **Preferencje** — 5–7 dni: każda preferencja pojawia się w **każdym** dniu (mix, nie „dzień natury”).
2. **Free Time** — brak FT na początku dnia; bloki ≤60 min miasto.
3. **Wrocław luty** — brak Spływów Złotniki; klaster Szczytnicki w jednym dniu.
4. **family_kids** — brak Neon Side, Bastion Sakwowy, Laser Tag (5 lat).
5. **Budżet 500** — brak Bungee / POI droższych niż limit dzienny.
6. **Cultural** — Wawel/Łazienki/POLIN w planie; Obwarzanki/Geologiczne nie otwierają dnia.
7. **relax** — HTTP 200 (hotfix #221 import); bez wielogodzinnego FT.

**Render:** po pushu Manual Deploy, potem `/plan/preview` z JSON-ami z `json_miasta/`.
