# CLIENT FEEDBACK - 19.02.2026 (Karolina) - UAT ROUND 2

**Date:** 19.02.2026  
**Context:** Klientka wykonała 10 testów manualnych po wdrożeniu Problem #1-12 (commit aac61c2)  
**Tests:** 10 comprehensive scenarios covering różne grupy, preferencje, budżety

---

## 📊 EXECUTIVE SUMMARY

**Critical Findings:**
- 🔴 **Bug #1:** Parking nachodzi na transit (występuje w 9/10 testów) - CRITICAL
- 🔴 **Bug #2:** dinner_break ma błędne duration_min=90 mimo krótszych slotów - CRITICAL
- 🔴 **Bug #3:** Duże dziury czasowe w harmonogramie (gap filling wymagane) - HIGH
- 🔴 **Bug #4:** why_selected puste [] lub generyczne (nie z preferencji) - HIGH
- 🟡 **Issue #5:** Preferencje ignorowane (history_mystery, kids_attractions, water_attractions, relaxation) - HIGH
- 🟡 **Issue #6:** Crowd_tolerance ignorowane (popularne miejsca oznaczane jako "Low-crowd") - MEDIUM
- 🟢 **Issue #7:** cost_estimate wymaga komunikacji (group vs per person) - LOW

**Statistics:**
- Tests performed: 10
- Critical bugs: 3
- High priority issues: 2
- Medium priority issues: 1
- Low priority issues: 1

**Impact:** Plan generator ma systematyczne błędy w zarządzaniu czasem (parking overlap, duration_min, gap filling) oraz słabo realizuje user preferences.

---

## 🔴 CRITICAL BUGS

### **BUG #1: Parking Nachodzi na Transit (OVERLAP)**

**Severity:** 🔴 CRITICAL  
**Frequency:** 9/10 tests  
**Impact:** Timeline jest fizycznie niemożliwy do realizacji (user nie może parkować przed przyjazdem)

**Examples:**

**Test 01:**
- Day 1: transit 13:53-14:03, parking 13:52-14:07 (parking startuje PRZED dojazdem)
- Day 2: transit 16:31-16:41, parking 16:23-16:38 (parking startuje PRZED dojazdem, overlap)
- Day 3: transit 13:22-13:36, parking 13:25-13:40 (parking w TRAKCIE przejazdu)

**Test 02:**
- Day 1: transit 13:33-13:43, parking 13:32-13:47 (parking PRZED transitem)
- Day 2: transit 14:22-14:36, parking 14:25-14:40 (parking w trakcie)
- Day 3: transit 15:00-15:23, parking 15:12-15:27 (parking w trakcie)

**Test 03:**
- Day 1: transit 13:13-13:23, parking 13:12-13:27 (parking PRZED transitem)

**Test 04:**
- Day 1: transit 14:22-14:37, parking 14:24-14:39 (parking w trakcie)
- Day 2: transit 12:47-12:57, parking 12:46-13:01 (parking PRZED transitem)

**Test 05:**
- Day 2: transit 13:17-13:27, parking 13:16-13:31 (parking PRZED transitem)

**Test 06:**
- Day 1: transit 14:22-14:39, parking 14:28-14:43 (parking w trakcie)
- Day 2: transit 13:47-13:57, parking 13:46-14:01 (parking PRZED transitem)

**Test 07:**
- Day 1: transit 13:13-13:23, parking 13:12-13:27 (parking PRZED transitem)
- Day 2: transit 13:52-14:06, parking 13:55-14:10 (parking w trakcie)

**Test 08:**
- Day 1: transit 13:13-13:23, parking 13:12-13:27 (parking PRZED transitem)
- Day 2: transit 13:52-14:10, parking 13:59-14:14 (parking w trakcie)
- Day 3: transit 14:14-14:38, parking 14:26-14:41 (parking w trakcie)
- Day 7: transit 15:15-15:25, parking 15:14-15:29 (parking PRZED transitem)

**Test 09:**
- Day 1: transit 13:13-13:23, parking 13:12-13:27 (parking PRZED transitem)
- Day 2: transit 14:14-14:35, parking 14:24-14:39 (parking w trakcie)
- Day 3: transit 13:22-13:36, parking 13:25-13:40 (parking w trakcie)

**Test 10:**
- Day 1: transit 13:17-13:27, parking 13:16-13:31 (parking PRZED transitem)
- Day 2: transit 13:34-13:44, parking 13:33-13:48 (parking PRZED transitem)

**Root Cause:**
Prawdopodobnie w `engine.py` parking item jest dodawany bez weryfikacji, że transit już się zakończył. Logika powinna być:

```
transit: 13:53-14:03
parking: 14:03-14:18 (startuje DOKŁADNIE gdy transit się kończy)
attraction: 14:18-XX:XX
```

