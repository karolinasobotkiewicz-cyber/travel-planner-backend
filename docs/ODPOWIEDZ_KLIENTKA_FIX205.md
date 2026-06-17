# Odpowiedź dla klientki — FIX #205 (17.06.2026)

Dzień dobry,

dziękuję — i cieszę się, że dobór atrakcji oceniają Państwo dobrze :)

Skupiłam się na **najczęściej powtarzanym problemie ze wszystkich miast**:
coverage zaniżał liczbę atrakcji (np. „plan ma 6 atrakcji dziecięcych, a coverage
pokazuje 1"; „nature_landscape = false mimo że są takie atrakcje w planie").

## Co naprawione

Sprawdziłam to na realnym planie i przyczyna była jednoznaczna: atrakcje były
poprawnie w planie, ale **system liczenia pokrycia** wymagał dokładnych etykiet,
podczas gdy w bazie tagi są bardzo szczegółowe (np. „turquoise_limestone_lake",
„city_zoo_animals", „large_city_meadow", „historic_city_park", „urban_lake_beach").
Dodałam dopasowanie po słowach kluczowych, więc takie atrakcje są już poprawnie
zaliczane.

Efekt na przykładowym planie rodzinnym Krakowa:
- kids_attractions: **z 3 → 9**
- nature_landscape: **z 0 (false) → 6 (true)**
- relaxation: **z 0 → 3**
- water_attractions: **z 0 → 3**

Co ważne — **nie cofnęłam** wcześniejszych poprawek: Pomnik Smoka, Podziemia
Rynku, Stare Miasto, place i budynki zdrojowe nadal NIE są błędnie zaliczane.
Czyli coverage jest teraz i dokładny, i kompletny.

## Co zostaje na kolejne rundy (większe zmiany lub dane)

Te punkty znam i są na liście — wymagają głębszych zmian w logice układania planu
albo poprawek w danych, więc robię je osobno, żeby nie zepsuć tego, co już działa:

- **Miasto bazowe w klastrze** (Karpacz/Kudowa/Sopot/Gdynia/Gdańsk itd.) — plan
  ma zaczynać i najmocniej premiować miasto bazowe.
- **Profil Adventure** — żeby realnie dawał aktywne/przygodowe atrakcje, a nie
  muzea i starówki; oraz mocniejszy wpływ profilu „friends".
- **Family + Nature** — wodospady i topowe atrakcje przyrodnicze zamiast samych
  sal zabaw; oraz pusty 3. dzień w krótkich planach rodzinnych.
- **relaxation realizowany przez free_time** — wypełnianie luk spa/parkami/basenem.
- **Zbyt dużo free_time** w długich planach.

## Dane do poprawy (po Państwa stronie / w arkuszu)

- **Ogród Botaniczny we Wrocławiu** — współrzędne wskazują okolice Krakowa.
- **Brakujące topowe atrakcje** Trójmiasta (ECS, Muzeum II WŚ, Westerplatte,
  Akwarium Gdyńskie, Dar Pomorza, Bazylika Mariacka).
- **Czarny Kocioł Jagniątkowski** ma 185 min przy stylu „relax" — to atrakcja
  raczej dla „adventure"; do korekty intensywności w danych.

Zakopane bez zmian (10/10 regresji). Czekam na kolejny retest.

Pozdrawiam
