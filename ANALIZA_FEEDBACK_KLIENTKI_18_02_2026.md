# 📋 ANALIZA FEEDBACK KLIENTKI - 18.02.2026

## 1. PLIKI JSON OD KLIENTKI

### Test 02 - Response (test02-response.json)
**Parametry testu:**
- Group: couples, size 2
- Preferences: museum_heritage, relaxation, local_food_experience
- Travel style: cultural
- Budget: level 2
- Duration: 3 days

**Obecne why_selected w pliku:**
- Muzeum Tatrzańskie (poi_24):
  * "Must-see attraction in Zakopane"
  * "Cultural museum experience for couples"
  * "Cultural enrichment and local history"
  
- Podwodny Świat (poi_6):
  * [] (PUSTE!)
  
- Galeria sztuki Oksza (poi_27):
  * "Cultural museum experience for couples"
  * "Cultural enrichment and local history"

**Problem:** Wiele why_selected jest pustych lub używa generycznych szablonów.

---

### Test 05 - Response (test05-response.json)
**Parametry testu:**
- Group: family_kids, size 4, children_age 6
- Preferences: kids_attractions, relaxation, local_food
- Travel style: relax
- Budget: level 2
- Duration: 2 days

**Obecne why_selected w pliku:**
- Wielka Krokiew (poi_20):
  * "Must-see attraction in Zakopane"
  * "Breathtaking mountain views"
  
- Kaplica Jaszczurówka (poi_30):
  * "Relaxing museum experience for families"
  * "Cultural enrichment and local history"
  
- Podwodny Świat (poi_6):
  * [] (PUSTE!)

**Problem:** Wiele pustych why_selected, brak informacji o dopasowaniu do preferencji.

---

## 2. FEEDBACK KLIENTKI - PROBLEM #7 REFINEMENT

### 🎯 Co klientka mówi:

> *"Chciałabym, żeby why_selected było generowane wprost z tych samych sygnałów co scoring (match do preferencji, travel_style, crowd_tolerance, budżet), a nie z „szablonu" na typ grupy."*

### Przykłady OCZEKIWANYCH reasons:
1. **"Matches your museum_heritage preference"** 
   - Bezpośredni match do konkretnej preferencji
   
2. **"Low-crowd option (fits your crowd_tolerance=1)"**
   - Pokazuje dopasowanie do crowd_tolerance
   
3. **"Good budget fit"**
   - Pokazuje dopasowanie do budżetu
   
4. **"Short transit time from previous stop"**
   - Pokazuje logistykę i planowanie

### Korzyści tego podejścia:
- ✅ Spójność z logiką scoringu
- ✅ Pomaga w edge-case'ach
- ✅ Transparentność wyboru
- ✅ Użytkownik rozumie DLACZEGO konkretnie to POI

---

## 3. ANALIZA OBECNEJ IMPLEMENTACJI

### Obecny kod (explainability.py - commit 8718c32):

**Problem:**
- Nadal używa SZABLONÓW:
  * "Matches your {pref_text} interests - perfect for couples"
  * "Cultural museum experience for couples"
  * "Well-suited for couples"
  
- NIE pokazuje KONKRETNYCH sygnałów scoringowych:
  * ❌ Brak informacji o crowd_tolerance
  * ❌ Brak informacji o short transit
  * ❌ Brak konkretnego match score
  * ❌ Tylko ogólne "matches your preference"

### Co trzeba zmienić:

**PRZED (obecny):**
```
"Matches your museum and heritage interests - perfect for couples"
"Cultural museum experience for couples"
```

**PO (nowy):**
```
"Matches your museum_heritage preference"
"Low-crowd (fits crowd_tolerance=1)"
"Good budget fit (ticket: 24 PLN)"
"Short transit (10 min from previous stop)"
```

---

## 4. FEEDBACK KLIENTKI - PROBLEM #12 (Małopolska POI)

### 🎯 Co klientka wyjaśniła:

> *"Zgadzam się z Twoją rekomendacją: najpierw bugfixy, potem rozbudowa bazy jako osobny feature."*

### Wymagania Problem #12:

