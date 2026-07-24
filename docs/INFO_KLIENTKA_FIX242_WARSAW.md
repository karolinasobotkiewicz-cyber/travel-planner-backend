# FIX #242 — Warszawa (feedback klientki test 1–10)

| Problem (json) | Rozwiązanie |
|----------------|-------------|
| **Pomnik Syreny** (1,2,4,5,8) | Hard deny w `should_deny_poi_for_profile` |
| **Multimedialny Park Fontann rano** (1,10) | `is_evening_only_poi` + strip wieczorny w pipeline |
| **Kolacja regionalna → FORNO włoska** (2) | Filtr `local_food_experience` przy dinner + `_filter_meal_suggestions` |
| **Adventure: PKiN/bulwary zamiast aktywności** (3) | Deny + boost kajaki/park linowy dla friends+adventure+active_sport |
| **Adventure: muzea cultural** (3,7) | Deny Norblin/MSN/Centrum Pieniądza/Ogrody Zamku; boost historia/podziemia |
| **Pałac Prezydencki / micro fillery** (4,8,9) | Demote −120 (`_waw_filler`) + deny solo nature+relax |
| **Słaby dzień 4** (4) | Audyt sparse/micro-heavy dla długich tripów |
| **Nature+relax: Browary/Most** (9) | Hard deny browary/pałac prez/most dla solo+nat+relax |
