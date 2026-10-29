# FIX #384 — Kraków, mail po #383

Pieczęć `_seal_fix384_krakow_client` stoi za #383. Wchodzi tylko Kraków. Wrocław i Zakopane zostają nietknięte. Godziny z #383 (koc 16:00 / 17:00) zostają w tamtej pieczęci. Obwarzanek i Geologiczne obsługuje ta.

- Dzień rodziny z dzieckiem, gdy w preferencjach jest kids albo nature: co najwyżej pięć atrakcji. Etnograficzne schodzi. Kładka, brama i pomnik schodzą, gdy nie pokrywają kids ani nature. Smok zostaje. Dwa postoje LEGO, klocków albo Świata w Budowie: zostaje dłuższy. Wizyta klocków krótsza niż 30 minut schodzi.
- Dziura przed posiłkiem, której w pierwotnym dniu nie było, zamyka się jednym otwartym postojem z preferencji. Zimą wchodzi też park, gdy auto dojeżdża bez nowego parkingu w już użytej okolicy i bez pary rozdzielonej dalszym środkiem. Json 1, dzień 1: Park Bednarskiego schodzi, w jego miejsce Park im. Henryka Jordana przez Parking al. 3 Maja.
- Muzeum z oknem (0, 0) tego dnia, poza Ojcowem i Pieskową Skałą: dojście, które na nie prowadziło, celuje w następny postój, gdy spacer mieści się w limicie dnia. Gdy następny postój jest dalej niż limit, w slot zamkniętego muzeum wchodzi otwarty punkt z preferencji, ze spacerem z poprzedniego postoju i spacerem do następnego. Niedziela Json 4, dzień 3: Muzeum Geologiczne schodzi, w slocie są Podziemia Rynku (Wawel → Krzysztofory to 1,25 km przy limicie 1,2). Niedziela Json 6: dojście z Groblach do Muzeum Archeologicznego mieści się w limicie seniorów.
- Obwarzanek w dzień roboczy kończy się do 16:00 i trwa około godziny. Wizyta, która zaczyna się po zamknięciu, schodzi. Dziura przed kolacją zamyka się powrotem na ostatni parking i jednym dojazdem do otwartego punktu z preferencji.
- Lunch przyjaciół przysuwa się tylko razem z dojściem tuż przed nim, do progu tej grupy.
- Pętla parkingu zwija się, gdy drugi spacer prowadzi do atrakcji stojącej zaraz za nim. Dojście z parkingu na lunch zostaje.
- Spacer z parkingu bez wcześniejszego auta, gdy parking leży tuż przy hubie, zwija pętlę. Samochód miejski poniżej 0,8 km nie wchodzi.
- Ojców i Pieskowa Skała zostają na dniu, gdy zdjęcie zostawia większą dziurę niż sam dojazd. Długi dojazd na krótką wizytę, który po zdjęciu psuje poranek, wraca do pierwotnego dnia.

Dzień rodziny trzyma pięć atrakcji i filtr wypełniaczy. Trzeci parking zostaje, gdy jego zdjęcie urywa łańcuch auta.

Dni bez uwag w tym mailu (Json 2, 3, 5, 9, 10 oraz reszta Json 6 poza niedzielnym muzeum) zostają w swojej kolejności, gdy już spełniają reguły.

Bramka Krakowa pilnuje `family_pace`, `family_filler`, `double_bricks`, `closed_sunday`, `after_close` dla Obwarzanka oraz `parking_loop` tylko przy drugim spacerze wprost do następnej atrakcji. Kształty z maila trzyma `test_fix384_repairs_mailed_shapes`.
