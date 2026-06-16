# Odpowiedź dla klientki — FIX #204 (16.06.2026)

Dzień dobry,

dziękuję za drugą, bardzo dokładną rundę testów. Część zgłoszeń naprawiłam od
razu w silniku, część wymaga albo większych zmian, albo poprawek w danych —
rozpisuję to jasno poniżej.

## Naprawione teraz (w silniku)

1. **Szlaki górskie (mountain_trails) zaliczane przez parki miejskie** —
   Park Kościuszki / Park Śląski / Park Chopina w Katowicach **nie są już**
   liczone jako szlaki górskie. Dodałam ścisłą listę tagów „naprawdę górskich".

2. **History Mystery zbyt szerokie** — budynki i place uzdrowiskowe
   (Plac Zdrojowy, Dom Zdrojowy) oraz deptaki/mola **nie trafiają już** do
   history_mystery. Twierdze, katedry, Ostrów Tumski itp. pozostają (poprawnie).

3. **Mikro-POI jako główne atrakcje + błędne „must_see"** — place, pomniki,
   kładki, mosty, tarasy widokowe są teraz traktowane jako krótkie przystanki:
   tracą sztuczne wywyższenie i **nie dostają już odznaki „must_see"**
   (np. Plac Ratuszowy w Jeleniej Górze). Najważniejsze atrakcje z realnie
   wysoką oceną (np. Rynek Główny w Krakowie, Molo, Bulwar) **pozostają**
   pełnoprawne — celowo ich nie ruszyłam, bo o część z nich Pani prosiła.

4. **Sezonowość (Dyniolandia w lutym)** — uszczelniłam dostawianie atrakcji:
   etapy „dopełniania planu" również filtrują teraz po sezonie. Działa to dla
   atrakcji, które mają w danych wpisaną sezonowość (patrz niżej).

## Wymaga kolejnej iteracji (większe zmiany w logice)

- **Skakanie między miastami w jednym dniu** (Trójmiasto) oraz **pełne
  rozłożenie klastra na dni** (dzień = jedno miasto).
- **Family Kids + natura** — żeby dla rodzin natura to były też łatwe wodospady,
  a nie tylko Ogród Bajek/sale zabaw; oraz **pusty 3. dzień** w krótkich planach
  rodzinnych.
- **relaxation realizowany przez free_time** — żeby luki wypełniać spa/parkami/
  basenem zamiast zostawiać wolny czas.
- **Długie plany 5–7 dni** — szersza eksploracja regionu (częściowo zależne od
  liczby atrakcji w bazie).

## Wymaga poprawy danych (nie silnika)

- **Ogród Botaniczny we Wrocławiu** ma w danych współrzędne spod Krakowa —
  trzeba poprawić GPS w arkuszu.
- **Brakujące topowe atrakcje** Trójmiasta (Europejskie Centrum Solidarności,
  Muzeum II Wojny Światowej, Westerplatte, Akwarium Gdyńskie, Dar Pomorza, Hel,
  Park Oliwski) — do dodania/dowartościowania w arkuszu.
- **Brama Chlebnicka** jest w danych otagowana jako „hidden_history /
  fortyfikacje", więc nadal liczy się do history_mystery — jeśli ma nie liczyć,
  poprawimy tagi w Excelu.
- **„Dyniolandia"** — jeśli w arkuszu nie ma wpisanej sezonowości, filtr jej nie
  złapie; trzeba uzupełnić sezon dostępności.

Zakopane bez zmian (10/10 regresji). Czekam na kolejny retest.

Pozdrawiam
