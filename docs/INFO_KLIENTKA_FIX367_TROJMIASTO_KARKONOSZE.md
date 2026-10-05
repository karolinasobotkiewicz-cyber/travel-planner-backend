# FIX #367 (core) - Trojmiasto i Karkonosze

## Kontekst
UAT 2026-10-05. Ten FIX to RDZEN: ciaglosc lokalizacji i huby. Reszta w kolejnej rundzie.
Wroclaw / Zakopane nadal zamrozone.

## Co naprawia (core)
1. Location cursor (user_at / car_at) - spacer nie startuje ze starego POI; return_to_car tylko gdy auto != user i zaraz jest przejazd.
2. Ban hubow generycznych mid-day (Gdansk/Gdynia/Sopot/Karpacz itd.).
3. Implausible walks - multi-km w krotkim czasie -> auto lub drop.
4. Clip 23:59-23:59 usuwany.

## Validator hard-fail (non-frozen)
stale_walk_start, implausible_walk, generic_hub, aba_return_loop.

## Olozone (kolejna runda)
- Day clustering Trojmiasto/Karkonosze
- Cross-city POI / duplicate coords
- Nowe bramki pre-push per miasto
- Soft profile (zima/kids/senior)
- Pelny redesign posilkow poza #366

## Pliki
- app/application/services/plan_service.py (_seal_fix367_uat_day core)
- scripts/plan_quality_validator.py
- tests/test_fix367_*.py
- docs/INFO_KLIENTKA_FIX367_TROJMIASTO_KARKONOSZE.md
