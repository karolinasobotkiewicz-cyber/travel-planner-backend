# FIX #367 – Trójmiasto i Karkonosze (UAT 2026-10-05)

## Kontekst
Uwagi klientki po testach JSON-ów Gdańsk / Gdynia / Sopot oraz Karpacz / Jelenia Góra / Szklarska Poręba. Na `main` były już FIX #361–#366 (Kraków/Katowice). Ten FIX domyka powtarzalne klasy defektów globalnie dla miast aktywnych UAT, **bez otwierania Wrocławia / Zakopanego**.

## Klasy naprawione
1. **Location cursor (`user_at` / `car_at`)** – spacer nie startuje ze starego POI po przejeździe; `return_to_car` tylko gdy auto ≠ użytkownik i zaraz jest przejazd.
2. **Ban hubów generycznych mid-day** – „Gdańsk” / „Gdynia” / „Sopot” / „Karpacz” itd. nie tworzą sztucznych 0,5 km odcinków w środku dnia (dozwolone na starcie/końcu dnia).
3. **Cross-city POI** – filtr przed timeline + usuwanie zanieczyszczeń (Loopy’s World Wrocław, JUMPCITY Katowice, Hala Targowa Wrocław, złe regiony Leśna Huta / Krucze Skały) oraz bbox regionu.
4. **Implausible walks** – multi-km w ≤40 min → auto (gdy jest) albo drop.
5. **Duplicate coords** – Zapora/Zbiornik Łomnica itd. scalane do jednego POI.
6. **Posiłki / okno dnia** – late lunch → 13:30; brak kolacji przy dniu ≥17:00 → doklejenie; clip 23:59–23:59 usuwany.
7. **Day cluster** – jeden subregion na dzień (Gdańsk / Sopot / Gdynia albo Karpacz / Szklarska / Jelenia); zmiana miasta tylko po uzasadnionym przejeździe (≥3 km auto).

## Validator
- `scripts/plan_quality_validator.py` – kody hard-fail dla Trójmiasta/Karkonoszy:
  `stale_walk_start`, `implausible_walk`, `generic_hub`, `cross_city_poi`,
  `duplicate_coords_poi`, `missing_dinner`, `late_lunch`, `day_past_window`,
  `zero_duration_clip`, `aba_return_loop`
- Wrocław / Zakopane: nadal pomijane (frozen).
- Kraków / Katowice: dotychczasowe kody #366 bez zmian regresji.

## Świadomie nie ruszane / decyzja właściciela
- **Twarde fail stacked free_time** – silnik nadal może mieć pojedyncze bloki ≤60 min; #367 nie failuje stosów globalnie (jak #366: aba_hop raportowy).
- **Soft profile (zima/dziecko/senior)** – częściowo pokryte istniejącymi sealami remaining-city; pełne gwarancje preferencji to osobna decyzja.
- **Poznań** – seal #367 nie obejmuje Poznania (scope = Trójmiasto + Karkonosze), żeby nie ruszać bramek overlap/car_teleport.

## Pliki
- `app/application/services/plan_service.py` – `_seal_fix367_uat_day`, helpery regionu, rozszerzony `_strip_wrong_city_attractions`
- `scripts/plan_quality_validator.py`
- `tests/test_fix367_trojmiasto_karkonosze_uat.py`
- `tests/test_fix367_plan_validator.py`
- `docs/INFO_KLIENTKA_FIX367_TROJMIASTO_KARKONOSZE.md`
- opcjonalnie `tests/test_gate_trojmiasto.py` + hook pre-push

## Regresja
Nowe testy #367 + bramki Kraków / Katowice zielone względem baseline; Wrocław/Zakopane nietknięte.
