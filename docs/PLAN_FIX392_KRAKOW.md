# FIX #392 — usunięty punkt nie urywa dnia

Zmiany siedzą w końcowej pieczęci `_seal_fix389_krakow_client`. Wrocław i
Zakopane pozostają nietknięte.

- Usunięcie atrakcji (drugie LEGO, powtórka, punkt nieosiągalny przy „tylko
  auto”) nie wycina już całego odcinka aż do kolacji. Ludzie wracają pieszo
  do miejsca, w którym naprawdę stoi auto. Jeśli ten spacer przekracza limit
  i auto pojechało razem z usuniętym punktem, punkt zostaje.
- Zwolniony czas — także dziura zostawiona przez sam generator, bez żadnego
  usunięcia — jest zagospodarowany. Najpierw otwarty, nieużyty punkt z puli
  (albo z krótkiej listy zapasowej), z własną ceną, pieszo albo autem:
  dojście do auta, przejazd, dojście. Dopiero gdy nic nie pasuje, sąsiednia
  wizyta wydłuża się w realnych granicach (najwyżej +30 min albo ×1,5).
- Parki i bulwary nie są dokładane po 16:30 w zimie.
- Dzień po naprawie nie może być gorszy od dnia wejściowego: bez luki
  ≥45 min, teleportu auta, brakującego dojazdu, transportu poza wybranymi
  środkami, drugiej wystawy LEGO i szóstej atrakcji w dniu z dziećmi. Gdy
  naprawa dodałaby taki błąd, zostaje dzień wygenerowany.

`test_fix392_removed_stop_never_cuts_the_day` trzyma kształty z maila: J1 D1
po Muzeum Etnograficznym o 14:35 i J1 D2 po Parku Lotników o 16:14, a także
samą wygenerowaną dziurę bez usunięcia punktu.
