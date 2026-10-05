# FIX #366 — Kraków i Katowice (uwagi UAT z 2026-10-05)

## Kontekst
Uwagi wspólniczki po testach JSON-ów Kraków 1–10 i Katowice 1–8. Na `main` były już FIX #361–#365. Ten FIX domyka to, co nadal wychodziło na aktualnym `main`, bez otwierania Wrocławia / Zakopanego.

## Co było już naprawione na main (przed #366)
Większość zgłoszeń z maila **nie reprodukuje się** na HEAD sprzed tej gałęzi (FIX #365), m.in.:
- powroty do Fabryki Wódki bez wizyty, błędne 133 m Fabryka→Stare Miasto
- pętla Czartoryskich/Wawel, Planty bez wizyty
- MOCAK / Galicja po zamknięciu (w aktualnych planach wizyty mieszczą się w godzinach)
- pętla zoo→Pixel→zoo, Dolina/Ponderosa, skansen→Browar
- Guido ~45 min, Pixel/Legendia dla seniorów (w tych JSON-ach)
- prosta linia Skałki↔Kopiec (w aktualnym planie), Milkbar 33 km

## Co naprawia FIX #366
1. **Sztolnia Wieliczka po powrocie do Krakowa** — usuwamy nieuczciwy krótki hop do restauracji-satelity (Bagry→Sztolnia ~558 m) oraz orphan return; etykietę kolacji czyścimy do „Restauracja”, żeby nie ciągnąć Wieliczki po hub-return. Wycieczka Kopalnia/Tężnia i powrót `→ Kraków centrum` zostają.
2. **Puste `preference_fill` (Cybermagia)** — stub bez opisu/adresu jest usuwany przed dociągnięciem współrzędnych; fallback ma realny opis/adres/koszt z Excela.
3. **Samochód na < 0,5 km** — hop samochodowy w miastach open-mail → spacer.
4. **Maczuga Herkulesa** — błędne wymuszone współrzędne (1,7 km od Pieskowej Skały) poprawione do wartości z Excela (~75 m).
5. **Dziury po usuniętych hopach** — `_seal_fix366_uat_day` dokłada jeden blok free_time (≤60 min), żeby nie zostawiać `anonymous_gap`.
6. **Token parkingu / return_to_car** — wąska korekta etykiet: nie-noop return_to_car przy pinie auta jest przebranżawiany na zwykły przejazd (żeby nie gubić dojazdu do kolejnej atrakcji), a no-op powrót do pinu jest usuwany. Pełnego _seal_remaining_car_token nie uruchamiamy (psuł inne dni).
7. **Stos 44-min free_time w seal open-mail** — przy dużej luce wstawiany jest jeden residual ≤60 min zamiast łańcucha 44+44+44.

## Validator
- `scripts/plan_quality_validator.py` + `tests/test_fix366_plan_validator.py`
- Twarde fail tylko dla Kraków/Katowice na kodach: `short_car`, `restaurant_no_meal`, `overlap` (aba_hop tylko raport)
- Inne miasta: raport bez faila (decyzja właściciela)

## Świadomie nie ruszane / decyzja właściciela
- **Poznań** — _seal_fix366_uat_day nie działa dla Poznania (shared open-mail), żeby nie psuć bramki overlap/car_teleport; zostaje seal #353–#365.
- **Pokrycie preferencji** (KRK J10 woda/relaks, KAT J7 underground `covered`) — wymaga osobnej decyzji o twardych gwarancjach preferencji.
- Pełne „zero wolnego czasu” w popołudniach — silnik nadal może mieć pojedyncze bloki ≤60 min; #366 usuwa stosy i nieuczciwe hopy, nie przepisuje scoringu.

## Pliki
- `app/application/services/plan_service.py` — `_seal_fix366_uat_day`, Maczuga, Cybermagia, residual free_time
- `tests/test_fix366_krakow_katowice_uat.py`
- `tests/test_fix366_plan_validator.py`
- `scripts/plan_quality_validator.py`
- `docs/INFO_KLIENTKA_FIX366_KRAKOW_KATOWICE.md`

## Regresja
Bramki Kraków / Katowice oraz testy jednostkowe #366 — zielone względem baseline sprzed zmian na tej gałęzi.
