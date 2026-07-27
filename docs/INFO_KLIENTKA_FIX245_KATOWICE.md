# FIX #245 — Katowice (feedback klientki, runda 2)

## Problemy zgłoszone
- Powtarzające się atrakcje w planie (Park Kościuszki, Rynek, Wedel, Planetarium…)
- Puste / rzadkie dni (np. dzień 7 w json 8, dzień 3 w json 9)
- Brak atrakcji dla dzieci w family_kids (json 1, dzień 2)
- Adventure zbyt muzealne; Wilson za wysoko (json 3)
- Poranek pusty przy starcie o 9:00 (json 3, dzień 2)
- Guido + Królowa Luiza nie mogą iść po sobie (json 4)
- Słabe water_attractions (json 10)

## Zmiany techniczne
1. **`poi_trip_repeat_key`** — fuzzy klucze powtórzeń (Kościuszki, Rynek, Wedel, Planetarium, Dolina, Pixel, Kolejkowo, Nikiszowiec, Tężnia…)
2. **`_strip_trip_repeat_filler_attractions`** — max 1× filler na cały wyjazd
3. **`_strip_guido_luiza_same_day`** — blokada tego samego dnia i kolejnych dni
4. **`_backfill_sparse_day_attractions`** — uzupełnianie pustych dni + poranny backfill dla friends adventure
5. **`_strip_family_non_kids_late_day`** — family_kids D2+ bez kids POI
6. **Scoring FIX #245** — Wilson demote dla friends adventure, kids/water/sparse-day boosts, penalty za powtórki

## Pliki
- `app/domain/scoring/profile_poi_rules.py`
- `app/application/services/plan_service.py`
- `tests/test_fix245_katowice_client.py`
- `scripts/_audit_katowice_fix245.py`
