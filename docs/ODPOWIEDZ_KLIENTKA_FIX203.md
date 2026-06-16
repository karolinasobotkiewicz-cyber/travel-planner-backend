# Odpowiedź dla klientki — FIX #203 (16.06.2026)

Dzień dobry,

dziękuję za szczegółowy feedback dla 14 miast. Przeszłam przez wszystkie punkty i
wdrożyłam poprawki. Poniżej co się zmieniło:

## Najważniejsze naprawy (dotyczą prawie wszystkich miast)

1. **Klaster działa teraz dla wszystkich regionów.** Przyczyna była po stronie
   wykrywania: gdy w teście podany jest `region_type: "cluster"`, planer rozpoznaje
   region (Trójmiasto, Karkonosze, Kotlina Kłodzka) i realnie planuje **na wielu
   miastach**, zamiast zostawać w jednym. Dotyczy: Gdańsk/Gdynia/Sopot,
   Karpacz/Jelenia Góra/Szklarska, Kłodzko/Kudowa/Polanica.

2. **Pokrycie preferencji (preference_coverage) przebudowane.** Wyeliminowane
   błędne przypisania:
   - Pomnik Smoka, Kładka Bernatka, mosty, place, rynki, wieżowce, fontanny,
     Stare Miasto **nie są już** zaliczane do `nature_landscape`.
   - Rynek/Stare Miasto **nie są** liczone jako `history_mystery`.
   - Zoo/Rynek/muzea **nie trafiają** do `active_sport`.
   - Podziemia Rynku **nie są** `kids_attractions`.

   Naprawione pominięcia (teraz **są** liczone):
   - Łazienki, parki zdrojowe, uzdrowiska → `relaxation`.
   - Muzeum Polskiej Wódki → `local_food_experience`.
   - Multimedialny Park Fontann → `water_attractions`.
   - Muzeum Pana Tadeusza, Centrum Historii Zajezdnia, muzea statków (ORP
     Błyskawica, Dar Pomorza), Muzeum Emigracji → `museum_heritage`.
   - Ostrów Tumski, Katedra, Twierdza Kłodzko → `history_mystery`.
   - Szczeliniec, Wodospad Wilczki → `nature_landscape`.

3. **Spójność opisów (why_selected) z pokryciem.** Komunikaty „Relaxing activity /
   matches your style" pojawiają się tylko, gdy atrakcja realnie pokrywa daną
   preferencję — koniec sprzeczności „opis mówi relaks, a coverage = false".

4. **Transity.** Usunięta przyczyna „przejazd z/do POI, którego nie ma w planie" —
   po finalnej podmianie atrakcji endpointy transitów są odświeżane. W testach:
   **zero** błędnych transitów.

5. **Day End.** „Harmonogram wykracza poza limit dnia" / „free_time po day_end" —
   dodany finalny clamp do okna dnia i przycięcie kolacji. W testach: **zero**
   przekroczeń.

## Co jeszcze wymaga uzupełnienia danych (nie silnika)

- **Bardzo długie plany (6–7 dni) w regionach z małą liczbą atrakcji** (Kotlina
  Kłodzka, częściowo Karkonosze, Poznań) potrafią mieć rzadsze/puste dni i więcej
  czasu wolnego — po prostu kończą się atrakcje w bazie. To wymaga **dodania POI do
  arkusza**, nie zmian w logice.
- **Poznań** nie ma jeszcze zdefiniowanego klastra (jak Trójmiasto) — jeśli ma
  eksplorować okolicę, trzeba taki region dodać.
- Dwa pliki testowe (`Gdynia/test-06`, `Katowice/test-07`) mają błąd składni JSON i
  się nie wczytują.

Zakopane pozostaje nienaruszone (10/10 testów regresji). Czekam na ponowny retest.

Pozdrawiam
