# FIX #380 — Kraków, mail po testach #379

Nowa runda. Nie powtarza pętli Szpitalna–Wolnica ani lunchu o 15:25. Trzy mechanizmy i dwie wąskie reguły. Wszystko w jednej funkcji wołanej na końcu `_seal_fix373_krakow_trip`, po #379. Wchodzi tylko Kraków. Wrocław i Zakopane zostają zamknięte. Globalne `_reset_stale_meal_location_context` i `_align_meal_identity` nie są ruszane, bo z nich korzystają inne miasta, a pieczątka Krakowa i tak nadpisuje je później.

## 1. Jeden posiłek, jedna nazwa, jeden dojazd

Dotyczy: J1 D1, J2 D1, J3 D1, J4 D4, J5 D1, J5 D2, J6 D2, J6 D3, J7 D2, J9 D2, J9 D3, J10 D1.

Dziś etykieta, `location_context` i `suggestions[0]` potrafią nazywać trzy różne lokale, a ciało planu zostaje przy poprzedniej atrakcji. Stąd lunch „przy Błoniach” z Milkbar Tomasza w kontekście i kolejny hop, który znowu startuje z Błoń.

Zasada na końcu dnia:

- Jeśli pierwsza propozycja jest w zasięgu spaceru od poprzedniego postoju, etykieta, `location_context` i propozycja nazywają ten sam lokal. Przed posiłkiem jest hop do jego pinu, a następny hop startuje z tego lokalu.
- Jeśli lokal jest daleko, nazwa dalekiej knajpy schodzi. Zostaje restauracja z tej okolicy albo uczciwa przerwa przy obecnym postoju. Pusta lista i „MIŁA” w kontekście przy zoo (J5 D2) nie mogą żyć obok siebie.
- Etykieta nigdy nie zostaje przy „Czarnej Kaczce”, gdy kontekst mówi Olio, Otto albo Sukiennice.

## 2. Auto nie wraca na parking, na którym jeszcze nie stało

Dotyczy: J1 D3, J2 D2, J4 D2, J7 D1, J7 D2, J8 D6, J10 D2. Wzorzec ten sam: dzień otwiera się pieszo („Kraków → Obwarzanek” albo ogród), a później jest „powrót do auta” na Parking ul. Szpitalna.

Szpitalna jest najbliższym parkingiem Rynku w `start_parking`. Dzień pieszy nigdy tam nie dojechał, a ledger i tak traktuje ją jako miejsce auta.

Zasada: hop autem i „powrót do auta” wolno skierować tylko na parking, który już jest celem wcześniejszego dojazdu w tym dniu. Pierwsze użycie auta po starcie pieszym to dojazd z Krakowa na parking najbliższy celowi, nie powrót na Szpitalną.

J9 D3 (16 min na Starowiślną, potem spacer do Muzeum Motyla) jest tą samą księgą: krótki cel w zasięgu spaceru nie dostaje objazdu przez obcy parking.

## 3. Jeden kierunek wycieczki na dzień

- J8 D5: Wieliczka, a potem 49,5 km / 75 min do Pieskowej. Dzień, który już wyjechał w jedną stronę, nie dokleja drugiej.
- J9 D3: drugi wyjazd do Wieliczki, 16,6 km / 39 min, tylko na 42 minuty Rynku Górnego. Rynek zostaje przy dniu, który już jest w Wieliczce. Osobny dojazd na sam rynek schodzi.

## 4. Dwie wąskie rzeczy, nie nowy scoring

- J4 D5: Ogród Doświadczeń 24 lutego. Sezon obiektu to kwiecień–październik. W zimowym i marcowym dniu Krakowa ten POI schodzi. Innych miast to nie dotyczy.
- J1 D2: sześć atrakcji przy ośmiolatku, w tym po 93 min w MOCAK-u i Muzeum Etnograficznym, przy preferencjach `kids_attractions` i `nature_landscape`. Muzeum, które nie pokrywa żadnej z wybranych preferencji, nie dostaje pełnych 93 minut jako kolejny blok, gdy dzień rodziny ma już cztery postoje. Zamiennik musi być z okolicy i z preferencji. Dziury po wycięciu nie zostawiamy.

## Wdrożone

Pieczęć `_seal_fix380_krakow_mail` stoi za #379 i kończy się przed zwrotem dni.

- Posiłek z propozycją w zasięgu spaceru dostaje jedną nazwę i hop do pinu. Daleka nazwa schodzi, zostaje przerwa przy postoju, przy którym ciało planu już jest.
- Dzień pieszy, który później wraca na parking startowy przy Rynku, nazywa ten parking już na pierwszym hopie.
- Dwa kierunki jednego dnia (Wieliczka i Ojców) nie zostają obok siebie. Samotny krótki Rynek po wcześniejszej Wieliczce też schodzi.
- Ogród Doświadczeń w miesiącach 11–3 jest zdejmowany. Gdy stoi w środku dnia, powrót do auta startuje z poprzedniej atrakcji, a ogon dnia przysuwa się wcześniej. Gdy jest ostatnim punktem, schodzi razem ze spacerem do niego, a kolacja zostaje przy ostatniej atrakcji, nie wcześniej niż o 17:00 i nie wcześniej niż trzy godziny po lunchu.
- Rodzinny dzień z dzieckiem skraca MOCAK albo muzeum etnograficzne poniżej 90 minut, gdy nie pokrywa wybranej preferencji, i nie otwiera dziury większej niż 44 minuty.

Bramka Krakowa po tej pieczęci przechodzi, łącznie z `meal_identity`, `meal_stranded`, `car_spawn`, `second_satellite`, `out_of_season` i `offpref_museum`.