**Expected Flow:**
1. Transit ends at time T1
2. Parking starts at T1, ends at T2
3. Attraction starts at T2

**Current (Broken) Flow:**
1. Transit scheduled T1-T2
2. Parking scheduled T0-T3 (T0 < T1, T3 może być > T2)
3. OVERLAP / TIME PARADOX

**Files to Check:**
- `app/domain/planner/engine.py` (parking insertion logic)
- Funkcja `_add_parking()` lub podobna

**Priority:** 🔴 P0 - Must fix before next UAT

---

### **BUG #2: dinner_break ma błędne duration_min**

**Severity:** 🔴 CRITICAL  
**Frequency:** 6/10 tests  
**Impact:** Dane response są inconsistent (duration_min nie zgadza się z actual time)

**Examples:**

**Test 01, Day 3:**
```json
{
  "type": "dinner_break",
  "start_time": "18:39",
  "end_time": "19:00",
  "duration_min": 90
}
```
Actual time: 19:00 - 18:39 = **21 minut**, ale duration_min = 90 ❌

**Test 02:**
- Day 2: dinner_break 52 min actual, duration_min=90
- Day 3: dinner_break 25 min actual, duration_min=90

**Test 07, Day 1:**
```json
{
  "type": "dinner_break",
  "start_time": "18:32",
  "end_time": "19:00",
  "duration_min": 90
}
```
Actual time: **28 minut**, duration_min = 90 ❌

**Test 09, Day 3:**
```json
{
  "type": "dinner_break",
  "start_time": "18:39",
  "end_time": "19:00",
  "duration_min": 90
}
```
Actual time: **21 minut**, duration_min = 90 ❌

**Root Cause:**
System planuje dinner_break z duration_min=90, ale potem skraca go do czasu pozostałego do day_end (19:00), nie aktualizując pola duration_min.

**Expected Behavior:**
```json
{
  "type": "dinner_break",
  "start_time": "18:39",
  "end_time": "19:00",
  "duration_min": 21  // ✅ ACTUAL duration
}
```

**Solution:**
Po wygenerowaniu itemu (dinner_break, lunch_break, any time-constrained item), recalculate duration_min:
```python
duration_min = (end_time - start_time).total_seconds() / 60
```

**Files to Check:**
- `app/domain/planner/engine.py` (_insert_dinner_break function)
- Wszystkie miejsca gdzie tworzymy items z duration_min

**Priority:** 🔴 P0 - Must fix (data integrity issue)

---

### **BUG #3: Duże Dziury Czasowe w Harmonogramie**

**Severity:** 🔴 HIGH  
**Frequency:** 8/10 tests  
**Impact:** Plan wygląda nieprofesjonalnie, user nie wie co robić przez 2-3 godziny

**Examples:**

**Test 01, Day 3:**
- Termy kończą się: 15:41
- Kolacja zaczyna się: 18:39
- **Luka: 2h 58min (15:41-18:39)** ❌

**Test 03:**
- Day 1: Termy 16:46 → free_time 19:23 (**2h 37min luki**)
- Day 2: Termy 15:41 → dinner 18:39 (**2h 58min luki**)
- Day 2: dinner kończy 20:09, day_end 21:00 (**51min luki**)

**Test 04, Day 5:**
- Termy: 09:47-11:47
- Dom do góry nogami: 12:07-12:27
- **Luka: 12:27-14:28 (2h 1min)** ❌

**Test 05, Day 1:**
- Lunch kończy się: 14:22
- Day_end: 16:00
- **Luka: 1h 38min (14:22-16:00)** ❌
- Po lunchu plan jest PUSTY, mimo że day_end jest 16:00

**Test 06:**
- Day 1: koniec zwiedzania 15:29, day_end 18:00 (**2h 31min luki**)
- Day 3: lunch 15:16, day_end 18:00 (**2h 44min luki**)

**Test 08, Day 4:**
- Termy: 13:41-15:41
- dinner_break: 18:39-20:00
- **Luka: 2h 58min (15:41-18:39)** ❌

**Test 10, Day 2:**
- Termy kończą się: 15:19
- free_time: 17:14-17:54
- **Luka: 1h 55min (15:19-17:14)** ❌

**Client Requirement:**
> "Po lunchu powinno wejść 1 lekka rzecz kids albo relax (albo oba)"
> "Jeśli zostaje wolny czas do day_end, dodaj automatycznie free_time z sensowną etykietą: 'kolacja / spacer / zakupy'"

**Solution:**
1. **Gap Detection:** Jeśli luka > 60 min, system musi ją wypełnić:
   - Option A: Dodaj lekką atrakcję (short POI, <60min)
   - Option B: Dodaj structured free_time z etykietą: "Coffee break / Shopping / Dinner / Walk"
   
