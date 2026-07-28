# FIX #247 — Warszawa (feedback klientki, runda 2)

## Problemy zgłoszone
| JSON | Problem |
|------|---------|
| **8** | D6–7: długie bloki free time |
| **2** | D3: obniżyć Most Świętokrzyski |
| **3** | Brak pokrycia active_sport |
| **4** | D1 Pałac Prezydencki; D4 Most; powtórki Ogrody Zamku |
| **7** | Profil adventure nieodczuwalny |
| **9** | Centrum Pieniądza off-profile |
| **10** | Brak water_attractions; powtórki Ogrody/Plac Europejski |

## Zmiany
1. **Warsaw trip-repeat keys** — Most, Pałac Prezydencki, Ogrody Zamku, Plac Europejski, Centrum Pieniądza, Browary
2. **Deny/demote** — fillery + Centrum Pieniądza (solo relax); couples museum+relax
3. **Boost** — active_sport (Tepfactor, Park Linowy, Kajaki); underground/adventure; solo nature; couples water
4. **Backfill** — active_sport gdy brak w tripie; water per-day (couples); D6–7 na 7-dniowych wyjazdach
5. **Coverage** — team_challenge, tepfactor, warszawianka w preference_coverage

## Pliki
- `profile_poi_rules.py`, `preference_coverage.py`, `plan_service.py`
- `tests/test_fix247_warszawa_client.py`
- `scripts/_audit_warszaw_fix247.py`
