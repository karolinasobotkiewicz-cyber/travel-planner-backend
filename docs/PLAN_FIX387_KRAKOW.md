# FIX #387 — Kraków, mail po #386

Pieczęć `_seal_fix387_krakow_client` stoi za #386. Wchodzi tylko Kraków. Wrocław i Zakopane zostają nietknięte. Każda poprawka dnia zapisuje się osobno. #383–#386 nie są ruszane.

- Po zamku w dolinie, gdy do następnego posiłku albo atrakcji zostaje co najmniej 40 minut pustego czasu, wchodzi jeden otwarty sąsiad w zasięgu spaceru (Maczuga Herkulesa przy Pieskowej Skale). Kolacja zostaje o swojej godzinie, poranny zegar zamku też. Pusty czas spada poniżej 40 minut.
- Gdy dojazd do Ojcowa w obie strony ma co najmniej 40 minut i jest dłuższy niż pobyt, albo w dolinie stoi tylko jeden zamek, przed powrotem dochodzi drugi otwarty postój tej samej wycieczki. Zegar zamku się nie przesuwa. Gdy suma pobytu nadal przegrywa z dojazdem, wchodzi trzeci, o ile okno i powrót się mieszczą. Zamknięta zimą jaskinia nie wchodzi.
- Auto, które stoi na Szpitalnej, a następny przejazd rusza z Groblach, dostaje dojście do prawdziwego parkingu, gdy spacer się mieści. Gdy spacer jest dalszy niż limit grupy, skok z Groblach schodzi razem z atrakcją, która go wymagała, a dziura zapełnia się postojem w zasięgu ludzi. Następna atrakcja zostaje o swojej godzinie, gdy łańcuch mieści się w luce.

Dni bez uwag w tym mailu (Json 2–7, 9, 10 i pozostałe dni Json 1 oraz Json 8) nie dostają osobnej reguły.

Bramka dokłada `valley_gap` (puste ≥40 minut po postoju w dolinie) i `thin_ojcow` (jeden postój w dolinie przy dojeździe ≥40 minut dłuższym niż pobyt). Kształty z maila trzyma `test_fix387_repairs_mailed_shapes`.