2. **Gap Filling Rules:**
   - Luka 60-90 min → "Coffee break" lub short POI
   - Luka 90-150 min → Short POI + coffee break
   - Luka 150+ min → Full attraction OR error "Not enough time for another activity"

3. **End-of-Day Handling:**
   - Jeśli ostatnia atrakcja kończy się >60min przed day_end:
     - Dodaj free_time: "Dinner and evening leisure" (fill to day_end)

**Files to Check:**
- `app/domain/planner/engine.py` (gap filling logic)
- Może być related do Problem #11 fix (empty days detection)

**Priority:** 🔴 P1 - High priority (user experience critical)

---

## 🟡 HIGH PRIORITY ISSUES

### **ISSUE #4: why_selected Puste lub Generyczne**

**Severity:** 🟡 HIGH  
**Frequency:** 7/10 tests  
**Impact:** User nie rozumie dlaczego POI zostało wybrane, brak explainability

**Examples:**

**Test 02:**
```json
{
  "poi_name": "Dom do góry nogami",
  "why_selected": "Quiet, peaceful destination"  // ❌ To jest atrakcja instagramowa, nie peaceful
}
```

**Test 03:**
```json
{
  "poi_name": "Oksza",
  "why_selected": []  // ❌ PUSTE
},
{
  "poi_name": "Kaplica",
  "why_selected": []  // ❌ PUSTE
},
{
  "poi_name": "Termy Gorący Potok",
  "why_selected": []  // ❌ PUSTE
},
{
  "poi_name": "Termy Bukovina",
  "why_selected": []  // ❌ PUSTE
}
```

**Test 05, Day 2:**
```json
{
  "poi_name": "Wielka Krokiew",
  "why_selected": ["Must-see", "Low-crowd"]  // ❌ Brak odniesienia do kids_attractions/relaxation
},
{
  "poi_name": "Podwodny Świat",
  "why_selected": ["Low-crowd"]  // ❌ Brak "Matches your kids_attractions"
},
{
  "poi_name": "Muzeum Stylu Zakopiańskiego",
  "why_selected": ["Low-crowd"]  // ❌ Brak odniesienia do preferencji
}
```

**Test 07:**
```json
{
  "poi_name": "Wielka Krokiew",
  "why_selected": ["Quiet, peaceful destination"]  // ❌ Grupa: friends + adventure + crowd_tolerance=2
}
```

**Test 08:**
```json
{
  "poi_name": "Morskie Oko",
  "why_selected": ["Quiet, peaceful destination"]  // ❌ Morskie Oko to jedno z najbardziej popularnych miejsc w Polsce
}
```

**Client Requirement:**
> "why_selected powinno być generowane wprost z tych samych sygnałów co scoring (match do preferencji, travel_style, crowd_tolerance, budżet)"
> 
> **Test 05 feedback:**
> "W preferences = kids_attractions + relaxation, a w why_selected nigdzie nie ma 'Matches your kids_attractions' albo 'Matches your relaxation'"
>
> **Test 06 feedback:**
> "W preferences = museum_heritage, nature_landscape, relaxation powinno być w why_selected:
> - 'Matches your museum_heritage preference'
> - 'Matches your nature_landscape preference'
> - 'Matches your relaxation preference'
> A tu głównie 'Must-see' i 'Low-crowd'."
>
> **Test 07 feedback:**
> "Może warto generować why_selected z mapowania?
> - crowd_tolerance=2 → 'moderate crowd ok'
> - travel_style=adventure → 'active / dynamic / experience-driven'
> - group friends → 'good for group / fun factor / shared experience'"

**Root Cause:**
Problem #7 refinement (commit aac61c2) dodał scoring signal functions, ale:
1. Niektóre POI wciąż mają puste why_selected (nie wszystkie ścieżki są covered)
2. "Quiet, peaceful destination" jest spamowane mimo profilu user (friends+adventure)
3. Brak mapowania preferencji → why_selected text

**Solution:**
1. **Ensure No Empty why_selected:**
   - Każdy POI MUSI mieć ≥1 reason
   - Jeśli brak specific match, fallback: "Fits your travel plan timing and location"

2. **Stop Spamming Generic Phrases:**
   - Usunąć hardcoded "Quiet, peaceful destination"
   - Generować tylko z faktycznych scoringu signals:
     * Preference match
     * Crowd fit
     * Budget fit
     * Travel style match
     * Must-see status

3. **Add Preference Mapping:**
```python
PREFERENCE_TEXTS = {
    "kids_attractions": "Matches your kids_attractions preference",
    "nature_landscape": "Matches your nature_landscape preference",
    "museum_heritage": "Matches your museum_heritage preference",
    "relaxation": "Matches your relaxation preference",
    "water_attractions": "Matches your water_attractions preference",
    "history_mystery": "Matches your history_mystery preference",
    # ... etc
}
```

