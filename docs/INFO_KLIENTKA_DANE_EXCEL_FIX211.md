# Instrukcja — co poprawić w Excelu (`multi_city_attractions.xlsx`)

> Dla: klientka (Etap 3)  
> Data: **20 czerwca 2026**  
> Arkusz: **`All Cities`** (696 POI, 83 miast)  
> **Nie edytuj** `zakopane.xlsx` — to osobna, zamknięta linia bazowa.

---

## Priorytet 1 — wpływ na jakość planów (must-fix)

### 1. Brakujące POI

| POI | Miasto | Problem | Co zrobić |
|-----|--------|---------|-----------|
| **Browar Stu Mostów** | Wrocław | Zgłoszone jako brak w planach `local_food` | **Dodać nowy wiersz** z tagami: `brewery`, `craft_beer`, `beer_tasting`, `local_food_experience`, `regional_cuisine` |

### 2. Mikro-atrakcje z zawyżonym `Must see score` (≥8)

Silnik traktuje must_see ≥8 jako „ikony". Place, mosty, deptaki z must_see 9–10 dominują plan zamiast muzeów/parków.

**Obniżyć must_see do 4–6** (lub `priority_level` → optional) dla:

| must_see | Nazwa | Miasto |
|--------:|-------|--------|
| 9 | Brama Poznania | Poznań |
| 8 | Brama Wyżynna | Gdańsk |
| 10 | Fontanna Neptuna | Gdańsk |
| 8 | Plac Zdrojowy | Sopot |
| 9 | Deptak Monte Cassino | Sopot |
| 9 | Brama Floriańska | Kraków |
| 10 | Pomnik Smoka Wawelskiego | Kraków |
| 8 | Plac Bohaterów Getta | Kraków |
| 9 | Most św. Jana | Kłodzko |
| 9 | Deptak w Polanicy-Zdroju | Polanica-Zdrój |
| 8 | Fontanna Multimedialna | Wrocław |
| 9 | Most Tumski | Wrocław |
| 8 | Most Grunwaldzki | Wrocław |
| 8 | Pomnik Syreny Warszawskiej | Warszawa |

> **Zasada:** most / plac / pomnik / brama → must_see **4–6**, chyba że to naprawdę flagowa atrakcja regionu.

### 3. Tagi nierozpoznawane przez silnik (20 typów)

Te tagi są **ignorowane** w scoringu i coverage. Popraw w kolumnie `Tags` (literówka / zamiana na istniejący słownik) **lub** potwierdź, że mamy je dodać po stronie silnika:

| Tag (w Excelu) | Wystąpień | Sugerowana zamiana / akcja |
|----------------|----------:|----------------------------|
| `local_brands` | 3 | → `local_products` lub `regional_specialties` |
| `warsaw` / `wroclaw` / `katowice` | 2+2+2 | Usunąć (to nie tag preferencji) |
| `craft_beer`, `brewery`, `beer_tasting` | 2+2+2 | Zostawić — silnik doda mapowanie do `local_food` |
| `military` | 2 | → `military_heritage` lub `war_history` |
| `workshops` | 2 | → `craft_workshop` / `interactive_workshop` |
| `chocolate` | 2 | → `chocolate_tasting` / `sweet_tasting` |
| `bunkers` | 1 | → `ww2_history` / `fortifications` |
| `hel` | 1 | Usunąć (miasto, nie tag) |
| `sowie_mountains` | 1 | → `karkonosze_views` / `mountain_views` |
| `historic_site` | 1 | → `historical_site` (literówka) |
| `factory_tour` | 1 | → `industrial_heritage` |
| `farm` | 1 | → `farm_animals` / `agrotourism` |

### 4. Sezonowość — Góralski Ślizg

| POI | Obecna wartość | Poprawka |
|-----|----------------|----------|
| Góralski Ślizg | `spring,` + `summer` (dwa wiersze / złamany format) | Jedna komórka: `spring,summer,autumn` |
| Letni tor Góralka | `spring,summer,autumn` | OK — bez zmian |