**Zakres geograficzny:**
- ✅ Cała Małopolska (Kraków, Wieliczka, Ojców, Pieniny)
- NIE tylko Zakopane

**Kategorie POI (MVP):**
- ✅ Jaskinie (główny focus)
- ✅ Underground/history_mystery:
  * Wieliczka (Kopalnia Soli)
  * Bochnia (Kopalnia Soli)
  * Ojców (jaskinie)

**Źródło danych:**
- ✅ Nowy Excel dla Małopolski
- Format: taki sam jak zakopane_poi_extended_v1.xlsx

**Ilość POI (MVP):**
- ✅ 30 POI z Krakowa na start
- Potem rozszerzenie o inne miasta Małopolski

**Priorytet:**
- 🟢 Najpierw bugfixy (Problems #1-11)
- 🟢 Potem Problem #12 jako feature

---

## 5. PYTANIE KLIENTKI - SKALOWANIE

### 🤔 Pytanie:
> *"Rozumiem, że jak skończymy to nie będzie problemu żeby wpiąć bazę całej Polski?"*

### ✅ ODPOWIEDŹ:

**TAK, system jest zaprojektowany do skalowania!**

**Architektura wspiera:**

1. **POI Repository (POIRepository):**
   - Abstrakcja - łatwo dodać nowe źródła danych
   - Format Excel już zdefiniowany
   - Wystarczy dodać nowe pliki Excel dla innych regionów

2. **Location-based filtering:**
   - Engine już filtruje POI po `city` i `region_type`
   - Wystarczy dodać nowe miasta do trip_input

3. **Scoring jest region-agnostic:**
   - Wszystkie scoringi (preferences, budget, crowd, etc.) działają uniwersalnie
   - Nie ma hardcoded logic dla Zakopanego

4. **Skalowalność:**
   - 30 POI (Kraków MVP) → 100 POI (Małopolska) → 500+ POI (cała Polska)
   - Performance OK (scoring cached, travel time optimized)

**Plan rozbudowy:**
```
Phase 1 (MVP):
- Kraków: 30 POI (jaskinie + underground)

Phase 2:
- Małopolska: 100 POI (Wieliczka, Ojców, Pieniny)

Phase 3:
- Polska: 500+ POI (Warszawa, Gdańsk, Wrocław, etc.)
```

**Wymagane zmiany do skalowania:**
- ✅ NIE TRZEBA zmieniać engine.py
- ✅ NIE TRZEBA zmieniać scoring logic
- ✅ TYLKO dodać nowe Excel files i załadować do DB
- ⚠️ Opcjonalnie: cache POI w Redis dla performance (500+ POI)

---

## 6. PLAN DZIAŁANIA

### Priorytet 1: Problem #7 Refinement (URGENT)
**Zadanie:** Przepisać explainability.py z szablonów na konkretne sygnały scoringowe

**Implementacja:**
1. Usunąć szablonowe teksty w stylu "perfect for couples"
2. Dodać funkcje generujące reasons ze SCORING SIGNALS:
   - `_explain_preference_match(poi, user)` → "Matches your museum_heritage preference"
   - `_explain_crowd_fit(poi, user)` → "Low-crowd (fits crowd_tolerance=1)"
   - `_explain_budget_fit(poi, user)` → "Good budget fit (ticket: 24 PLN)"
   - `_explain_transit_efficiency(poi, context)` → "Short transit (10 min from previous)"
   - `_explain_travel_style_fit(poi, user)` → "Cultural POI (matches style)"

3. Priorytet reasons:
   - Must-see (priority_level)
   - Preference match
   - Crowd tolerance fit
   - Budget fit
   - Transit efficiency
   - Travel style

4. Testy:
   - Sprawdzić test02-response.json (couples, cultural)
   - Sprawdzić test05-response.json (family, relax)
   - Wszystkie POI muszą mieć niepuste why_selected

**Czas:** 2-3h

---

### Priorytet 2: Problem #12 - Małopolska POI (FEATURE)
**Zadanie:** Rozszerzyć bazę POI o Kraków i Małopolskę

**Implementacja:**
1. **Excel data preparation:**
   - Utworzyć `krakow_poi_v1.xlsx` (30 POI)
   - Format identyczny jak `zakopane_poi_extended_v1.xlsx`
   - Kategorie: jaskinie, underground, history_mystery, museums

2. **POI loading:**
   - Dodać nowy loader: `load_krakow.py`
   - Zmodyfikować `poi_repository.py` - załaduj 2 pliki (Zakopane + Kraków)

3. **Testing:**
   - Test request z city: "Kraków"
   - Sprawdzić czy Wieliczka, jaskinie Ojcowskie są w wynikach

4. **Documentation:**
   - README: jak dodać nowy region
   - Excel template dla nowych regionów

**Czas:** 4-5h (głównie data preparation)

---

## 7. NOTATKI DO PAMIECI

### ✅ Problems Status (11/12 COMPLETED):
1. ✅ Preferences filtering (commit 182e22a)
2. ✅ Target group filtering (commit 182e22a)
3. ✅ Crowd_tolerance (commit 182e22a)
4. ✅ Time gaps (commit 182e22a)
5. ✅ Budget constraint (commit 182e22a)
6. ✅ Cross-day uniqueness (commit 182e22a)
7. ⚠️ **why_selected** (commit 8718c32) - REQUIRES REFINEMENT!
8. ✅ cost_estimate (commit e7b1f6f)
9. ✅ Parking logic (commit de35a29)
10. ✅ must_see (commit 22c4ecf)
11. ✅ dinner_break (commit 6222330)
12. ⏳ Małopolska POI (PENDING - data preparation)

### 🚨 CRITICAL NEXT STEP:
**Problem #7 refinement - zmienić why_selected z szablonów na scoring signals!**

Klientka przesłała test02 i test05 JSONy ŻEBY POKAZAĆ problem z szablonowymi why_selected.
Oczekuje KONKRETNYCH sygnałów: preference match, crowd fit, budget fit, transit time.

---

## 8. ODPOWIEDŹ DLA KLIENTKI

### ✅ Potwierdzenie zrozumienia:

**Problem #7 Refinement:**
- Rozumiem problem - obecne why_selected są szablonowe
- Zmienię na KONKRETNE sygnały scoringowe
- Przykłady: "Matches your museum_heritage preference", "Low-crowd (fits crowd_tolerance=1)"

**Problem #12 Małopolska:**
- Zakres: cała Małopolska (Kraków + okolice)
- MVP: 30 POI z Krakowa (jaskinie + underground)
- Format: nowy Excel jak zakopane_poi_extended_v1.xlsx

**Skalowanie do całej Polski:**
- TAK, architektura jest skalowalna
- POI Repository obsługuje multiple regions
- Scoring jest region-agnostic
- Można dodać 500+ POI bez przebudowy engine

**Co dalej:**
- Najpierw: Problem #7 refinement (2-3h)
- Potem: Problem #12 data preparation (4-5h)
- Testy UAT po obu zmianach

---

## 9. TECHNICAL NOTES

### Scoring Signals dla why_selected:

**Dostępne sygnały w engine:**
1. **preferences_score** (engine.py line ~400)
   - Match do user preferences
   - Tag overlap detection
   
2. **crowd_score** (crowd.py)
   - crowd_tolerance vs popularity
   - Low/medium/high crowd POI
   
3. **budget_score** (budget.py)
   - ticket_price vs budget_level
   - Free/cheap/expensive classification
   
4. **travel_time** (engine.py)
   - Transit duration from previous POI
   - Short/medium/long transit
   
5. **travel_style_score** (travel_style.py)
   - POI type vs travel_style
   - Cultural/relax/active match

### Implementation approach:

**Option A: Pass scoring details to explainability**
```python
explain_poi_selection(
    poi, 
    context, 
    user,
    scoring_details={
        "preferences_match": ["museum_heritage"],
        "crowd_score": 8.5,
        "budget_fit": "good",
        "transit_time": 10
    }
)
```

**Option B: Recalculate in explainability**
- Pros: No engine changes
- Cons: Duplicate scoring logic

**Recommendation: Option A** - pass scoring details from engine to explainability for transparency.

