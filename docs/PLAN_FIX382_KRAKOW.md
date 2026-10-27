# FIX #382 — Kraków, kolejna runda maila

Pieczęć `_seal_fix382_krakow_client` stoi za #381. Wchodzi tylko Kraków. Wrocław i Zakopane zostają nietknięte.

- Plac Bohaterów Getta jest bezpłatny i trwa najwyżej 40 minut. Przy rodzinie z dziećmi i preferencji dzieci albo przyrody schodzi z dnia.
- Pixel XL schodzi, gdy nie pokrywa żadnej wybranej preferencji. Brak wiersza w bazie nie wyrzuca go rodzinie z dziećmi.
- Podziemia Rynku zaczynają się o 10:00. Dojście rozciąga się do tej godziny, a minuty zabiera późniejszy postój przed lunchem, żeby lunch nie odjechał. Gdy nie ma skąd ich wziąć, cały ogon dnia przesuwa się później.
- Muzeum Narodowe (nie Sukiennice) kończy się do 18:00. Za krótka wizyta po obcięciu schodzi.
- Muzeum zamknięte w poniedziałek schodzi także w środku dnia. #381 zostawiał je, gdy nie dało się przepiąć objazdu.
- Wyjazd do Wieliczki tylko po krótki Rynek Górny schodzi nawet wtedy, gdy kopalni nie było wcześniej.
- Dzień 2 zostaje w Krakowie, gdy któryś późniejszy dzień jest jeszcze w mieście. Zamiana bierze całe dni, data zostaje przy numerze. Wyjazd dwudniowy nie ma z czym się zamienić.
- Kolacja, która nosiła nazwę atrakcji z tego dnia, wraca do „Kolacja”. Odcinek, który istniał tylko pod tę nazwę, schodzi. Dziurę przed kolacją zamyka do trzech punktów w zasięgu spaceru, otwartych tego dnia. Gdy okna dnia nie da się dociągnąć spacerem, wcześniejszy postój oddaje minuty ze swojego limitu. Kolacja o 17:00, i trzy godziny po lunchu, jest wymuszana tylko gdy dzień trwa do 19:00 albo dłużej.

Bramka Krakowa pilnuje teraz `square_cost`, `square_long`, `offpref_square`, `offpref_pixel`, `before_open`, `after_close` dla Muzeum Narodowego, `dinner_as_stop`, `short_return` bez warunku wcześniejszej kopalni i `day2_out`.
