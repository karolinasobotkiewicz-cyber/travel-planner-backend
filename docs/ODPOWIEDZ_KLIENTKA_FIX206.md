# Odpowiedź dla klientki — FIX #206 (18.06.2026)

Dzień dobry,

kolejna paczka poprawek pod Wasze ostatnie testy (Kraków, Warszawa, Katowice):

## Co naprawione

**1. Mikro-POI (Pomnik Smoka, Most, Plac Matejki, Brama Floriańska itd.)**
Te miejsca nie mogą już być „core” ani głównymi punktami dnia — nawet przy wysokim
must_see w Excelu. Zostały obniżone w rankingu; mogą pojawić się jako krótki dodatek.

**2. Friends + Adventure / Active Sport**
Wzmocniony ranking atrakcji grupowych i miejskich aktywnych: Pixel XL, park linowy,
trampoliny, GOjump, VR, labirynt. Profil „friends” ma teraz wyraźniejszy wpływ.

**3. Free Time**
Znaleźliśmy główną przyczynę wielkich bloków (90–180+ min): po kolacji system dokładał
kilka kolejnych bloków wolnego czasu. Teraz jest **jeden krótki blok** (max 45 min).
Na testowym planie Krakowa friends+adventure dzień 2 spadł z **188 min → 60 min**
wolnego czasu.

**4. Relaxation (solo/seniors)**
Parki, bulwary i miejsca typu Zakrzówek dostają wyższy ranking przy stylu relax /
preferencji relaxation — żeby plan nie wypełniał się samym „czasem wolnym”.

**5. Water Attractions — Bulwary Wiślane**
Bulwary są teraz poprawnie zaliczane do pokrycia water (wcześniej tylko Łazienki).

**6. sparse_day**
Ostrzeżenie nie powinno już pojawiać się na dniach z 4+ atrakcjami przy umiarkowanym
wolnym czasie.

## Uwaga o danych

W bazie **nie ma escape roomów** w Krakowie/Warszawie — jeśli je dodacie do Excela,
scoring adventure/friends jest już przygotowany na takie tagi.

## Do kolejnej rundy

- Cluster Warszawa (Kampinos/Suntago vs. samo miasto przy Relax)
- family_kids + nature (natury znika przy kids)
- Dalsze zmniejszenie free_time na ostatnich dniach długich planów

Zakopane bez zmian (10/10). Proszę o retest :)

Pozdrawiam