4. **Add Profile-Based Reasons:**
```python
if user.group.type == "friends" and user.travel_style == "adventure":
    reasons.append("Great for group adventures")
    
if user.group.crowd_tolerance >= 2:
    reasons.append("Popular attraction (fits your crowd comfort)")
```

**Files to Check:**
- `app/domain/planner/explainability.py` (explain_poi_selection function)
- Helper functions: _explain_preference_match, _explain_travel_style_match

**Priority:** 🟡 P1 - High (explainability jest core value proposition)

---

### **ISSUE #5: Preferencje Ignorowane przez Engine**

**Severity:** 🟡 HIGH  
**Frequency:** 7/10 tests  
**Impact:** Plan nie realizuje user expectations, satisfaction spadnie

**Breakdown by Preference:**

#### **5A: history_mystery Ignorowane**

**Test 04 (5 dni, solo, preferences: nature + history_mystery + museum_heritage):**
> "W całym 5-dniowym planie jest natura (Kościeliska, Morskie Oko, Rusinowa), jest heritage (Muzeum Tatrzańskie, Koliba/Atma) ale **mystery nie ma praktycznie nic**."

**Test 07 (2 dni, friends, preferences: underground + history_mystery + museum_heritage):**
> "muzeum jest (Muzeum Tatrzańskie / Koliba) OK
> underground: 0 elementów (ale to zrozumiałe bo nie mamy)
> **history_mystery: praktycznie 0** (poza muzeami; za to jest Dom do góry nogami, papugarnia, mini zoo…)"

**Client Suggestion:**
> "Może zróbmy regułę: jeśli w preferencjach jest underground/history_mystery, plan musi zawierać co najmniej X takich POI dziennie albo dać alternatywę."

#### **5B: kids_attractions Słabo Realizowane**

**Test 05 (2 dni, family kids 3-6, preferences: kids_attractions + relaxation, travel_style=relax):**
> "Kids_attractions są słabo realizowane:
> - Day 1: Rusinowa to nie kids_attractions (może być family friendly, ale to nadal 'natura/trail')
> - Day 2: Podwodny Świat ok jako kids, ale reszta to… muzeum + Krokiew
> 
> **Jeśli preferences mają kids_attractions jako top, to plan powinien mieć przynajmniej 1 kids POI dziennie jako core.**"

#### **5C: relaxation Nie Istnieje w Planach**

**Test 05 (family kids, preferences: kids_attractions + relaxation, travel_style=relax):**
> "preferences = kids_attractions + relaxation, a **w planie brak term / basenów / spa / strefy relaksu** w oba dni.
> I jeszcze travel_style=relax, a Day 2 to 'zaliczanie' (Krokiew + akwarium + muzeum)."

**Test 06 (seniors, preferences: museum_heritage + relaxation + nature_landscape, travel_style=relax):**
> "Brak realizacji preferencji 'relaxation' (mimo travel_style=relax)
> **W całym planie nie ma żadnej atrakcji/segmentu, który realnie wspiera relaxation: brak term / spa / łaźni / spokojnej strefy relaksu**"

**Test 09 (solo, preferences: nature_landscape + relaxation, travel_style=relax):**
> "Dzień 1 to 'miasto + muzea + zoo + papugarnia'. To jest bardziej family / sightseeing niż **relax + nature**."
> 
> "Ogólna jakość: **'relax' powinno mieć więcej prawdziwego relaksu**
> W planie np. czasu na kawę (1 blok free_time dziennie w sensownym miejscu)"

#### **5D: water_attractions "Na Siłę"**

**Test 10 (couples, preferences: water_attractions + relaxation + local_food_experience, travel_style=relax, budget=1):**
> "Day 1: Wielka Krokiew + Podwodny Świat + 2 muzea + kaplica.
> To jest miks 'must-see i kultura', a nie **'woda + relaks'**.
> 
> **water_attractions: Podwodny Świat (akwarium) to woda 'na siłę', ale to nie jest relaksująca atrakcja wodna w Zakopanem.**"

**Client Requirement for Test 10:**
> "Dla: couples + relax + water + food + low budget, idealny 'szkielet' dnia to:
> 1. 1 główna atrakcja wodna (termy)
> 2. 1 spokojny spacer widokowy / łatwa trasa
> 3. 1 mocny punkt 'jedzeniowy'
> 4. **mało muzeów**"

#### **5E: active_sport + mountain_trails Ignorowane**

**Test 03 (friends, preferences: active_sport + mountain_trails + history_mystery, travel_style=adventure):**
> "Plan nie realizuje 'active_sport' i 'mountain_trails' w Day 1
> Day 1 to: Krokiew + muzeum + galeria + kaplica + termy. To jest **miks 'must-see + kultura + relaks', a nie 'friends + adventure + active_sport + mountain_trails'**."

---

**Root Cause Analysis:**

