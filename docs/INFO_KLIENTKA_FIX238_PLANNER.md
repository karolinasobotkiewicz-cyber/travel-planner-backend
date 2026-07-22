# FIX #238 — poprawki plannera po testach (22.07.2026)

Odpowiedź na uwagi z ostatniej tury testów. Poniżej co zostało naprawione,
jak i czego dotyczy każda zmiana.

---

## 1. `routing_source: "haversine"` na przejazdach samochodowych — ROZWIĄZANE

Przejazdy samochodowe nie pokazują już `"haversine"`. Fallback drogowy jest
teraz konsekwentnie oznaczany jako `"estimated_road"` (a gdy ORS jest włączony —
`"ors"`). `"haversine"` może pojawić się wyłącznie przy krótkich odcinkach
pieszych (spacer < 1,2 km), gdzie routing drogowy nie ma sensu.

## 2. Przejazdy z `geometry: null` / `routing_source: null` — ROZWIĄZANE

Przyczyną były przejazdy, których punkty końcowe nie były rozpoznane w słowniku
współrzędnych (np. inna nazwa POI albo odcinek z/do hotelu).

- Współrzędne są teraz dociągane również **z samych pozycji atrakcji w planie**
  (każda atrakcja niesie `lat`/`lng`), więc odcinki między atrakcjami zawsze
  dostają geometrię (linia prosta jako minimum) i realny `routing_source`.
- Dla odcinków bez możliwych do ustalenia współrzędnych (etykiety typu „hotel")
  gwarantujemy niepuste `routing_source` (`estimated_road` / `estimated_walk`).

**Żaden przejazd nie wychodzi już z `routing_source: null`.**

## 3. Atrakcja kończy się dokładnie w minucie startu kolejnej (różne lokalizacje) — ROZWIĄZANE

Gdy dwie atrakcje w różnych miejscach stały „na styk" (0 min przerwy), planner
wymuszał brak przejazdu. Teraz, jeśli dostępna luka jest mniejsza niż realny czas
dojazdu, kolejna atrakcja (i cały dalszy plan) jest **przesuwana do przodu** o
brakujące minuty (w granicach czasu do końca dnia), a między nie wstawiany jest
przejazd. Efekt: nie ma już atrakcji „nachodzących" czasowo na siebie w różnych
lokalizacjach.

## 4. Atrakcje sezonowe w miesiącach zimowych — ROZWIĄZANE (kolejna warstwa)

Filtr sezonowości działał w głównej pętli silnika, ale atrakcja mogła wrócić do
planu **po** filtrze — przez podmianę pokrycia preferencji lub popołudniowe
dopełnianie. Dodane zostały dwie bariery:

- podmiana pokrycia preferencji **pomija POI poza sezonem** dla danego dnia,
- na końcu finalizacji dnia działa **siatka bezpieczeństwa**, która usuwa każdą
  atrakcję poza sezonem (po dopełnianiu/podmianach).

## 5. i 6. Przerwy 1,5–3,5 h oraz nadużywanie „Free Time"

Częściowo adresowane powyższymi zmianami (m.in. eliminacja „pustych" luk bez
przejazdu i przesuwanie planu). Pozostałe duże przerwy w konkretnych miastach/
profilach wynikają z **liczby dostępnych POI w bazie** dla danego zestawu
preferencji — planner uruchamia już popołudniowe dopełnianie i zgłasza
ostrzeżenie `day_density_low`, gdy nie ma czym wypełnić dnia. Jeśli prześlecie
konkretne przypadki (miasto + JSON zapytania), dołożymy brakujące POI do bazy lub
dostroimy progi dla tych scenariuszy.

---

## Testy

Nowy zestaw: `tests/test_fix238_client_feedback.py` (routing niepusty, brak
zerowej luki między atrakcjami, filtr sezonowy). Wszystkie zielone; istniejące
testy plannera/routingu bez regresji.
