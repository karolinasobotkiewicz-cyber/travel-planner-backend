# FIX #230 — feedback klientki (round 3)

Miasta: **Wrocław, Warszawa, Kraków, Katowice, Poznań**

## Free Time
- Cap miejski: **30 min** (merge + trim pojedynczych bloków)
- `_trim_long_free_time_blocks` na końcu pipeline dnia
- Agresywniejszy backfill ostatnich dni (≥4 dni, ostatnie 2 dni, <3 atrakcje)

## Lunch
- Wymuszony od **12:30** (nie czekamy do 13:00+)
- Post-POI lunch trigger od lunch_earliest
- Seniorzy: lunch target **12:30** (spójnie)

## Adventure / relax / nature przez cały pobyt
- Silniejszy spread preferencji (`compute_prefs_needed_today`, boost +155)
- `profile_poi_rules.py` — profile-specific deny/demote
- Relax-led: max **1 muzeum/dzień** w mieście
- Adventure warning: GoJump, Aquapark, Hydropolis liczą się jako aktywne

## POI rules (profile_poi_rules + family_fit)
- Zoo off: friends+adventure+underground/history, friends+adventure+active_sport
- Kościole/bazyliki demote dla family, relax, adventure bez historii
- Wrocław: Hala Targowa, Most Grunwaldzki, Dworzec Świebodzki, Hala Stulecia (friends+adventure)
- Warszawa: micro POI, Bulwary/Łazienki/Ogrody (friends+adventure)
- Kraków: Podziemia Rynku (family 5 lat), Ojców cluster boost po Maczudze
- Katowice: Park Kościuszki repeat penalty, kościoły
- Poznań: Okrąglak, Domy Kupieckie (profile-specific)

## Logistyka
- Mid-day hop: **>40 min** lub **>12 km** → skip (Muzeum Wódki → Ogrody)

## Coverage
- Nature/relax: adequate dopiero przy **≥2** mocnych POI (lub 2+ trafień)

## Testy
`tests/test_fix230_client_feedback.py` + regresja FIX #221–#229