1. **Scoring System Preference Weights:**
   - Prawdopodobnie preferences mają zbyt mały weight w total score
   - Must-see POI (priority_level=12) overrides preferences
   - System wybiera "safe" choices (muzea, must-see) zamiast match do preferences

2. **POI Repository Gaps:**
   - Może brakuje wystarczającej ilości POI z tagami: relaxation, water_attractions, history_mystery?
   - Jeśli tak, system nie ma z czego wybierać

3. **Travel_style Not Used Properly:**
   - travel_style=relax powinien drastycznie zwiększać weight dla: termy, spa, easy trails, free_time
   - travel_style=adventure powinien zwiększać weight dla: active_sport, mountain_trails, long hikes

4. **No Minimum Preference Coverage Rule:**
   - Brak walidacji: "Jeśli preference X jest w top 3, plan MUSI mieć ≥1 POI z tym tagiem dziennie"

**Solution:**

1. **Add Preference Coverage Validator:**
```python
def validate_preference_coverage(day_plan, user_preferences):
    """Ensure each day has at least 1 POI matching top preferences"""
    top_prefs = user_preferences[:3]  # Top 3 preferences
    
    for pref in top_prefs:
        matched_poi = [poi for poi in day_plan if pref in poi.tags]
        if len(matched_poi) == 0:
            # Warning or try to inject a matching POI
            logger.warning(f"Day has no POI matching preference: {pref}")
```

2. **Increase Preference Weight in Scoring:**
```python
# OLD: preference_match gives +5 points
# NEW: preference_match gives +15 points (especially for top 3 preferences)

if pref in user_preferences[:3]:  # Top 3
    score += 15
elif pref in user_preferences:  # Other preferences
    score += 8
```

3. **Add travel_style Modifiers:**
```python
if user.travel_style == "relax":
    if "relaxation" in poi.tags or "spa" in poi.tags or "termy" in poi.tags:
        score *= 1.5  # 50% boost
    if "active_sport" in poi.tags:
        score *= 0.5  # 50% penalty
        
if user.travel_style == "adventure":
    if "active_sport" in poi.tags or "mountain_trails" in poi.tags:
        score *= 1.5
    if "museum_heritage" in poi.tags:
        score *= 0.7  # Slight penalty (not impossible, but lower priority)
```

4. **Audit POI Repository:**
   - Check: Ile mamy POI z tagiem "relaxation", "water_attractions", "history_mystery"?
   - If insufficient, either:
     * Add more POI to repository
     * Add aliases/synonyms for matching (e.g., termy → relaxation + water_attractions)

**Files to Check:**
- `app/domain/planner/scoring.py` (preference weights)
- `app/domain/planner/engine.py` (POI selection logic)
- `data/zakopane_poi_extended_v1.xlsx` (POI repository audit)

**Priority:** 🟡 P1 - High (core value proposition: personalization)

---

## 🟠 MEDIUM PRIORITY ISSUES

### **ISSUE #6: Crowd_tolerance Ignorowane**

**Severity:** 🟠 MEDIUM  
**Frequency:** 5/10 tests  
**Impact:** why_selected mówi "Low-crowd", a POI jest popularne → brak wiarygodności

**Examples:**

**Test 04 (solo, crowd_tolerance=1):**
> "Crowd_tolerance = 1, a engine pcha 'centrumowe / popularne' rzeczy + kids zapychacze"
> "W wielu miejscach powtarza się: **'Low-crowd option (fits crowd_tolerance: 1)' dla atrakcji, które w realu potrafią być tłoczne** (Krokiew, Krupówki, Morskie Oko w sezonie)."

**Test 05 (family kids, crowd_tolerance=1):**
> "Crowd_tolerance = 1 ignorowane przez dobór. Tu to samo co wcześniej:
> - **Krokiew potrafi być tłoczna**, a engine daje tekst 'Low-crowd option'
> - Muzeum Stylu + okolice centrum też potrafią być gęste, zwłaszcza w sezonie."

**Test 06 (seniors, crowd_tolerance=1, travel_style=relax):**
> "Profil 'seniors + crowd_tolerance=1' ignorowany:
> - Day 2 zaczyna się od Wielkiej Krokwi (**miejsce potencjalnie tłoczne**), a engine znów daje tekst 'Low-crowd option'.
> - Dodatkowo wrzuca Mini Zoo (to raczej rodziny z dziećmi, nie seniorzy jako domyślny wybór)."

**Test 08 (couples, crowd_tolerance=2):**
> "'Quiet, peaceful destination' to jest prawie wszędzie, nawet przy **Morskim Oku, Krupówki/atrakcje na Krupówkach** i termach"

**Root Cause:**
1. **Scoring system:** crowd_tolerance penalty za high_crowd POI jest zbyt słaby
2. **why_selected generyka:** System generuje "Low-crowd option" dla każdego POI jeśli user ma crowd_tolerance=1, bez real fact-checking POI crowd_level

