# FIX #227 — Poznań (30.06.2026)

Poznań ma w bazie **69 atrakcji dla samego miasta** (53 dostępne dla
`family_kids`, ~22 natura, ~17 relaxation), więc — inaczej niż Katowice —
problemy NIE wynikają z braku danych, tylko z **rozkładu i priorytetów**.

## 1. Pusty ostatni dzień w planach 5- i 7-dniowych (uwagi #3, #12) — kluczowa naprawa

Przyczyna: mechanizm „ratujący" rzadkie/puste dni (FIX #160/#213) działał
**tylko dla miast w klastrach** (Trójmiasto, Karkonosze…). Poznań jest miastem
pojedynczym, więc ten retry **nigdy się nie uruchamiał** — a globalny zakaz
powtórek (dedup) potrafił „wyczyścić" pulę na ostatni dzień → dzień pusty.

Dodałem **retry dla miast pojedynczych**: jeśli późny dzień ma < 3 atrakcje,
planner próbuje go zapełnić ponownie, **dopuszczając powtórzenie atrakcji
sprzed ≥ 2 dni** (powtórzona ikona jest dużo lepsza niż pusty dzień).

Wynik testu (Poznań 7 dni, profil relax + nature):
- **Dzień 7: 0 → 5 atrakcji**
- **Dzień 5: 2 → 4 atrakcje**
- żadnego pustego dnia.

## 2. Kolacja 90 min (uwaga #7)

Domyślna kolacja skrócona z **90 → 60 min** (z przeliczeniem godziny
zakończenia) — analogicznie do lunchu z FIX #226.

## 3. Profil family_kids (uwagi #4, #5, #13, #14, #15)

- **Bazylika Archikatedralna**, **Domy Kupieckie**, **Escape Room** — wykluczone
  z planów `family_kids`.
- **Escape Room** dodatkowo twardo odrzucany dla małych dzieci (≤ 6 lat) —
  jak laser tag.
- **Ikony rodzinne Poznania** (Brama Poznania, Rogalowe Muzeum, Termy
  Maltańskie, Nowe/Stare Zoo) — premiowane dla `family_kids`, żeby realnie
  wchodziły do planu rodzinnego.

## 4. Za wysoki priorytet drobnych POI (uwagi #10, #16, #21, #25)

Demotowane jako „uniwersalny wypełniacz":
**Pomnik Bamberki, Makiety Dawnego Poznania, Okrąglak, Rynek Jeżycki, Pixel XL**.

## 5. PIXEL XL w underground / history / museum na 15 min (uwaga #21)

- Pixel XL / arcade / escape room / kino 7D **przestają zaliczać** preferencje
  `underground`, `history_mystery`, `museum_heritage` (nie „udają" już muzeum).
- Pixel XL trafił też na listę wypełniaczy (niższy ranking).

## 6. Kościoły i bazyliki (uwagi #1, #18)

Działa ogólna kara dla kościołów/kaplic/bazylik (z FIX #226) dla profili
nie-historycznych. Prawdziwe ikony (Bazylika Archikatedralna, must_see ≥ 9)
pozostają dla profili kulturowych, ale są wykluczone z `family_kids` (pkt 3).

## 7. Relaxation / nature przez cały pobyt (uwagi #6, #11, #17, #23, #27)

Mechanizm rozkładania preferencji (FIX #222/#223) + naprawa pustych dni (pkt 1)
sprawiają, że profile relax/nature dostają teraz dużo parków i terenów
zielonych każdego dnia (w teście 7-dniowym m.in. Cytadela, Park Wilsona,
Palmiarnia, Park Sołacki, Arboretum w Kórniku, Jezioro Maltańskie) zamiast
jednej atrakcji i Free Time.

## Pozostałe uwagi — status

- **#2, #19, #24 (Free Time / start dnia / 3 bloki Free Time pod rząd)** —
  działają mechanizmy z FIX #222 (`_strip_leading_free_time`, cap 60 min,
  konsolidacja). Naprawa pustych dni dodatkowo ogranicza Free Time na końcu.
- **#8 (przerwa przed kolacją)** — krótszy domyślny blok + konsolidacja.
- **#9 (trzy identyczne „Kolacja i spacer")** — wynika z pustych slotów; po
  zapełnieniu dni (pkt 1) takich powtórzeń jest znacznie mniej.
- **#20, #22 (adventure / muzea przy friends, adventure)** — kara dla muzeów
  bez `museum_heritage` (FIX #226) ogranicza dominację muzeów; `adventure`
  zależy od liczby POI tego typu w bazie (w Poznaniu są tylko ~2).
- **#26 (Plaża w Puszczykowie, 16 km na 35 min)** — do rozważenia osobno:
  to atrakcja spoza Poznania; rekomendacja, by traktować ją jak wyjazd
  dzienny (dłuższa wizyta) albo wykluczyć z krótkich planów miejskich.

## Testy

`tests/test_fix227_client_feedback.py` — Escape Room (dziecko + family_kids),
Bazylika/Domy Kupieckie dla family_kids, ikony rodzinne, demotowanie
Pomnika Bamberki, Pixel bez pokrycia underground/history/museum.
Regresja FIX #221–#226 — wszystkie testy przechodzą, bez regresji.
E2E Poznań 7 dni — brak pustych dni (dzień 7: 0→5 atrakcji).
