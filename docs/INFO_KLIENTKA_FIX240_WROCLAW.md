# FIX #240 — Wrocław client feedback (24.07.2026)

## Zgłoszenia i poprawki

| Obszar | Poprawka |
|--------|----------|
| **Dworzec Świebodzki** | `should_deny` poza museum_heritage/history; hard deny dla family_kids; demote −120 |
| **family_kids** | deny: Dworzec, Browar, Muzeum Uniwersytetu (już było) |
| **Galeria Neon / Browar / Fontanna rano** | `is_evening_only_poi` + strip rano w pipeline |
| **Fontanna / Arboretum zimą** | filtr sezonowy w `seasonality.py` |
| **Hala Targowa** | deny przy active_sport + history_mystery |
| **Kolacja za wcześnie (json8)** | `_collapse` nie przesuwa kolacji; `_enforce_minimum_dinner_time` (≥17:30–18:00) |
| **Dni kończą za wcześnie / pusty dzień 7** | afternoon top-up; `_fill_post_dinner_shift_gaps` po przesunięciu kolacji |
| **Luki przed kolacją** | wieczorne POI od 17:00; collapse nie przesuwa evening-only wcześniej |
| **routing haversine** | piesze → `estimated_walk`; car + user car → tryb jazdy od 600 m |
| **46 km w 5 min** | `_fix_implausible_transit_duration` |
| **Wystawa Pająków** | deny family_kids + relaxation |
| **Pigcasso / Topacz / muzea seniors** | demote w `profile_poi_rules` |
| **nature + relaxation** | boost parków/bulwarów |
| **Arboretum dzień 1** | demote −100 (json9) |

## Testy

- `tests/test_fix240_wroclaw_client.py` — 10 JSON-ów Wrocław + audyt FIX #239
- `scripts/_audit_wroclaw_fix240.py` — szybki raport lokalny
