# FIX #233 — Client feedback (global + per-city)

**Data:** 2026-07-04  
**Zakres:** Wrocław, Poznań, Kraków, Warszawa, Katowice

## Problemy globalne — zmiany

| # | Problem | Rozwiązanie |
|---|---------|-------------|
| 1 | Adventure = 1 aktywna atrakcja + zwiedzanie | `profile_poi_rules`: boost aktywnych POI, demote muzea/kościoły po 1. aktywnym; engine: cap muzeów adventure = 0 bez `museum_heritage` |
| 2 | Długie luki / free_time | Urban cap 15 min/blok, 35 min/dzień; gap-fill max 15 min free_time w miastach |
| 3 | Restauracje daleko + „Restauracja w centrum” | `MEAL_RESTAURANT_MAX_DIST_KM` 1 km; usunięty generic fallback w engine i plan_service |
| 4 | Balanced = za dużo muzeów | Cap 2 muzea/dzień (balanced); demote po 3+ muzeach w tripie |
| 5 | Pierwsza atrakcja ~1h po starcie | Urban snap pierwszej atrakcji do day_start+5 min; `_trim_gap_after_day_start` 12 min |
| 6 | Wszystkie parkingi „free” | `normalizer._normalize_parking_type` + default **paid** gdy brak danych |
| 7 | Profile family_kids / solo+relax / couples+cultural | Rozszerzone deny/demote w `profile_poi_rules` + `family_fit` |
| 8 | Wyjazdy 1 POI → powrót | Regiony Gniezno/Gliwice/Suntago/Modlin; `should_block_premature_excursion_return`; cluster boost |
| 9 | Zbyt krótkie czasy zwiedzania | `choose_duration` min: Pixel 45, Kopiec Krakusa 45, GPE 90, Muzeum Powstania 45 min |

## Miasta — rankingi / reguły

- **Wrocław:** demote Wena, Arboretum Wojsławice (dzień 1), zima=rejsy/pontony blocked, bungee budget 45%
- **Poznań:** boost Jezioro Maltańskie przy `water_attractions`, demote Bambrów/Okrąglak/Bazylika
- **Kraków:** demote micro (Matejki, Geologiczne, Bernatka…), family deny Schindler/Rynek, Ojców cluster
- **Warszawa:** demote micro (Pałac, Syrenka, Most…), deny Powązki dla family, Suntago+Modlin = osobne regiony
- **Katowice:** demote Muzeum Historii/Etnologii/Parafia/Park Chrobrego; deny zoo friends+adventure / couples+cultural

## Pliki

- `app/domain/planner/engine.py`
- `app/domain/scoring/profile_poi_rules.py`
- `app/domain/scoring/family_fit.py`
- `app/application/services/plan_service.py`
- `app/infrastructure/repositories/normalizer.py`
- `tests/test_fix233_client_feedback.py`
- `tests/test_fix233_client_json_audit.py`

## Testy

```powershell
cd travel-planner-backend
python -m pytest tests/test_fix233_client_feedback.py tests/test_fix233_client_json_audit.py tests/test_fix232_front_plan_fields.py -q --no-cov
```
