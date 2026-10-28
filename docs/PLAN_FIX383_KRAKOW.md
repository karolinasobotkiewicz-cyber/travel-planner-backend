# FIX #383 — Kraków, domknięcie maila po #382

Pieczęć `_seal_fix383_krakow_client` stoi za #382. Wchodzi tylko Kraków. Wrocław i Zakopane zostają nietknięte. #382 dalej rozciąga dojście, żeby Podziemia zaczęły się o 10:00. Ta pieczęć oddaje spacerowi prawdziwe minuty i zostawia godzinę przyjścia.

- Spacer od 0,4 km, który trwa ponad dwanaście minut dłużej niż dystans, wraca do czasu marszu. Koniec zostaje, więc wizyta nie rusza się wcześniej. Gdy przed pierwszym spacerem zostaje co najmniej 40 minut, wchodzi jeden otwarty postój w obie strony, z powrotem na ten sam parking.
- Lunch dłuższy niż 75 minut jest ścinany do godziny od swojego startu. Ogon dnia nie jedzie do tyłu.
- Ogród Doświadczeń schodzi w miesiącach 11–3 także wtedy, gdy nie ma czym go zastąpić.
- Kolacja, która nazywa się Muzeum Narodowe albo atrakcją z tego dnia, wraca do „Kolacja”. Odcinek za ostatnią atrakcją, który wiódł tylko pod tę nazwę, schodzi.
- Rodzina z dziećmi nie dostaje MOCAK-u ani Etnograficznego jako wypełniacza, a wydłużenie tych dwóch kończy się przed 90 minutami.
- Zamek na Wawelu (nie Smok) i Pieskowa Skała: wizyta razem z dojściem, które tylko jej służy, wsuwa się tak, by start był do 16:00, a koniec do 17:00. Nic za następnym postojem nie jedzie. Dojazd od 20 km, przy którym skrócona wizyta byłaby za krótka na ten dystans, nie jest wsuwany — schodzi zamek i ten dojazd.
- Zamek, który i tak dobija do 17:00, a kolacja jest jeszcze później, zostaje przy 45 minutach. Zwolnioną godzinę bierze muzeum na pełną godzinę, z którego da się dojść pieszo do nazwanej kolacji.
- Wypełniacz nie siada w parze bliższej niż 0,7 km, gdy pomiędzy jest postój dalej niż 1,2 km od obu. Sąsiad ostatniego postoju zostaje.
- Dziurę przed kolacją bez nazwy miejsca zamyka dojazd samochodem do jednego otwartego punktu w środku. Las i inne zimowe plenery nie wchodzą. Dojazd nie przekracza 25 km i nie jest dłuższy niż sama wizyta. Nazwana kolacja nie jest porzucana na rzecz takiego wyjazdu.
- Po zdjęciu punktu, który zostawił dwa postoje bez dojścia, wraca jeden uczciwy spacer, gdy dystans mieści się w limicie dnia.
- Dzień 2 zostaje w Krakowie, gdy późniejszy dzień jest już w mieście. Zamiana bierze pozycje i tytuł, data zostaje przy numerze. Poniedziałek, na który wjechał dzień z muzeum zamkniętym w poniedziałek, traci to muzeum, a ogon przysuwa się tylko do progu kolacji.

Bramka Krakowa pilnuje `slow_walk`, `long_lunch` oraz `after_close` dla Wawelu (bez Smoka) i Pieskowej Skały. Kształty z maila trzyma `test_fix383_repairs_mailed_shapes`.
