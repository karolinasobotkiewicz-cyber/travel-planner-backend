# FIX #225 — Kraków (29.06.2026)

Główny wniosek z testów: problem nie leży już w preferencjach, tylko w
priorytetyzacji i logice budowania dnia. Topowe ikony Krakowa (Wawel, Rynek,
Sukiennice, Mariacka, Planty) wypadały z planów, a drugoplanowe POI je wypierały.

## 1. Topowe atrakcje w KAŻDYM planie (uwagi #2, #8, #10, #14, #16)

**Diagnoza:** premia dla flagowych atrakcji działała wcześniej tylko dla profilu
`cultural` / `museum_heritage`. Dlatego przy `family_kids`, `relax`, `nature`
Wawel/Rynek/Mariacka w ogóle nie wchodziły do planu.

**Poprawka:**
- **Uniwersalna premia kotwicy** dla ikon miasta (Wawel, Rynek, Sukiennice,
  Mariacka, Planty, Bulwary…) — działa dla **wszystkich profili**, najsilniej
  w pierwszych dniach (must_see ≥ 9 → +95 pkt). To sprawia, że ikony są
  wybierane jako pierwsze, mocne punkty dnia, a nie pomijane.
- **Premia dla ikon rodzinnych** przy `family_kids`: Smok Wawelski, Wawel,
  Ogród Doświadczeń, Park Jordana, Park Lotników, Zoo (+80 pkt).
- Dzięki temu dzień nie zaczyna się już od Kościoła św. Wojciecha / Kładki
  Bernatka (które pozostają „quick-stop"), tylko od najmocniejszych atrakcji.

## 2. Za krótkie wizyty na najważniejszych atrakcjach (uwaga #5)

**Diagnoza:** Rynek/Bazylika Mariacka/Bulwary/Planty mają w bazie `time_min = 30`,
a generator pozycji używał surowego `time_min` (ignorując czas zarezerwowany przez
silnik — patrz FIX #74). Stąd ~35-minutowe wizyty na ikonach.

**Poprawka:** wprowadziłem **podłogę czasu wizyty** zależną od rangi POI
(z górnym ograniczeniem do `time_max`, więc nigdy nie przekraczamy rezerwacji
silnika):
- ikony / `must_see ≥ 9` (Wawel, Rynek, Sukiennice, Mariacka): min. **60 min**,
- muzea: min. **45 min**,
- parki / bulwary / Planty / kopce: min. **45 min**.

Efekt uboczny: wypełnienie zarezerwowanego slotu redukuje też puste `free_time`
po atrakcji (uwaga #1).

## 3. Skakanie po mapie — klastry wycieczek (uwagi #6, #13)

Dodałem rozpoznawanie **regionów wycieczkowych Krakowa**:
- `region_ojcow` (Ojców, Maczuga Herkulesa, Pieskowa Skała, Jaskinia Ciemna,
  Grodzisko…),
- `region_wieliczka` (Wieliczka / Bochnia / Kopalnia Soli).

Mechanizm „jeden kierunek na dzień" (FIX #183) działa teraz także dla Krakowa —
planner nie pomiesza już w jednym dniu Wieliczki z Maczugą, a atrakcje Ojcowa
zaplanuje razem (Ojców → Pieskowa Skała → Maczuga…).

## 4. Za wysoki ranking atrakcji drugoplanowych (uwagi #3, #9, #11)

Dodatkowa kara (−70 pkt) dla: Muzeum Obwarzanka, Muzeum Geologiczne, Fabryka
Wódki, Pałac Krzysztofory, Be Happy Museum, Kino 7D, Muzeum Żywego Motyla,
Kopiec Krakusa, Lustrzany Labirynt.
- **Wieża Ratuszowa** — usunięta z listy ikon + dodatkowa kara (−75) dla profilu
  **seniorów** (wspinaczka po wąskich schodach wieży).

## 5. Błędne dopasowania preferencji (uwagi #10, #11, #12, #17)

Reguły pokrycia preferencji:
- **Nowa Huta** — nie liczy się jako `water_attractions`, `local_food_experience`
  ani `relaxation`.
- **Fabryka Wódki** — już wcześniej wykluczona z nature/relax/food/water.
- **Park Decjusza** — nie liczy się jako `active_sport` ani `history_mystery`.
- **Lustrzany Labirynt** — nie liczy się jako `museum_heritage` ani `relaxation`.
- **Muzeum Geologiczne** — już wykluczone z `nature_landscape`.

## Uwagi przekrojowe (#1, #7, #15)

- **Free Time** — redukowany dodatkowo przez poprawkę #2 (wypełnianie slotów).
- **Late lunch** — `LUNCH_LATEST` pozostaje na 14:00; obserwujemy po wdrożeniu.
- **Rozkład preferencji relax/nature** — wzmocnione mechanizmy z FIX #223 plus
  nowe reguły pokrycia (Fabryka Wódki/Nowa Huta nie „udają" relaxu) stabilizują
  charakter wyjazdu między dniami.

## Testy

`tests/test_fix225_client_feedback.py` — klastry Ojców/Wieliczka, obecność ikon
w listach, demotowanie POI drugoplanowych, reguły pokrycia.
Regresja FIX #221–#224 — 42 testy przechodzą, bez regresji.
