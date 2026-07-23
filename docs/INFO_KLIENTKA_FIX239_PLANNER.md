# FIX #239 — planner po ponownych testach klientki (23.07.2026)

## Problemy zgłoszone (powtarzające się)

1. Duże luki 1,5–3 h w harmonogramie  
2. Częsty blok **Free Time**  
3. `routing_source: "haversine"` na przejazdach  
4. Przejazdy z `geometry: null` / `routing_source: null`  
5. Brak przejazdu między atrakcjami / długa przerwa  

## Co zrobiono (kolejność wdrożenia)

### Punkt 3–4 — routing (test: audyt transitów na JSON)

- `_run_transit_routing_pass` — jednolita pętla: brakujące przejazdy → korekta `from`/`to` → deduplikacja → wzbogacenie ORS/cache → **normalizacja** metadanych.
- `_normalize_transit_routing_item` — każdy transit ma `routing_source` (nigdy `null`); jazda ≠ `haversine` (→ `estimated_road` / `ors`); brak geometrii → linia z współrzędnych atrakcji.
- `_attach_route_metadata` — jazda drogowa nie zostaje z etykietą `haversine`.
- Mapa współrzędnych `_final_coord_map` uwzględnia też `Lat`/`Lng` z Excela.
- Po `validate_and_heal_timeline` routing jest **ponownie** liczony (wcześniej metadane znikały).

### Punkt 5 — brakujące przejazdy (test JSON)

- Druga (i końcowa) passa `_run_transit_routing_pass` po afternoon top-up i po finalizacji dnia.
- Wstrzykiwanie przejazdów między atrakcjami (FIX #235/#238) z przesuwaniem harmonogramu przy zerowej luce.

### Punkt 2 — Free Time (test JSON)

- `_apply_free_time_final_hygiene` na końcu pipeline (miasto: max 12 min łącznie / blok; poza miastem: 25).
- `_strip_inter_attraction_free_time` — usuwa duże bloki free_time **między** atrakcjami po top-up.

### Punkt 1 — duże luki (test JSON)

- `_collapse_excessive_timeline_slack` — jeśli między kolejnymi pozycjami jest >25 min pustki, reszta dnia jest przesuwana wcześniej (kolacja/free_time nie „wiszą” 2 h po ostatniej atrakcji).

## Testy regresji klientki

- Moduł: `app/application/services/plan_client_audit.py`
- Pytest: `tests/test_fix239_client_json_audit.py` (50 plików: Wrocław, Warszawa, Kraków, Katowice, Poznań × test-01…10)
- Skrypt lokalny (szybki raport): `scripts/_audit_all_client_json.py`  
- **Wynik po FIX #239: 50/50 OK** (audyt: routing, brakujące transity, free_time, luki >90 min)

## Dla klientki (skrót)

Routing na mapie i w JSON powinien być spójny (`ors` / `estimated_road`, geometria wypełniona). Przejazdy między atrakcjami są domykane na końcu generowania planu. Free Time i wielogodzinne „puste” przerwy przed kolacją są mocno ograniczane; popołudnia w miastach nadal zależą od bazy POI — przy konkretnych JSON-ach z problemem można dołożyć atrakcje w Excelu.
