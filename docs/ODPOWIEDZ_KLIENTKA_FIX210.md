# Odpowiedź — FIX #210 (Trójmiasto)

Dziękujemy za feedback dotyczący Gdańska, Gdyni i Sopotu.

## Co poprawiliśmy

### Koncentracja na mieście bazowym (Gdynia / Sopot)
Gdy wybieracie Gdynię lub Sopot jako punkt wyjścia, planer ładuje teraz cały klaster Trójmiasta, ale **każdy dzień jest przypisany do jednego miasta** (hub-day). Dzień 1 w Gdyni nie powinien już zawierać Molo w Sopocie wymuszonego przez mechanizm „preference guarantee”. Mniejsze miasta (Gdynia, Sopot) dostają też więcej dni w swoim hubie niż Gdańsk (65% vs 55%).

### Mikro-atrakcje w Gdańsku
Żuraw, Złota Brama, Fontanna Neptuna, bramy i podobne punkty są traktowane jako krótkie postoje, nie główne atrakcje dnia.

### museum_heritage vs history_mystery
Rozdzieliliśmy wagę: **Westerplatte, Wisłoujście, Twierdza, Muzeum II WŚ, ECS** dostają silny boost przy odpowiednich preferencjach. Zwykłe kościoły, place i bramy miejskie są karane w `history_mystery` i nie powinny mieć tej samej rangi co fortyfikacje.

### Adventure
Przy `travel_style=adventure` / `active_sport` bez kultury w top-3 — kara za rynek/kościół/plac (-55) i boost za urban active (trampoliny, park linowy, VR itd.).

### Brakujące flagowe miejsca
Muzeum II Wojny Światowej, ECS, Westerplatte i Wisłoujście są w bazie — dodaliśmy **flagship boost**, żeby trafiały do planów przy `museum_heritage` / `history_mystery`.

### Klasyfikacja (Sopot)
- Dom Zdrojowy — nie jako `museum_heritage`
- Opera Leśna — nie jako `nature_landscape`
- Atrakcje z Helu przypisane do Gdyni — to day-tripy z bazy (Hub Gdynia); w planie mają właściwe miasto w danych

### nature / relaxation
Bez `museum_heritage` w preferencjach — kara za muzea/zabytki na rzecz parków i bulwarów.

## Nadal otwarte
- **Duże bloki Free Time** (Sopot 5–7 dni) — częściowa poprawa; pełne dopicie popołudnia to osobna iteracja.
- Dla pełnego mixu 3 miast warto używać `region_type: "cluster"` lub `is_cluster: true`.

## Testy
- `test_fix203.py`: 61/61 PASS

Prosimy o ponowne testy Gdańsk/Gdynia/Sopot (adventure, museum+history, nature+relax, 5–7 dni).
