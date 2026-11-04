# FIX #389 — końcowe warunki Krakowa

Pieczęć `_seal_fix389_krakow_client` stoi za #388 i jest ostatnim krokiem
Krakowa. Wrocław i Zakopane pozostają nietknięte.

- Dzień rodzinny kończy się z najwyżej jedną wystawą LEGO. Krótsza wystawa
  schodzi razem z prywatnymi dojazdami. Połączenie do następnego punktu jest
  liczone z rzeczywistej pozycji ludzi i auta. Gdy powrót do auta przekracza
  limit spaceru, wchodzi uczciwy transport publiczny zamiast fikcyjnego
  przejazdu autem — tylko gdy użytkownik go wybrał (FIX #391). Dotyczy to także ostatniej atrakcji przed kolacją: dojście
  do usuniętej wystawy nie może zostać samo.
- Lunch nie może trwać dłużej niż 75 minut. Regresja #388
  `14:27–16:52` wraca do standardowych 40 minut (`14:27–15:07`), a dalsza
  część dnia przesuwa się wcześniej. Kolacja pozostaje po 17:00 i co najmniej
  trzy godziny po lunchu.
- Każdy przejazd autem jest sprawdzany stanem `people_at/car_at`. Początkowy
  parking auta jest odczytywany również z pierwszego spaceru wychodzącego z
  parkingu, bez wcześniejszego przejazdu autem. Przejazd,
  który nie może ruszyć z prawdziwego parkingu, jest zastępowany uczciwym
  połączeniem ludzi do następnego punktu. Samochód nie zmienia wtedy miejsca.
- Maczuga Herkulesa i Plac Bohaterów Getta zawsze mają koszt grupy i oba
  bilety równe zero. Chroni to również punkty dodane przez sklonowanie
  technicznego szablonu innej atrakcji.

Bramka Krakowa sprawdza `double_bricks`, `long_lunch`,
`free_place_cost`, `car_teleport` i `car_position_mismatch`.
`test_fix389_enforces_final_krakow_postconditions` trzyma dokładne kształty
z maila niezależnie od wariantu wygenerowanego dnia.
