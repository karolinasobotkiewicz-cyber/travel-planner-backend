# FIX #379 — Kraków, mail z 10 JSON-ów

Zapis ustaleń przed zmianą kodu. Nie commitować diagnostyki (`_diag*`, `_dump*`, `_audit*`). Nie ruszać Wrocławia i Zakopanego. Nie zmieniać globalnych podłóg w `choose_duration` / `visit_duration_hard_cap`, bo te same nazwy jadą w Poznaniu, Katowicach i Warszawie.

HEAD na GitHubie: `cfa638f` (FIX #378). Lokalnie niezacommitowane są `plan_service.py` i `tests/test_gate_krakow.py` — to dalszy ciąg pieczątki #376 (lunch, budżet spaceru, zamek jako ogon dnia). Zostaje. Nowa praca wchodzi w tę samą pieczątkę albo w jedną nową funkcję wołaną na końcu, tylko gdy `_is_krakow_context` i nie `_is_locked_city_context`.

Profile JSON-ów: `json_miasta/Kraków/test-01.json` … `test-10.json`. Bramka: `tests/test_gate_krakow.py`.

## Pięć mechanizmów, nie dwadzieścia łatek

### 1. Długość wizyty: bohater kontra dodatek

Dotyczy: J1 D3 (Park Wodny 75 min, Be Happy i Manufaktura po tyle samo), J4 D4 (zoo 45, Manufaktura 93), J4 D5 (Brama Floriańska 75), J6 D3 (Be Happy i Manufaktura po 75, Ogród Doświadczeń 20), J8 tempo (Matejki 75, Brama 87, Smok 75), J10 D2 (Be Happy + Labirynt 90).

Zasada, tylko Kraków: Park Wodny, zoo i Ogród Doświadczeń trzymają `time_min` z Excela. Dodatki (Be Happy, Manufaktura Czekolady, Lustrzany Labirynt, Brama Floriańska, plac Matejki, Smok) mają krótki cap i nie wchłaniają dziury. Minuty zabrane dodatkowi wracają do bohatera tego samego dnia, bez ruszania lunchu i kolacji.

J4 D3 (Geologiczne kończy się 12:50, Archeologiczne startuje 12:50) to osobny wiersz w tej samej pieczątce: dwa przystanki o tym samym zegarze dostają tranzyt, nawet krótki.

### 2. Lunch w tej dzielnicy i przed deadline z `krakow_client_limits`

Deadline już jest: rodzina 13:30, relax 14:00, balanced 14:30, reszta 14:45. Nie jest dotrzymany: J2 D1 15:25, J7 D1 15:19, J8 D2 15:08.

Pętle to ten sam błąd co spóźniony lunch: restauracja jest daleko od pary przystanków, które są blisko siebie.

Dotyczy: J3 D1 Szpitalna ↔ Wolnica 7,43 km, J7 D1 Katedra / Szpitalna / Wawel / Smok / Szpitalna, J8 D1 Błonia → Kazimierz → Jordan (8,57 km), J8 D2 Barbakan → Podgórze → Krzysztofory (7,37 km, lunch 15:08), J9 D1 Szpitalna → Kazimierz na lunch → Galeria, wieczorem z powrotem na Kazimierz.

Zasada: jeśli dwa przystanki są bliżej siebie niż restauracja każdego z nich, posiłek zostaje między nimi jako przerwa w tej okolicy. Nazwana knajpa nie wyciąga dnia na Kazimierz albo Podgórze i z powrotem. Lunch, który i tak jest po deadline, przysuwa się do ostatniego przystanka przed progiem, bez doklejania postoju i bez 50 m hopu.

### 3. Satelita jest tematem dnia, nie ogonem

Dotyczy: J7 D2 Pieskowa 64 km / 112 min jazdy na 54 min zwiedzania, J9 D2 65 km / 114 min na 70 min (zamek + Maczuga), J8 D5 Wieliczka → Pieskowa 49 km / 75 min, choć Ojców był dzień wcześniej.

Zasada: Ojców, Pieskowa, Maczuga i Wieliczka wchodzą tylko jako blok dnia. Minuty jazdy nie mogą być wyraźnie dłuższe niż wizyta. Okolica odwiedzona wczoraj nie wraca następnego popołudnia po innej wycieczce. Niedokończony fragment w lokalnym diffie („zamek po dniu w mieście to nowy dzień, nie ogon”) zostaje tą zasadą, nie drugą funkcją.

### 4. Krótki dzień i uczciwe preferencje

Dotyczy: J5 D1 dwie godziny i koniec o 13:13 przy oknie do 16:00; Muzeum Geologiczne opisane jako dopasowane, a w planie nie ma nic dla pięciolatka. J8 Pixel XL, Be Happy, Kino 7D przy `nature_landscape`, `local_food_experience`, `museum_heritage`. J10 Be Happy i Labirynt przy `water_attractions`, `local_food_experience`, `relaxation`.

Zasada: popołudniowa dziura w oknie dnia dostaje pobliski POI z puli, który naprawdę pokrywa preferencję. POI spoza preferencji schodzi, jeśli obok jest zamiennik. Opis „dopasowane” nie zostaje przy muzeum, które nie pokrywa `kids_attractions`.

### 5. Parking Ogrodu Botanicznego

J9 D3: parking wymusza 1,96 km tam i z powrotem. Pin parkingu tego jednego miejsca, w `krakow_parking`, a nie nowy model auta.

## Kolejność i bramka

Jedna passa, jeden przebieg `tests/test_gate_krakow.py`. Nowe kody trafień dopisywane do tej bramki, zanim passa wejdzie: `short_hero`, `long_lookaround`, `late_lunch`, `meal_detour`, `far_tail`, `sparse_afternoon`, `pref_mismatch`, `abutting_stops`.

Po zielonym Krakowie, przed jakimkolwiek pushem: bramki Wrocław, Poznań, Katowice (hook `.githooks/pre-push`). Push tylko z `travel-planner-backend` na `origin`. Folder nadrzędny nie ma remote.

## Co pokazał przebieg 10 JSON-ów (23.10.2026, lokalna pieczątka #376)

Mail opisuje plany sprzed tej pieczątki. Na aktualnym kodzie nie ma już pętli Szpitalna–Wolnica, lunchu o 15:25, zoo 45 min, Bramy na 75 min, Smoka na 75 min ani ogona 64 km na 54 min zwiedzania. Park Wodny ma 136 min, zoo 153, Ogród Doświadczeń 90. Bramka WATCH (teleport auta, overlap, missing_hop) jest czysta.

Zostaje:

- Json 5 dzień 1 kończy atrakcje o 14:15 przy oknie do 16:00. To jedyne okno ≤ 16:30, więc dopełnienie jednym spacerem (bez auta, tylko POI pokrywające preferencję, zimą bez parku) nie dotyka pozostałych dziewięciu JSON-ów.
- Trzy trafienia `lunch_after` (J1 D2, J1 D3, J3 D2) przy lunchu o czasie. Przesuwanie tego lunchu rozcinałoby dzielnicę, czyli wracałby błąd z maila. Kod zostaje, a bramka zgłasza `lunch_after` tylko gdy lunch jest też po progu `late_lunch`.

Geologiczne i Archeologiczne stykają się o tym samym zegarze, ale w Excelu dzieli je 12 m, więc walidator traktuje to jako jeden dziedziniec i nie żąda hopu. Nie ruszam pinów, bo przeliczyłyby dojazdy w innych dniach.

## Świadomie nie w tej rundzie

Przepisywanie `build_day`. Globalne capy Manufaktury (75) i podłogi zoo / Parku Wodnego — one już są i inne miasta na nich stoją. Kraków i tak je potem skraca albo rozciąga w pieczątce, więc korekta jest na końcu dnia, nie w silniku wspólnym.
