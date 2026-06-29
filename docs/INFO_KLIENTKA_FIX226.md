# FIX #226 — Katowice (29.06.2026)

Najważniejsze ustalenie: puste i krótkie dni w Katowicach miały **przyczynę
w danych** — w bazie jest tylko **21 atrakcji dla Katowic**, a miasto (w
odróżnieniu od Trójmiasta, Karkonoszy czy Kotliny Kłodzkiej) **nie miało
zdefiniowanego klastra**. Przy planie 3-dniowym pula wyczerpywała się po 1-2
dniach → dzień kończył się o 12:00 albo był pusty.

## 1. Puste / krótkie dni (uwagi #1, #7, #12, #17) — przyczyna danych + klaster

Dodałem **klaster GZM „Górny Śląsk"** (jak Trójmiasto): Katowice + Gliwice +
Zabrze + Chorzów + Tychy, połączone gęstą komunikacją miejską i traktowane jako
**jedna destynacja**.

- Pula POI dla wyjazdu „Katowice" rośnie z **21 → 51** atrakcji.
- To wystarcza, by zapełnić 3-4 dniowe plany bez pustych dni i bez kończenia
  dnia po 2-3 atrakcjach.
- Klientka sama wspominała wcześniej „Rynek w Gliwicach" i „Park Kościuszki" —
  teraz wchodzą one naturalnie do planu Katowic.

> Uwaga: docelowo i tak warto dosypać do bazy więcej atrakcji śląskich
> (zwłaszcza relaxation / water / active_sport — patrz niżej), bo ich liczba
> wciąż jest niewielka.

## 2. Kościoły wszędzie i otwierają dzień (uwaga #3)

- **Kościół św. Michała** — już wykluczony z `family_kids`.
- **Ogólna kara** dla kościołów/kaplic/parafii (−60), gdy profil nie jest
  historyczny/heritage (prawdziwe katedry-ikony z must_see ≥ 9, jak Mariacka,
  pozostają nietknięte). Dzięki temu kościoły nie otwierają już dnia w planach
  np. rodzinnych czy aktywnych.

## 3. Za dużo muzeów dla profili bez museum_heritage (uwagi #8, #15)

Kara dla muzeów (−45), gdy `museum_heritage` / `history_mystery` nie są wybrane,
a styl nie jest `cultural`; dodatkowo −50, jeśli tego dnia było już muzeum.
To rozładowuje „dużo muzeów przy active_sport / adventure".

## 4. Spodek / Planetarium / Pixel XL (uwagi #11, #13)

Dodatkowa kara (−55) dla Spodka, Planetarium i Pixel XL — przestają być
uniwersalnym wypełniaczem (szczególnie przy underground + history + museum).

## 5. ZOO przy profilu pary cultural/museum/relaxation (uwaga #4)

Kara dla ZOO już obejmuje profile z `museum_heritage` / `history_mystery` /
`cultural` (−110) — Śląskie ZOO nie wchodzi już do takiego planu.

## 6. Lunch 90 min (uwaga #9)

Domyślny lunch skrócony z **90 → 60 min** (z przeliczeniem godziny zakończenia).
Już nie „zjada" środka dnia.

## 7. Rynek 35 min (uwaga #10)

Rozszerzyłem podłogę czasu wizyty (z FIX #225) o rynki / starówki / dzielnice
(np. Nikiszowiec) i zamki → **min. 45 min** zamiast 35.

## Preferencje przez cały pobyt (uwagi #2, #5, #6, #14, #16)

Mechanizm rozkładania preferencji (FIX #222/#223) działa, ale dla Katowic
głównym ograniczeniem była **mała pula** (relaxation ~3, water ~1, active ~7
POI dla samych Katowic). Wraz z klastrem GZM dochodzą atrakcje z Gliwic/Zabrza/
Chorzowa/Tychów, co daje materiał do rozłożenia tych preferencji na kolejne dni.
Pełna stabilność relaxation/water/active będzie wymagała dosypania kilku
atrakcji tego typu do bazy (szczególnie water_attractions).

## Testy

`tests/test_fix226_client_feedback.py` — klaster GZM (Katowice→Gliwice/Zabrze/
Chorzów/Tychy), demotowanie kościołów i Spodka.
Regresja FIX #221–#225 — 46 testów przechodzi, bez regresji.
