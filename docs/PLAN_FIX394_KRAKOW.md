# FIX #394 — przejazd między parkingami i godziny otwarcia

Oba warunki stoją na końcu pieczęci Krakowa. Wrocław i Zakopane pozostają
nietknięte.

- Auto jedzie z parkingu, na którym stoi, na parking następnego punktu.
  Parking może być w polu „skąd” (także pod skróconą nazwą, jak „Parking pod
  Kopcem Kościuszki”) albo tylko przy atrakcji. Dochodzi dojście do auta,
  gdy ludzie są gdzie indziej. Jeśli to dojście przekracza limit spaceru,
  punkt wypada zamiast zostawiać skok.
- Wizyta mieści się w całości w godzinach z Excela na ten dzień, z tym samym
  marginesem zamknięcia co reszta silnika. Nie skracamy jej do kilku minut.
  Gdy pełna wizyta nie wchodzi przed zamknięciem, schodzi razem z dojazdem,
  a wolny czas dostaje inny otwarty punkt. Zdjęcie zostaje tylko wtedy, gdy
  dzień nie dostaje urwany przejazd, brak dojazdu, ani czekanie na posiłek.
  Wioski Świata w poniedziałek 17:58–19:14 przy zamknięciu o 16:00 nie zostają.
