# FIX #241 — Kraków client feedback (24.07.2026)

## Zgłoszenia i poprawki

| Obszar | Poprawka |
|--------|----------|
| **Kładka Bernatka** | deny family_kids / friends+adventure; demote −150 (−80 engine) |
| **Fabryka Wódki rano** | `is_afternoon_only_poi` + strip przed 14:00 |
| **Kino 7D & VR** | deny dla adventure; boost escape room / aktywności |
| **Rynek / Stare Miasto repeat** | kara −95..−115 gdy core old town już w tripie |
| **family_kids 5 lat** | boost papugarnia/kolejkowo/pixel; deny bernatka |
| **seniors Rynek** | demote powtórne rynek/stare miasto/bazylika |
| **solo relax nature (json9)** | demote podziemia/schindler/wieliczka bez history pref |
| **OPN + centrum mix (json8)** | `_strip_mixed_opn_krakow_attractions` |
| **Lustrzany Labirynt** | deny cultural / couples water+relax / adventure |
| **json10 couples water** | deny kościół Wojciecha, Nowa Huta, bazylika, zoo |
| **Nowa Huta** | demote gdy brak history prefs (zbyt ogólna dzielnica) |
| **Park Decjusza / Kopiec Wandy** | deny/demote friends+history+adventure |

## Testy

- `tests/test_fix241_krakow_client.py` — 10 JSON-ów Kraków
- `scripts/_audit_krakow_fix241.py` — szybki raport lokalny
