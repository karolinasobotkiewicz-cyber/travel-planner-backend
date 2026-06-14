# Raport wewnętrzny — FIX #202 dane Excel + tagi (14.06.2026)

**Dla:** Matte  
**Deploy:** commit po `git push` na `main`  
**Klientka:** nie informowana (na żądanie — osobna wiadomość później)

---

## Wykonane automatycznie

### 1. Excel `multi_city_attractions.xlsx` (684 POI)

| POI | Zmiana |
|-----|--------|
| **Fontanna Multimedialna** | `City: Warsaw → Wrocław` (Hub już był Wrocław) |
| **Spodek w Katowicach** | `Must see: 10→6`, `priority: core→secondary` (tagi bez museum — bez fałszywych tagów) |
| **Długi Targ** | `Must see: 10→5`, `priority: core→secondary` |
| **Pomnik Bamberki** | `Must see: 7→4`, `priority: core→optional` |
| **Fokarium (Hel)** | `Hub: Gdańsk→Hel` |
| **Rewa - Cypl Rewski** | `Hub: Gdynia→Rewa` |
| **31 wierszy Kotlina** | `recommended_time_of_day`: `midday.afternoon` → `midday,afternoon` |
| **7 wierszy (Zakopane+)** | Tags: newline → przecinki (Obwarzanka, Krupówki, Antałówka…) |

Backup przed zmianą: `data/multi_city_attractions_backup_20260614_135234.xlsx`

### 2. Silnik — tag vocabulary (FIX #202)

- `get_all_registered_tags()` w `tag_preferences.py` — dynamiczny rejestr tagów
- `excel_validator.py` — walidacja zsynchronizowana z `tag_preferences` + `TAG_ALIASES`
- `tag_mapper.py` — ~60 nowych aliasów (warianty z myślnikiem, Trójmiasto, parki wodne…)
- Parsowanie tagów: obsługa newline w kolumnie Tags

**Walidator przed:** 27+ tag warnings, 31 tod warnings  
**Walidator po:** **0 tag warnings**, **0 tod warnings**

### 3. Regresja

- `test_naturalness_klientka.py` — **10/10**
- `test_multi_city_density.py` — **10/10**

---

## Efekt na planowanie

| Obszar | Efekt |
|--------|-------|
| Cluster Trójmiasto | Osobne huby **Hel** i **Rewa** → `build_cluster_hub_day_pools()` może przypisać im dni |
| Wrocław | Fontanna nie trafia do filtra Warszawy |
| Scoring | Bamberki/Długi Targ/Spodek — niższy must_see w danych + `is_quick_stop_poi` w silniku |
| Preferencje | Więcej POI dostaje scoring (tag mapper + zero unknown w walidatorze) |

---

## Skrypt powtarzalny

```powershell
cd travel-planner-backend
python _fix_data_fix202.py
```

Idempotentny dla większości pól (patches po nazwie POI).

---

## Do powiedzenia klientce (później)

- Poprawiliśmy dane w arkuszu (City, must_see, huby Hel/Rewa, formaty tagów/czasów)
- Prosimy o retest Trójmiasto 5–7 dni (dzień Hel / Rewa) i Wrocław (Fontanna)
- Nie trzeba od niej nowego Excela — zmiany już w `multi_city_attractions.xlsx` na serwerze po deploy

---

## Pliki zmienione

```
data/multi_city_attractions.xlsx
app/domain/scoring/tag_preferences.py
app/domain/scoring/tag_mapper.py
app/infrastructure/repositories/excel_validator.py
_fix_data_fix202.py
```