**Solution:**

1. **Accurate POI Crowd Levels:**
   - Review POI repository: czy `crowd_level` jest accurate?
   - Popular POI (Morskie Oko, Krupówki, Wielka Krokiew) powinny mieć crowd_level=3
   - Spokojne szlaki (Rusinowa, Dolina Kościeliska off-season) → crowd_level=1

2. **Stronger Crowd Penalty:**
```python
if user.crowd_tolerance == 1:  # Low tolerance
    if poi.crowd_level >= 3:  # High crowd
        score *= 0.3  # 70% penalty (strong)
    elif poi.crowd_level == 2:  # Medium crowd
        score *= 0.7  # 30% penalty
```

3. **Fix why_selected Logic:**
```python
def _explain_crowd_fit(poi, user):
    if user.crowd_tolerance == 1 and poi.crowd_level <= 1:
        return "Low-crowd option (fits your crowd_tolerance: 1)"
    elif user.crowd_tolerance >= 2 and poi.crowd_level == 3:
        return "Popular attraction (fits your crowd comfort)"
    # DON'T SAY "Low-crowd" if POI actually has high crowd_level
    return None
```

**Files to Check:**
- `data/zakopane_poi_extended_v1.xlsx` (crowd_level column accuracy)
- `app/domain/planner/scoring.py` (crowd penalty weights)
- `app/domain/planner/explainability.py` (_explain_crowd_fit function)

**Priority:** 🟠 P2 - Medium (affects trust, but not blocking)

---

## 🟢 LOW PRIORITY ISSUES

### **ISSUE #7: cost_estimate Communication**

**Severity:** 🟢 LOW  
**Frequency:** Mentioned in Test 03  
**Impact:** User może być confused czy cost_estimate jest per person czy for group

**Client Feedback (Test 03):**
> "Cost_estimate wygląda jak liczony 'na grupę', ale **musimy to przekazać w komunikacji**, że cost_estimate = total for group (bo inaczej będzie zamieszanie przy UI)."

**Current Status:**
- Problem #8 (cost_estimate inconsistent) został fixed 16.02.2026
- System teraz liczy poprawnie (per person vs group)
- Ale w API response nie ma explicit note: "This is total for your group of X people"

**Solution:**

**Option A: Add Field to Response:**
```json
{
  "cost_estimate": 120,
  "cost_breakdown": {
    "per_person": 30,
    "group_size": 4,
    "total": 120
  }
}
```

**Option B: Add Hint in Documentation:**
- Swagger docs: "cost_estimate represents total cost for the entire group"
- Frontend tooltip: "Total cost for your group (X people)"

**Option C: Add to day summary:**
```json
{
  "day_summary": {
    "total_cost_estimate": 500,
    "cost_note": "Total for your group of 4 people"
  }
}
```

**Recommendation:** Option A (most explicit, best UX)

**Files to Check:**
- `app/domain/planner/explainability.py` (cost calculation)
- `app/api/routes/plan.py` (response normalization)

**Priority:** 🟢 P3 - Low (documentation/communication issue, not a bug)

---

## 📋 OTHER OBSERVATIONS

### **O1: Teleports / Time Paradoxes (Related to Bug #1)**

**Test 08, Day 5:**
> "Chochołów +… Myszogród (bez przejazdu i z teleportem w czasie)
> - transit 11:17–11:37 do Myszogrodu
> - a potem parking 14:00–14:15 i Myszogród 14:18–14:48"

This suggests że czasem parking jest duplikowany lub generator nie synchronizuje timeline properly.

**Likely Related to Bug #1** (parking overlap). Fix Bug #1 first, then re-test.

---

### **O2: Free_time jako "Zapychacz na Siłę"**

**Test 08:**
> "free_time jako zapychacz:
> - Day 6 i Day 7 wyglądają jak plan wygenerowany na siłę, żeby zapełnić do 20:00."

**Test 09:**
> "Day 6: free_time 09:00–09:40 + free_time 09:40–10:20, a atrakcja Tatrzański Park Edukacyjny 09:19–10:19"

This is likely **OVERLAP BUG** similar to parking/transit, but with free_time and attractions.

**Related to Bug #1 and Bug #3** (gap filling + overlaps). Comprehensive timeline validator needed.

---

### **O3: Realističnost "realistic_timing" Badge**

**Test 09, Day 2:**
> "'realistic_timing' jest naciągane.
> Po 12:22 jest free_time 13:12–13:34 i lunch 13:34–14:14, a potem transit 'z Morskiego Oka do Zakopanego' 21 min."

This suggests quality badge "realistic_timing" może być assigned nawet gdy timeline ma luki/overlaps.

