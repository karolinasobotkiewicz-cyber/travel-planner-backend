# FIX #246 — Kraków (feedback klientki, runda 2)

## Problemy zgłoszone
| JSON | Problem |
|------|---------|
| **8** | D2: Lustrzany Labirynt — obniżyć ranking (przypadkowy filler) |
| **5** | Za mało kids_attractions (1 atrakcja) |
| **2** | D2: długi transit (~41 min); D3: brak propozycji kolacji |
| **4** | D4: Alvernia Planet off; mocniejszy nature |
| **10** | Relaxation praktycznie nieobecny |

## Zmiany
1. **Lustrzany Labirynt** — deny + demote (−140/−240) dla couples nature/museum bez kids
2. **Alvernia Planet** — deny dla solo+nature
3. **family_kids** — boost kids POI (+115), backfill gdy <2 kids w tripie
4. **Long transit** — `_strip_long_transit_destinations` (>35 min → drop cel)
5. **Kolacja** — fallback sugestii przy `local_food`; re-run `ensure_meal_suggestions` w finalize
6. **couples water+relax** — strip heritage filler bez relaksu; backfill Bulwary/Park Wodny
7. **solo nature** — boost parków/bulwarów/botanicznego; demote muzeów gdy 2+ w dniu

## Pliki
- `profile_poi_rules.py`, `plan_service.py`, `family_fit.py` (markers)
- `tests/test_fix246_krakow_client.py`
- `scripts/_audit_krakow_fix246.py`