---

## Priorytet 2 — długie pobyty 5–7 dni (uzupełnienie puli)

Przy **<50 POI w regionie** silnik fizycznie nie wypełni 7 dni bez `free_time` i powtórek. To **limit danych**, nie bug.

### Regiony krytyczne (hub miasta)

| Miasto / region | POI w bazie | Rekomendacja |
|-----------------|------------:|--------------|
| **Sopot** | 28 | +10–15 (nature, relax, evening) |
| **Gdynia** | 32 | +10 (ORP Błyskawica już jest — więcej museum/adventure) |
| **Kudowa-Zdrój** | 19 | +8–10 (spa, local food, easy nature) |
| **Kłodzko** | 12 | +5–8 |
| **Polanica-Zdrój** | 11 | +5–8 |
| **Karpacz** | 23 | +10 (łatwa natura dla rodzin, nie tylko szlaki) |
| **Szklarska Poręba** | 17 | +8 |
| **Jelenia Góra** | 19 | +8 |
| **Katowice** | 21 | +5 (underground, industrial) |

### Wieczór w Gdańsku

- Obecnie: **11 / 77** POI ma `recommended_time_of_day` = evening  
- Dla planów kończących się o 18:00–20:00 dodaj tag `evening` u: bulwarów, fontann, spacerów, kawiarni z widokiem, ECS wieczorem itd.

---

## Priorytet 3 — doprecyzowanie tagów (jakość coverage API)

### museum_heritage vs history_mystery

| Przykład | Obecne tagi | Sugestia |
|----------|-------------|----------|
| Muzeum Tatrzańskie (Zakopane) | `regional_heritage`, `mountain_culture` | Dodać `folklore` lub `history_mystery` jeśli ma liczyć się jako historia, nie tylko muzeum |
| Brama Chlebnicka (Gdańsk) | `old_fortifications` | OK dla `history_mystery` — zostawić, jeśli to zamierzone |
| Cmentarz na Pęksowym Brzyzku | `historical_exhibits`, `local_legends` | OK — bez zmian |

### Target group — błąd formatu

- Wiersz z wartością **`seniors friends`** (dwa profile w jednej komórce) → rozdzielić na `seniors, friends` lub wybrać jeden profil dominujący.

### Hel / Rewa (wycieczki z Trójmiasta)

- Upewnij się, że kolumna **`Hub`** = `Gdańsk` lub `Gdynia` (day-trip), nie puste.
- `City` = Hel / Rewa jest OK dla wycieczek jednodniowych.

---

## Priorytet 4 — nice to have

| Temat | Akcja |
|-------|-------|
| `recommended_time_of_day` po polsku (`rano`) | Zamienić na `morning` / `afternoon` / `evening` / `any` |
| Duplikaty / stare wiersze `Warsaw` vs `Warszawa` | Ujednolicić nazwę miasta |
| POI jednodniowe (1 POI w mieście) | OK jako day-trip; nie budować na nich 5-dniowego planu |

---

## Czego NIE trzeba poprawiać (już OK w arkuszu)

- **Fontanna Multimedialna** — `City=Wrocław` (poprawione)
- **Sezonowość Góralki** — `spring,summer,autumn` (OK)
- Walidator Excel: **0 błędów**, 18 ostrzeżeń (głównie tagi + must_see info)

---

## Jak przekazać zmiany

1. Edytuj **`Planer - miasta atrakcje.xlsx`** (arkusz All Cities)
2. Wyślij zaktualizowany plik — my podmienimy `data/multi_city_attractions.xlsx`
3. Po Twoich poprawkach uruchomimy retest `json_miasta/*/test-*.json` i prześlemy raport

---

*Wygenerowano automatycznie: `_audit_excel_client211.py` | stan silnika: FIX #211*
