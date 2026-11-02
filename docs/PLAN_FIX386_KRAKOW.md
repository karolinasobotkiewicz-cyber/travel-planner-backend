# FIX #386 — Kraków, mail po #385

Pieczęć `_seal_fix386_krakow_client` stoi za #385. Wchodzi tylko Kraków. Wrocław i Zakopane zostają nietknięte. Każda poprawka dnia zapisuje się osobno.

- Dzień rodziny (dzieci albo natura): najwyżej pięć atrakcji. Najpierw schodzą Kładka, brama, pomnik (poza Smokiem) i Muzeum Etnograficzne, potem najkrótszy postój poza Wawelem i Smokiem. Piąty parking schodzi: przejazd, który tylko zmienia parking bez wysiadania, zlewa się w jeden dojazd. Json 5 zostaje przy trzech parkingach, bo ten dzień nie dostał uwagi.
- Krótszy z dwóch pokazów LEGO na dniu rodziny schodzi jeszcze raz, gdy #385 go przywróciła. Dziura między sąsiadami zamyka się dojściem. Json 3, który ma jeden pokaz, zostaje.
- Lunch ponad 30 minut po progu grupy dosuwa się o tyle, o ile da się skrócić postój przed nim do jego minimum. Koniec lunchu i popołudnie zostają. Lunch tylko kwadrans po progu zostaje.
- Dojazd do Ojcowa liczy obie nogi przy zamku, także gdy pojedyncza ma mniej niż 20 km i co najmniej 20 minut. Gdy suma jest dłuższa niż pobyt i ma co najmniej 40 minut, zamek rośnie do limitu i do końca dnia. Gdy okno tego nie pomieści, zamek schodzi i reszta dnia wchodzi w dziurę.
- Auto, które stoi na jednym parkingu, a następny przejazd startuje z innego, dostaje dojazd z prawdziwego miejsca postoju. Następna atrakcja zostaje o swojej godzinie, gdy łańcuch mieści się w luce.

Dni bez uwag w tym mailu (Json 2, 3, 4, 5, 6, 9, 10) nie dostają osobnej reguły.

Bramka dokłada `family_lots` (piąty parking na dniu rodziny) i dolicza do `far_ojcow` nogi przy zamku krótsze niż 20 km. Kształty z maila trzyma `test_fix386_repairs_mailed_shapes`.
