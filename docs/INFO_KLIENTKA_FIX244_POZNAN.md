# FIX #244 — Poznań (feedback klientki test 1–10)

| Problem (json) | Rozwiązanie |
|----------------|-------------|
| **Nowe + Stare Zoo jednego dnia** (1) | Cap 1 zoo/dzień w engine + strip w pipeline |
| **Kolacja regionalna → gruzińska/włoska** (2,8) | Filtr georgian/italian w dinner + `_filter_meal_suggestions` |
| **Dzień muzealny** (2,4) | Max 1 muzeum/dzień couples cultural+relax; strip 3+ muzeów |
| **Okrąglak/Ratusz/Domy Kupieckie** (3) | Hard deny friends adventure |
| **Słabe/sparse dni** (4,8) | Gap-fill + boost nature day 7 |
| **Pixel XL 35 min** (5) | Min 60 min family_kids / 45 min ogólnie |
| **Pixel XL zły profil** (7) | Deny friends underground+history |

Naprawiono też fixtures test-01..04,09 (city: Poznań zamiast Kraków).
