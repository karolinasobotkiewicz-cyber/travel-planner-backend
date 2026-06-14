# Wiadomość dla klientki — FIX #198–#201 (czerwiec 2026)

> Gotowy szkic do wysłania. Dostosuj powitanie i datę.

---

Cześć Karolino,

Wdrożyliśmy pakiet poprawek silnika (#198–#201) na podstawie Twojego ostatniego feedbacku z testów miast i clusterów. Poniżej podsumowanie — co naprawiliśmy po naszej stronie, a co wymaga drobnych poprawek w Excelu.

---

## Co naprawiliśmy w silniku

### Transity i timeline
- Przejazdy pojawiają się **tylko między atrakcjami z planu** — usunięte transity do POI, których nie ma w danym dniu
- Zamiast „Previous location" w przejazdach — **nazwa poprzedniej atrakcji**
- Atrakcje są lepiej „dociągane" do końca przejazdu (mniej pustych 10–20 minut)
- **Kolacja nie psuje końca dnia** — po uzupełnieniu planu popołudniowego nic nie ląduje już po kolacji

### GPS, parking, adresy
- Atrakcje w odpowiedzi API mają z powrotem **współrzędne i adresy** (wcześniej były puste przez błąd normalizacji)
- Parking: gdy brak osobnego parkingu — **GPS z atrakcji** + opis „Parking w okolicy atrakcji" (miasta)

### Pokrycie preferencji (coverage)
- Rynek, Spodek, deptaki, fontanny **nie liczą się już** jako muzeum, natura ani lokalne jedzenie
- Jaskinie i kopalnie lepiej wykrywane dla preferencji `underground`
- Wodospady, termy, aquaparki lepiej wykrywane dla `water_attractions`
- Opisy „dlaczego wybrano" (`why_selected`) są **zgodne z coverage** — np. nie pojawi się „Relaks" gdy nie masz relaksu w preferencjach

### Klastry (Trójmiasto, Kotlina, Karkonosze)
- Dni są **przypisywane do konkretnych miejscowości** (hub) — np. osobny dzień Gdyni, osobny Sopotu
- Dłuższe pobyty (5–7 dni): więcej dni na miejscowości z większą liczbą atrakcji
- Rodziny z małym dzieckiem (≤5 lat) w Kotlinie: **bez szlaków górskich** (Czarna Góra, Jawornik itd.)

### Must-see i jakość planu
- Krótkie postoje foto (Bamberki, Brama Chlebnicka, Długi Targ jako deptak) **nie dostają już badge must_see** w API

---

## Co prosimy poprawić w Excelu (dane)

Te punkty silnik nie może naprawić sam — wynikają z wartości w arkuszu:

| Atrakcja | Problem | Prośba |
|----------|---------|--------|
| **Fontanna Multimedialna** | `City = Warsaw` | Zmień na **Wrocław** |
| **Spodek** | `must_see = 10`, tagi bez muzeum | Obniż must_see lub dodaj sensowne tagi |
| **Długi Targ, Pomnik Bamberków** | `must_see = 10`, `priority = core` | Obniż do postoju foto (np. must_see 5–6) |
| **Hel / Rewa** | Brak osobnego `hub` | Dodaj `hub = Hel` / `hub = Rewa` przy POI z tych miejsc — wtedy silnik zrobi osobny dzień |

Parkingi w aktualnym pliku (684 POI) mają uzupełnione współrzędne — jeśli nadal widzisz „Brak danych o parkingu", wygeneruj **nowy plan** po deployu (stare wyniki mogą być sprzed poprawki).

---

## Testy

- Zakopane (10 testów klientki): **10/10** — bez regresji
- Miasta + klastry: **10/10** — test gęstości multi-city

---

## Prośba o retest

Proszę wygeneruj **świeże plany** (nie używaj starych JSON-ów) dla:
1. Wrocław 3–4 dni
2. Katowice 2 dni
3. Trójmiasto 5–7 dni
4. Kotlina Kłodzka — family_kids, dziecko 4–5 lat

Sprawdź szczególnie: GPS atrakcji, transity, coverage preferencji, podział dni na Gdynię/Sopot/Gdańsk.

Daj znać co jeszcze nie gra — kolejna iteracja (#202) to m.in. pełny dzień z dojazdem na Hel i dalsza kalibracja must_see w danych.

Pozdrawiam!