**Solution:** quality_badges powinny być generated AFTER timeline validation (bug #1-3 fixed).

---

### **O4: Brak Atrakcji w POI w Harmonogramie**

**Test 06, Day 3:**
> "Braki w strukturze: 'Atma' bez parkingu w timeline
> Day 3: do Atmy jest transit, ale nie ma elementu parking (a w obiekcie atrakcji jest parking 'PARKING KRUPÓWKI AK')."

**Possible Causes:**
1. Parking logic skipped dla downtown locations (Krupówki)?
2. Parking tylko dla "big" attractions (termy, trails), not museums?

**Investigation Needed:** Check parking insertion rules w engine.py

---

## 🎯 PRIORITY MATRIX

### **P0 - MUST FIX (Blockers):**
1. 🔴 **Bug #1: Parking Overlap** (9/10 tests) - timeline physically impossible
2. 🔴 **Bug #2: dinner_break duration_min** (6/10 tests) - data integrity issue

### **P1 - HIGH PRIORITY (Before Next UAT):**
3. 🔴 **Bug #3: Gap Filling** (8/10 tests) - UX critical, plan looks unprofessional
4. 🟡 **Issue #4: why_selected** (7/10 tests) - explainability jest core value
5. 🟡 **Issue #5: Preferences Ignored** (7/10 tests) - personalization nie działa

### **P2 - MEDIUM PRIORITY (Nice to Have):**
6. 🟠 **Issue #6: Crowd_tolerance** (5/10 tests) - affects trust
7. 🟢 **Issue #7: cost_estimate communication** (1/10 tests) - documentation

### **P3 - LOW PRIORITY (Backlog):**
8. Observations (teleports, free_time overlaps, parking missing for some POI)

---

## 📊 TEST SCENARIOS SUMMARY

| Test | Group | Days | Budget | Key Prefs | Main Issues |
|------|-------|------|--------|-----------|-------------|
| 01 | Family kids | 3 | 2 (std) | kids, nature, trails | Parking overlap (3x), dinner duration, gap Day 3 |
| 02 | Couples | 3 | 3 (premium) | museum, relax, food | Parking overlap (3x), dinner duration, generic why_selected |
| 03 | Friends | 2 | 2 (std) | active, trails, mystery | Parking overlap, huge gaps, prefs ignored (active/trails), empty why_selected |
| 04 | Solo | 5 | 1 (low) | nature, mystery, heritage | Parking overlap (2x), mystery ignored, crowd_tolerance ignored, gap Day 5 |
| 05 | Family kids | 2 | 2 (std) | kids, relax | Parking overlap, gap Day 1, kids/relax ignored, generic why_selected |
| 06 | Seniors | 3 | 2 (std) | heritage, relax, nature | Parking overlap (2x), relax ignored, gaps Day 1 & 3, missing parking for Atma |
| 07 | Friends | 2 | 2 (std) | underground, mystery, heritage | Parking overlap (2x), dinner duration, mystery ignored, generic why_selected |
| 08 | Couples | 7 | 2 (std) | trails, nature, food, heritage | Parking overlap (4x), free_time spam, gap Day 4, teleport Day 5, overlap Day 6 |
| 09 | Solo | 3 | 2 (std) | nature, relax | Parking overlap (3x), dinner duration, relax ignored, "realistic_timing" naciągane |
| 10 | Couples | 2 | 1 (low) | water, relax, food | Parking overlap (2x), water/relax ignored, gap Day 2 |

**Overall Stats:**
- **Parking overlap:** 9/10 tests (90%) 🔴
- **dinner_break duration bug:** 4/10 tests explicitly mentioned (40%) 🔴
- **Gap filling issues:** 8/10 tests (80%) 🔴
- **why_selected problems:** 7/10 tests (70%) 🟡
- **Preferences ignored:** 7/10 tests (70%) 🟡
- **Crowd_tolerance ignored:** 5/10 tests (50%) 🟠

---

## 🛠️ RECOMMENDED FIX ORDER

### **Sprint 1 (Feb 19-20): Critical Timeline Bugs**
1. **Bug #1: Parking Overlap Fix**
   - Time estimate: 4-6 hours
   - Root cause investigation: 1h
   - Fix implementation: 2h
   - Comprehensive testing: 2-3h

2. **Bug #2: dinner_break duration_min Fix**
   - Time estimate: 2 hours
   - Fix: Recalculate duration_min after time adjustment
   - Test all break types (lunch, dinner, restroom, etc.)

3. **Bug #3: Gap Filling Logic**
   - Time estimate: 6-8 hours
   - Implement gap detection (threshold: 60min)
   - Implement gap filling strategies (short POI / free_time)
   - End-of-day handling

**Total: 12-16 hours (1.5-2 days)**

---

### **Sprint 2 (Feb 21-22): Explainability & Preferences**
4. **Issue #4: why_selected Refinement 2.0**
   - Time estimate: 4-5 hours
   - Eliminate generic phrases ("Quiet, peaceful")
   - Ensure no empty why_selected
   - Add preference mapping texts
   - Add profile-based reasons (friends/adventure, seniors/relax, etc.)

5. **Issue #5: Preference Coverage Enforcement**
   - Time estimate: 6-8 hours
   - Audit POI repository (tag coverage)
   - Increase preference weights in scoring
   - Add travel_style modifiers
   - Implement preference coverage validator

**Total: 10-13 hours (1.5 days)**

---

### **Sprint 3 (Feb 23-24): Polish & Testing**
6. **Issue #6: Crowd_tolerance Accuracy**
   - Time estimate: 3-4 hours
   - Audit POI crowd_level data
   - Strengthen crowd penalty in scoring
   - Fix _explain_crowd_fit logic

7. **Issue #7: cost_estimate Communication**
   - Time estimate: 1-2 hours
   - Add cost_breakdown to response

8. **Comprehensive Regression Testing**
   - Time estimate: 4-6 hours
   - Re-run all 10 test scenarios
   - Validate all fixes
   - Document results

**Total: 8-12 hours (1-1.5 days)**

---

### **Total Effort Estimate: 30-41 hours (4-5 days)**

---

## 📝 TESTING CHECKLIST (After Fixes)

For each test scenario (01-10), validate:

✅ **Timeline Integrity:**
- [ ] No parking overlaps with transit
- [ ] No attraction overlaps with free_time
- [ ] All duration_min fields match actual time
- [ ] Gaps >60min are filled with POI or structured free_time
- [ ] End-of-day gaps are filled with evening free_time

✅ **Preference Coverage:**
- [ ] Each day has ≥1 POI matching top 3 preferences
- [ ] travel_style is reflected in POI selection
- [ ] Special preferences (kids_attractions, relaxation, water_attractions) are realized

✅ **Explainability:**
- [ ] No empty why_selected
- [ ] No generic "Quiet, peaceful destination" spam
- [ ] why_selected references actual user preferences
- [ ] Profile-based reasons (friends/adventure, seniors/relax) present

✅ **Crowd & Budget:**
- [ ] crowd_tolerance is respected (low tolerance → avoid high_crowd POI)
- [ ] cost_estimate is accurate and clearly communicated
- [ ] why_selected doesn't say "Low-crowd" for popular POI

✅ **Quality:**
- [ ] Quality badges are accurate (realistic_timing, has_must_see, good_variety)
- [ ] No teleports / time paradoxes
- [ ] Parking is present where needed (not missing for downtown attractions)

---

## 🔄 SCOPE DISCUSSION: Problem #12 (Małopolska POI)

**Client Note:**
> "Miałam mylne wyobrażenie, myślałam że podpięcie większej bazy nie będzie wymagało dodatkowe pracy. Nie chcę Ci oczywiście dokładać tego co nie było przewidziane w naszej umowie."

**Interpretation:**
Klientka rozumie, że Małopolska POI expansion (30 POI Kraków) to NEW FEATURE beyond ETAP 2 scope. Nie chce dokładać pracy poza umową.

**Recommendation:**
- **ETAP 2:** Focus on fixing 7 issues (Bugs #1-3, Issues #4-7) from this UAT feedback
- **Problem #12 (Małopolska):** Defer to ETAP 3 or separate mini-project after ETAP 2 delivery

**ETAP 2 Revised Completion Criteria:**
- ✅ All 11 original UAT problems fixed (Problems #1-11 from 16.02.2026) - DONE
- ✅ Problem #7 refinement (scoring signals) - DONE (commit aac61c2)
- 🔄 Round 2 UAT feedback (7 issues from 19.02.2026) - IN PROGRESS
- 🎯 Delivery: Clean, bug-free system for Zakopane region
- 📅 Timeline: 4-5 days (19-24.02.2026)

**Next Steps:**
1. Complete Sprint 1 (critical timeline bugs) - Feb 19-20
2. Complete Sprint 2 (explainability & preferences) - Feb 21-22
3. Complete Sprint 3 (polish & testing) - Feb 23-24
4. Deliver ETAP 2 with comprehensive test report
5. Propose ETAP 3 scope (Małopolska expansion + additional features)

---

## 📎 ATTACHMENTS

**Test Data Location:** (Provided by client in message, not as files)  
**Previous Feedback:** CLIENT_FEEDBACK_16_02_2026_KAROLINA.md  
**Problem #7 Refinement:** PROBLEM7_REFINEMENT_RAPORT_PELNY.md  
**ETAP 2 Plan:** ETAP2_PLAN_DZIALANIA.md

---

**Document Created:** 19.02.2026  
**Author:** System Analysis (Based on Client Feedback)  
**Status:** 🔄 ACTIVE - Bugfixes in Progress  
**Next Review:** After Sprint 1 completion (20.02.2026)
