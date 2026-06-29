# FIX #224 — Warszawa (29.06.2026)

Poniżej co zostało poprawione w odpowiedzi na uwagi do Warszawy.

## 1. Bardzo krótkie wizyty i kolacja na kilka minut (uwagi #5, #8)

**Diagnoza:** Łazienki 14 min, Muzeum Wojska 5 min, Ogrody Zamku 21 min oraz
„kolacja 9 min" pochodziły z tego samego miejsca — `DAY_END ENFORCER`. Gdy punkt
wychodził poza koniec dnia, był przycinany i zostawiany, jeśli zostawało
„≥ 5 min". Dlatego powstawały takie kikuty.

**Poprawka:** wprowadziłem minimalny próg zależny od typu pozycji:
- kolacja / obiad: min. **30 min** (poniżej → pozycja jest usuwana, nie skracana),
- atrakcja: min. **25 min**,
- pozostałe (czas wolny, dojazd): bez zmian.

Efekt: nie pojawiają się już 5-/14-minutowe muzea ani 9-minutowe kolacje —
jeśli czas się nie mieści, pozycja jest pomijana, a nie pokazywana jako kikut.
Pełne czasy zwiedzania (np. Łazienki 60 min, Muzeum Wojska 90 min) wynikają
teraz z bazy i nie są ścinane.

## 2. Zbyt wysoki ranking / uniwersalne wypełniacze (uwaga #2)

Dodane do listy „quick-stop" (tracą bonus must-see, są traktowane jak punkty
fotograficzne, a nie główne atrakcje):
- **Kopiec Powstania Warszawskiego**
- **Manufaktura Cukierków**
- **Pijalnia Czekolady E. Wedel**

(Muzeum Fabryki Norblina, Plac Europejski, Pomnik Syreny, Most Świętokrzyski,
Grób Nieznanego Żołnierza, Pałac Prezydencki, Browary Warszawskie były już
wcześniej zdemotowane w FIX #222/#223.)

## 3. Brak największych atrakcji przy profilu cultural (uwaga #4)

Wzmocniłem premię dla flagowych atrakcji miasta (Łazienki Królewskie, POLIN,
Pałac Kultury i Nauki, Muzeum Powstania, Zamek Królewski, Muzeum Narodowe):
- bonus podniesiony z 85 → **130 pkt** (pierwsze 3 dni) / 55 → **90 pkt** (dalej),
- dodatkowo **+40 pkt** dla prawdziwych ikon `must_see ≥ 9`,
- premia działa teraz także dla preferencji `history_mystery`, nie tylko
  `museum_heritage` / stylu `cultural`.

## 4. Błędne dopasowania preferencji (uwagi #7, #11, #12)

Reguły pokrycia preferencji (`preference_coverage`):
- **Jeziorko Czerniakowskie** — nie liczy się już jako `active_sport` ani
  `history_mystery`.
- **Pijalnia Wedla / Manufaktura Cukierków** — nie liczą się jako `underground`
  ani `history_mystery` (wcześniej już wykluczone z `active_sport`,
  `museum_heritage`, `water_attractions`).
- **ZOO** — wykluczone z `history_mystery` / `underground` (przy profilu
  nastawionym na historię i eksplorację).
- **Kopiec Powstania** — wykluczony z `active_sport` (już wcześniej z `water`/
  `relaxation`).

## 5. Centrum Nauki Kopernik przy profilu solo (uwaga #9)

Mimo że baza dopuszcza `solo`, dodałem twardy filtr nazwy — **Centrum Nauki
Kopernik nie pojawi się w planie solo** (pozostaje dostępne dla rodzin/par).

## Uwagi przekrojowe (#1, #3, #6, #10)

- **Free Time / rozkład preferencji / styl relax** — mechanizmy wzmocnione w
  FIX #222/#223 (silniejsze premie za rozkładanie preferencji na kolejne dni,
  agresywniejsze domykanie luk, premia za realny relaks zamiast pustego czasu)
  pozostają aktywne. Dla części profili Warszawy ograniczeniem jest sama pula
  atrakcji (np. natura to praktycznie Łazienki, Wilanów, Ogrody Zamku) — tutaj
  pomoże dalsze uzupełnienie bazy o tereny zielone.

## Testy

`tests/test_fix224_client_feedback.py` — quick-stop dla Kopca/Manufaktury/Wedla,
pokrycie preferencji dla Jeziorka i Wedla, wykluczenie Kopernika dla solo.
Regresja FIX #221/#222/#223 — bez zmian (przechodzą).
