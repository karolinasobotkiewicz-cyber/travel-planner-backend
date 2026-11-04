# FIX #391 — tylko wybrane środki transportu, bez powtórek, pełne wyjazdy do doliny

Zmiany siedzą w końcowej pieczęci `_seal_fix389_krakow_client`, więc obowiązują
niezależnie od wariantu wygenerowanego dnia. Wrocław i Zakopane pozostają
nietknięte.

- Transport publiczny pojawia się tylko wtedy, gdy użytkownik go wybrał w
  `transport_modes`. #389/#390 używały go jako awaryjnego połączenia, gdy
  ludzie byli za daleko od zaparkowanego auta. Przy wyborze „tylko samochód”
  połączenie idzie pieszo do prawdziwego parkingu i dalej autem. Jeśli to
  niemożliwe w limicie spaceru, nieosiągalny punkt wypada razem ze swoimi
  dojazdami, a dzień domyka się bez dziury: dłuższa wizyta (maksymalnie +30 min
  lub ×1,5) albo pobliski, otwarty i nieużyty punkt z puli z własną ceną.
- Ta sama atrakcja nie występuje w dwóch dniach. Reguła dopasowania nazw jest
  ta sama co w bramce `repeat_place`. Powtórka schodzi z późniejszego dnia;
  jeśli była pierwszym punktem dnia, dzień zaczyna się dojazdem do następnego
  punktu o tej samej godzinie.
- Wyjazd do Doliny Prądnika nie kończy się na jednym punkcie, gdy jazda trwa
  co najmniej 40 minut i dłużej niż zwiedzanie. Dochodzi Maczuga Herkulesa
  (bezpłatna, 45–60 min), a gdy była już w planie, zamek w Pieskowej Skale lub
  w Ojcowie w godzinach otwarcia. Spod Pieskowej Skały to krótki spacer z
  parkingu pod zamkiem. Z Ojcowa auto jedzie z Parkingu Złota Góra na parking
  pod zamkiem w Pieskowej Skale, a powrót do miasta rusza stamtąd. Reszta dnia
  przesuwa się tylko o tyle, ile nie mieści się w wolnym czasie przed kolejnym
  punktem, więc kolacja nie przesuwa się bez potrzeby.
- Dzień z dziećmi nadal ma najwyżej pięć atrakcji.

Bramka Krakowa doszła o `offmode_transport` (autobus/tramwaj w planie
„tylko samochód”). `test_fix391_*` trzymają kształty z maila: J8 D4
Katedra → Plac Bohaterów Getta, J8 D3 Skałki Twardowskiego, J1 D3 Pieskowa
Skała i J8 D6 Ojców — bez transportu publicznego, teleportu auta, brakującego
dojazdu i niezgodnego punktu startu.
