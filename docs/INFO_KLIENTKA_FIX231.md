# FIX #231 — feedback klientki (round 4)

Miasta: **Wrocław, Warszawa, Kraków, Katowice, Poznań**

## Globalne
- Free time miejski: cap **20 min** / blok, max **45 min** / dzień
- Lunch: truncate atrakcji przed oknem lunchu + `_fix_late_lunch` (max 14:00)
- Restauracje: filtr **1 km** od aktualnej pozycji
- Logistyka: skip hop >35 min / >10 km; dalekie (>8 km) krótkie wizyty (<75 min)
- Spread preferencji: silniejszy boost relax/nature/**active_sport** przez cały pobyt
- Pixel XL min 45 min, Palmiarnia min 60 min

## profile_poi_rules.py (nowe deny/demote)
- Wrocław: Most Grunwaldzki, Dworzec, Bastion, City Golf, boosts Park Szczytnicki/Hydropolis/Kolejkowo
- Warszawa: Plac Europejski, micro POI, friends+adventure parks/muzea, museum flagship boost
- Kraków: family_kids deny kościoły/Decjusz; cultural deny Lustrzany Labirynt
- Katowice: kościoły, Planetarium friends+adv, Rynek day-1, seniors relax parks
- Poznań: pomniki filler, adventure demote, relax Malta/Wartostrada/Sołacki

## Testy
- `tests/test_fix231_client_feedback.py` (unit)
- `tests/test_fix231_client_json_audit.py` (json_miasta test-01..10 × 5 miast)
- regresja FIX #221–#230
