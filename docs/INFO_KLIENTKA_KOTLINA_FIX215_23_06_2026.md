# FIX #215 — Kotlina Kłodzka + wyjaśnienie kolumny Hub

> Data: **23 czerwca 2026**

## Pytanie klientki: kolumna Hub vs City

**To jest celowe — nie pomyłka.**

| Kolumna | Znaczenie |
|---------|-----------|
| **City** | Faktyczna lokalizacja atrakcji (adres, GPS) — np. `Lądek-Zdrój`, `Radków`, `Szczytna` |
| **Hub** | Miasto-baza wypadowa w Kotlinie — do którego „dnia” / puli planera przypisana jest atrakcja |

Przykład: *Rynek w Lądku-Zdroju* ma `City=Lądek-Zdrój`, `Hub=Kłodzko` — atrakcja leży w Lądku, ale planer może ją zaplanować w dniu bazującym na Kłodzku (Zone B/C, dojazd samochodem).

**W API planu pole `city` przy atrakcji = kolumna City** (prawdziwe miasto). Jeśli w UI widać „Kłodzko” przy Lądku — daj znać, sprawdzimy warstwę frontu; silnik zwraca `city` z Excela.

Strefy w Excelu:
- **Zone A** — atrakcje w samym mieście uzdrowiskowym
- **Zone B/C** — wyjazdy dnia z hubu (Szczeliniec, Błędne Skały, Wambierzyce, Lądek itd.)

---

## Naprawione w silniku (FIX #215)

| Problem | Naprawa |
|---------|---------|
| Brak Szczelińca, Błędnych Skał, Skalnych Grzybów | Kotlina **zawsze** ładuje pełną pulę 3 hubów + Zone B/C (wcześniej Kłodzko miał ≥35 POI przez hub i soft-cluster się nie rozszerzał) |
| Nature = Park Szachowy, Ekocentrum | Boost ikon Gór Stołowych; kara/deny słabych POI |
| Museum słabe | Boost Twierdzy, Kaplicy, Jaskini, Muzeum Zabawek |
| Family — brak hitów | Boost Ogród Bajek, Muzeum Zabawek; deny Kaplica/Rynek Lądek |
| Active sport = Manufaktura Szkła | Coverage deny + kara scoring |
| Adventure → muzea | Kara muzeów przy active_sport/adventure w Kotlinie |
| Puste dni / koniec o 11 | Spa cluster scoring działa też w soft-cluster; density mode |

## W Excelu (klientka)

- **Śnieżnik, Czarna Góra, Wambierzyce, Muzeum Papiernictwa** — brak w bazie (do dopisania)
- **Zalew Radkowski** — sezonowość letnia (silnik filtruje po `Seasonality`)
- **Manufaktura Szkła** — tagi: `craft_workshop`, nie `active_sport`
- **Kaplica Czaszek** — `history_mystery` / `museum_heritage`, nie `kids_attractions`

## Testy

- `test_fix215.py`: **2/2**
- Regresja: `test_fix214`, `test_fix213`, `test_naturalness`
