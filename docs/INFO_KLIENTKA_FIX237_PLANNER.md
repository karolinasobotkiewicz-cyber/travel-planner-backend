# FIX #237 — logika planera (timeline, transit, posiłki)

Odpowiedź na feedback klientki (wspólne problemy we wszystkich miastach).

## Mapowanie wymagań → zmiany

| # | Wymaganie | Co zrobiono |
|---|-----------|-------------|
| 1 | Oś czasu bez nakładek / ujemnych czasów / dziur | `plan_day_integrity`: usuwanie bloków z `end ≤ start`, naprawa lunch↔transit, `validate_and_heal` (6 iteracji) |
| 2 | Przejazd przy każdej zmianie lokalizacji | Finalny pass: `_ensure_transits_between_attractions` + `_update_transit_destinations` + `_collapse_duplicate_transits` |
| 3 | Haversine ≠ final dla auta | `travel_time_minutes` → `get_travel_route` (ORS/cache); fallback samochodu: `routing_source: estimated_road` |
| 4 | Współrzędne transit vs POI | `assert_transit_endpoints_match_pois` + `_enrich_transits_with_routing` z mapy POI |
| 5 | Nie kończyć dnia wcześnie przy dostępnych POI | Ponowne `_afternoon_topup_items` w finalnym `_apply_fix237_day_pipeline` |
| 6–7 | Lunch/kolacja z `suggestions`, blisko aktualnej pozycji | `ensure_meal_suggestions` + `_tiered_nearby_restaurants` względem ostatniej atrakcji |
| 8 | Wyjazdy jako bloki dnia | Bez zmian w tym fixie — nadal reguły engine (#235 OPN/Kampinos re-entry) |
| 9 | Twarde profile (Family Kids, Adventure, …) | Bez zmian w tym fixie — nadal `profile_poi_rules` + `_ensure_preference_coverage` |

## Pliki

- `app/application/services/plan_day_integrity.py` — helpery timeline/meals
- `app/application/services/plan_service.py` — `_apply_fix237_day_pipeline` (finalna rekonsyliacja dnia)
- `app/domain/planner/engine.py` — routing przez provider
- `app/infrastructure/routing/haversine.py` — `estimated_road` dla auta
- `tests/test_fix237_planner_integrity.py`

## Testy regresji

Uruchom m.in.:

`pytest tests/test_fix237_planner_integrity.py tests/test_fix235_client_feedback.py tests/test_fix234_client_feedback.py tests/test_fix220_routing.py --no-cov`
