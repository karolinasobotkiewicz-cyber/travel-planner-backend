# FIX #229 — feedback klientki (01.07.2026)

Miasta: **Wrocław, Poznań, Katowice, Kraków, Warszawa**

## 1. Free Time
- Usuwanie `free_time` przed pierwszą atrakcją dnia i długich bloków (>45 min) na końcu dnia.
- Konsolidacja miejska: max **45 min** zamiast 60 min.
- Backfill ostatnich dni (≥5 dni) gdy dzień ma <3 atrakcje lub **0 atrakcji** w ostatnim dniu.
- FIX #227: retry z reuse POI także gdy ostatni dzień ma **0 atrakcji**.

## 2. Lunch
- Domyślnie **12:30–14:00**.
- Rodziny i seniorzy: **12:30–13:30**.

## 3. Etykiety czasu
- „Wieczorny relaks” tylko od **17:00** (merge wieczorny: start ≥17:00 i koniec ≥18:00).

## 4. Travel style / preferencje
- **Adventure**: silniejszy scoring (industrial, kopalnie, podziemia), kara za muzea bez `museum_heritage` w top-2.
- **Active sport**: +55 pkt za aktywne POI.
- **Relax + couples**: ogrody/bulwary zamiast aquaparku.
- **Cultural**: kara aquaparku.
- Rozłożenie preferencji na cały pobyt: wyższy spread boost (+130 + dzień×16).
- Spójność raportu pokrycia: silniejsze markery relax/nature (palmiarnia, Wyspa Słodowa itd.).

## 5. Muzea / rankingi
- Max **3 muzea/dzień** w mieście (gdy `museum_heritage` nie w top-2).
- Max **1 muzeo/dzień** dla adventure (style lub pref).
- Kary za streak kultury (adventure, friends, miasto).
- Demotions: Browar Stu Mostów, Dworzec Świebodzki, mosty, pomniki, kościoły (profile-specific).
- Long stay (5–7 d): boost Hydropolis, Ogród Japoński, Fontanna, Wyspa Słodowa.

## 6. Target group / deny
- Rodziny: bungee, secret room, mosty, ekstremalne, muzea nie dla dzieci.
- Friends+adventure: pomniki, mosty, place.
- Couples: Stacja Grawitacja, CNK.
- Restauracje filtrowane po `target_group` (lunch/dinner).

## 7. Logistyka
- Pomijanie POI wymagających **>50 min** dojazdu w środku dnia miejskiego.

## Testy
`tests/test_fix229_client_feedback.py` + regresja FIX #221–#228.
