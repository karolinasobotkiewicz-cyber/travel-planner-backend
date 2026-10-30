# FIX #385 — Kraków, mail po #384

Pieczęć `_seal_fix385_krakow_client` stoi za #384. Wchodzi tylko Kraków. Wrocław i Zakopane zostają nietknięte. Każda poprawka dnia zapisuje się osobno: jeden zły ruch nie przywraca zamkniętego muzeum i nie cofa dobrego zdjęcia.

- Dzień rodziny: drugi pokaz LEGO krótszy niż 30 minut schodzi, z dwóch zostaje dłuższy. Dziura po zdjęciu zamyka się otwartym postojem w zasięgu spaceru.
- Klocki poza dniem rodziny schodzą tylko u pary albo gdy sąsiaduje z nimi MOCAK. W slot wchodzi otwarty postój. Zimą park i bulwar zaczynają się przed 16:30. Gdy przy tym parkingu nie ma wolnego postoju w limicie spaceru, auto które jechało wyłącznie po klocki skręca do innego otwartego punktu, który nie leży tuż przy wcześniejszej atrakcji dnia. Json 7, dzień 2: po MOCAK są Bulwary, start 16:29. Json 8, dzień 4: zamiast Bricks & Figs jest Las Wolski. Json 3 zostaje przy swoim Świecie w Budowie.
- Muzeum z oknem (0, 0) tego dnia nie wraca. Ojców i Pieskowa Skała nie schodzą tylko dlatego, że okno jest (0, 0).
- Powrót na ten sam parking między dwoma postojami w zasięgu spaceru zwija się do jednego dojścia. Samochód 0,3–2,0 km między sąsiadami też.
- Lunch rusza się tylko wtedy, gdy start jest ponad 30 minut po progu grupy. Schodzi najkrótszy nieikoniczny postój tuż przed lunchem. Popołudnie zostaje. Lunch około 15 minut po progu zostaje.
- Ojców schodzi, gdy minuty dojazdu w obie strony są dłuższe niż czas na miejscu. Reszta dnia dosuwa się w dziurę, kolacja nie przechodzi progu.
- Pusta przerwa co najmniej 40 minut między dwiema atrakcjami dosuwa dojście i postój. Całe popołudnie i przypięta kolacja nie jadą.

Dni bez uwag w tym mailu (Json 2, 3, 5, 6) zostają w swojej kolejności, gdy już spełniają reguły.

Bramka Krakowa pilnuje `short_bricks`, `offpref_bricks` (para albo sąsiedztwo MOCAK), `idle_gap` od 40 minut, `late_group_lunch` powyżej progu grupy o 30 minut oraz `far_ojcow`. Kształty z maila trzyma `test_fix385_repairs_mailed_shapes`.
