# Baza Excel — potwierdzenie importu i drobne poprawki

> Dla: klientka (Etap 3)  
> Data: **23 czerwca 2026**  
> Plik: `multi_city_attractions.xlsx` (arkusz **All Cities**)  
> Status: **zaimportowany do silnika** ✅

---

## Podsumowanie importu

| | Poprzednia baza | Twoja wersja |
|---|---:|---:|
| Wiersze w Excelu | 696 | 713 |
| Miasta | 83 | 82 |
| POI używane przez silnik | 696 | **709** (+13) |

**Backup poprzedniej wersji:** zachowany po naszej stronie (nie w repozytorium).

---

## Co zostało poprawione — dziękujemy ✅

1. **Browar Stu Mostów** (Wrocław) — dodany, widoczny w bazie.
2. **Mikro-atrakcje** (mosty, place, deptaki) — must_see obniżone u **13 z 14** wskazanych POI.
3. **`seniors friends`** — format target group naprawiony.
4. **Nowe atrakcje** — m.in. Laser Arena Gdańsk, Park Paulinum, Wodospad Podgórnej, Jezioro Modre, Wzgórze Kościuszki, Promenada, Punkt Widokowy Orlinek, Zapora na Łomnicy, Żywy Bank Genów.
5. **Sezonowość Góralki** — format poprawny (`spring,summer,autumn`).

Testy naturalności planów (Zakopane): **10/10 OK** po imporcie.

---

## Do poprawienia w następnej wersji (Priorytet 1)

### 1. Niekompletne wiersze — silnik je pomija

Te POI **nie trafiają do planów**, dopóki nie uzupełnisz danych:

| Wiersz (orientacyjnie) | Nazwa | Problem |
|------------------------|-------|---------|
| ~713 | **Browary Warszawskie** | Brak Lat, Lng, City |
| ~714 | **Hala Targowa** | Brak Lat, Lng, City |
| ~446–447 | *(puste)* | Jelenia Góra — brak nazwy POI |

**Co zrobić:** uzupełnij współrzędne, miasto, tagi i priority_level — albo usuń puste wiersze.

### 2. Pomnik Syreny Warszawskiej

- Obecnie: **must_see = 8**
- Sugestia: obniżyć do **5–6** (jak pozostałe mikro-atrakcje typu pomnik/plac)

### 3. Góralski Ślizg — sezonowość

- Obecnie: `all_year`
- Sugestia z poprzedniej instrukcji: `spring,summer,autumn` (jeśli atrakcja nie działa zimą)

---

## Priorytet 2 — jakość scoringu (nie blokuje importu)

### Tagi nierozpoznawane przez silnik (~24 typy)

Silnik je **ignoruje** przy dopasowaniu preferencji użytkownika. Najczęstsze:

| Tag | Wystąpień | Sugestia |
|-----|----------:|----------|
| `outdoor_activity` | 13 | → `nature` / `active` / `hiking` (zależnie od POI) |
| `easy_nature` | 13 | → `nature` / `easy_trail` |
| `scenic_spot` | 5 | → `viewpoint` / `nature_landscape` |
| `historic_site` | 3 | → `historical_site` (literówka) |
| `craft_beer`, `brewery`, `beer_tasting` | po 3 | OK — dodamy mapowanie po stronie silnika |
| `chocolate_tasting` | 2 | OK — dodamy mapowanie |

### Inne drobne uwagi

| Temat | Akcja |
|-------|-------|
| `priority_level = 2` | Zamienić na `high` / `medium` / `low` |
| `recommended_time_of_day = middayafternoon` | → `midday` lub `afternoon` |
| Hel / Rewa (day-trip) | Hub = `Gdańsk` lub `Gdynia` (nie `Hel` / `Rewa`) |
| Usunięte POI | `Sery Lutomierskie`, `plac Ratuszowy` — celowe? Jeśli tak, OK |

---

## Czego nie trzeba ruszać

- **`zakopane.xlsx`** — osobna baza, bez zmian.
- **Fontanna Multimedialna** — City=Wrocław OK.
- **Letni tor Góralka** — sezonowość OK.

---

## Jak przekazać kolejną poprawkę

1. Edytuj plik Excel (arkusz **All Cities**).
2. Wyślij zaktualizowany `multi_city_attractions.xlsx`.
3. My podmienimy i uruchomimy retest `json_miasta/*/test-*.json`.

---

*Wygenerowano po imporcie bazy klientki | stan silnika: FIX #211/#212*
