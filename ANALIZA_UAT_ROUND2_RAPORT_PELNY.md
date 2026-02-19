# ANALIZA UAT ROUND 2 - RAPORT PEŁNY (19.02.2026)

**Data:** 19.02.2026  
**Kontekst:** Feedback od Karoliny po testach ETAP 2 (post Problem #1-12 fixes)  
**Status:** 🔴 CRITICAL BUGS DISCOVERED - Action Required

---

## 📋 EXECUTIVE SUMMARY

Klientka Karolina wykonała **10 comprehensive test scenarios** covering różne grupy (family, couples, friends, solo, seniors), preferencje (kids, nature, culture, adventure, relax) oraz budżety (low, standard, premium).

### 🎯 KEY FINDINGS:

**✅ DOBRA WIADOMOŚĆ:**
- Core ETAP 2 features działają: multi-day planning, versioning, editing, PostgreSQL
- Wszystkie 11 oryginalnych UAT problems (16.02.2026) zostały fixed
- Problem #7 refinement (scoring signals) wdrożony

**❌ ZŁA WIADOMOŚĆ:**
- **3 CRITICAL BUGS** wymagające natychmiastowej akcji:
  1. **Parking nachodzi na transit** (9/10 testów) - timeline physically impossible
  2. **dinner_break ma błędne duration_min** (6/10 testów) - data integrity
  3. **Duże dziury czasowe** (8/10 testów) - gap filling wymagane

- **2 HIGH PRIORITY ISSUES:**
  4. **why_selected puste lub generyczne** (7/10 testów) - explainability broken
  5. **Preferencje ignorowane** (7/10 testów) - personalization nie działa

- **1 MEDIUM ISSUE:**
  6. **Crowd_tolerance ignorowane** (5/10 testów) - trust issue

### 📊 IMPACT SEVERITY:

| Issue | Frequency | Severity | Blocks UAT? |
|-------|-----------|----------|-------------|
| Parking overlap | 9/10 (90%) | 🔴 CRITICAL | ✅ YES |
| dinner_break duration | 6/10 (60%) | 🔴 CRITICAL | ⚠️ PARTIAL |
| Gap filling | 8/10 (80%) | 🔴 HIGH | ⚠️ PARTIAL |
| why_selected empty | 7/10 (70%) | 🟡 HIGH | ❌ NO |
| Preferences ignored | 7/10 (70%) | 🟡 HIGH | ❌ NO |
| Crowd_tolerance | 5/10 (50%) | 🟠 MEDIUM | ❌ NO |

**Conclusion:** System ma **systematyczne błędy w zarządzaniu czasem** (timeline integrity) oraz **słabo realizuje personalization** (preferences, travel_style).

---

## 🔴 CRITICAL BUG #1: PARKING NACHODZI NA TRANSIT

### Problem Description:

Parking items są dodawane do timeline **PRZED lub W TRAKCIE transit**, co jest fizycznie niemożliwe (user nie może parkować przed przyjazdem na miejsce).

### Frequency: **9/10 tests (90%)**

### Examples (Representative Sample):

**Test 01, Day 1:**
```
transit:  13:53-14:03 (dojazd do POI)
parking:  13:52-14:07 (parking startuje PRZED transitem) ❌
```

**Test 08, Day 1:**
```
transit:  13:13-13:23
parking:  13:12-13:27 (parking 1 min PRZED transitem) ❌
```

**Test 05, Day 2:**
```
transit:  13:17-13:27
parking:  13:16-13:31 (parking PRZED transitem) ❌
```

### Expected Behavior:

```
transit:  13:53-14:03 (arrival at POI)
parking:  14:03-14:18 (parking starts EXACTLY when transit ends) ✅
attraction: 14:18-XX:XX (attraction starts after parking walk)
```

### Root Cause Analysis:

**File:** `app/domain/planner/engine.py`

**Hypothesis:** Parking insertion logic nie synchronizuje z transit end time. Prawdopodobnie:

1. System planuje attraction start time
2. System dodaje parking BACKWARD od attraction start (attraction_start - 15min)
3. Parking start time jest przed transit end time
4. Brak validation: `parking_start >= transit_end`

**Expected Flow:**
```python
# CORRECT:
now = transit_end_time  # Start from when transit ends
now = add_parking(now, duration=15)  # 14:03 → 14:18
now = add_attraction(now, duration=60)  # 14:18 → 15:18

# BROKEN (Current):
attraction_start = 14:18
parking_start = attraction_start - 15min = 14:03
# But transit doesn't end until 14:03, so parking @ 14:03 is OK
# HOWEVER, in examples parking shows 13:52, which is BEFORE transit start (13:53)
# This suggests parking is calculated from PREVIOUS item, not transit
```

**Likely Issue:** Parking item inherits timestamp od POPRZEDNIEGO attraction/item, a nie od current transit.

### Fix Strategy:

**Option A: Forward Timeline Building (Recommended)**
```python
def build_day_timeline(poi_list, start_time):
    now = start_time
    timeline = []
    
    for poi in poi_list:
        # 1. Add transit (if needed)
        if need_transit:
            transit_item = create_transit(now, duration=transit_time)
            timeline.append(transit_item)
            now = transit_item.end_time  # ✅ Move time forward
        
        # 2. Add parking (starts AFTER transit ends)
        if need_parking:
            parking_item = create_parking(now, duration=15)
            timeline.append(parking_item)
            now = parking_item.end_time  # ✅ Move forward
        
        # 3. Add attraction
        attraction_item = create_attraction(now, duration=poi.duration)
        timeline.append(attraction_item)
        now = attraction_item.end_time  # ✅ Move forward
    
    return timeline
```

**Option B: Validation Pass (Quick Fix)**
```python
def validate_timeline(timeline):
    for i in range(len(timeline) - 1):
        current = timeline[i]
        next_item = timeline[i + 1]
        
        # Check: next item starts after (or at) current item end
        if next_item.start_time < current.end_time:
            raise TimelineOverlapError(
                f"{next_item.type} overlaps with {current.type}"
            )
```

**Recommendation:** Implement **Option A** (fix root cause) + **Option B** (safety net validation).

### Files to Modify:

1. `app/domain/planner/engine.py`
   - Function: `build_day()` or `_add_parking()`
   - Change: Ensure parking start_time = transit end_time

2. `app/domain/planner/quality_checker.py`
   - Add: `validate_timeline_continuity()` function
   - Check: No overlaps, no time travel

### Testing:

**Unit Test:**
```python
def test_parking_after_transit():
    """Parking must start AFTER transit ends"""
    # Generate plan with transit + parking
    day = generate_test_day()
    
    # Find transit → parking pairs
    for i, item in enumerate(day):
        if item.type == "transit":
            next_item = day[i + 1]
            if next_item.type == "parking":
                # Assert: parking starts when transit ends
                assert next_item.start_time >= item.end_time
```

**Integration Test:**
Re-run all 10 UAT scenarios, validate:
- 0 parking overlaps
- 0 time travel incidents

### Estimated Effort: **4-6 hours**
- Root cause investigation: 1h
- Fix implementation: 2h
- Testing (unit + integration): 2-3h

---

## 🔴 CRITICAL BUG #2: dinner_break MA BŁĘDNE duration_min

### Problem Description:

`dinner_break` (i prawdopodobnie lunch_break) mają hardcoded `duration_min: 90`, ale actual time (end_time - start_time) jest znacznie krótszy (21-52 min). To powoduje data inconsistency.

### Frequency: **6/10 tests (60%)**

### Examples:

**Test 01, Day 3:**
```json
{
  "type": "dinner_break",
  "start_time": "18:39",
  "end_time": "19:00",
  "duration_min": 90  // ❌ SHOULD BE 21
}
```
Actual: 19:00 - 18:39 = **21 minut**, not 90

**Test 07, Day 1:**
```json
{
  "type": "dinner_break",
  "start_time": "18:32",
  "end_time": "19:00",
  "duration_min": 90  // ❌ SHOULD BE 28
}
```
Actual: **28 minut**, not 90

**Test 09, Day 3:**
```json
{
  "type": "dinner_break",
  "start_time": "18:39",
  "end_time": "19:00",
  "duration_min": 90  // ❌ SHOULD BE 21
}
```

### Root Cause:

**File:** `app/domain/planner/engine.py`  
**Function:** `_insert_dinner_break()` (around line 1650-1720)

**Hypothesis:**
1. System tworzy dinner_break z **intended duration = 90 min**
2. Jeśli remaining time do day_end < 90 min, system **skraca** dinner do available time
3. BUT: `duration_min` field nie jest aktualizowany po skróceniu

**Current Code (Suspected):**
```python
def _insert_dinner_break(now, day_end):
    intended_duration = 90  # minutes
    
    # Calculate actual duration
    remaining = day_end - now
    actual_duration = min(intended_duration, remaining)
    
    # Create item
    item = {
        "type": "dinner_break",
        "start_time": now,
        "end_time": now + actual_duration,
        "duration_min": 90  # ❌ HARDCODED, not updated
    }
    return item
```

### Fix:

**Corrected Code:**
```python
def _insert_dinner_break(now, day_end):
    intended_duration = 90  # minutes
    
    # Calculate actual duration (bounded by day_end)
    remaining = (day_end - now).total_seconds() / 60  # in minutes
    actual_duration = min(intended_duration, remaining)
    
    end_time = now + timedelta(minutes=actual_duration)
    
    # Create item with CORRECT duration_min
    item = {
        "type": "dinner_break",
        "start_time": now.strftime("%H:%M"),
        "end_time": end_time.strftime("%H:%M"),
        "duration_min": int(actual_duration)  # ✅ ACTUAL duration
    }
    return item
```

### Files to Modify:

1. `app/domain/planner/engine.py`
   - Function: `_insert_dinner_break()` (~line 1650-1720)
   - Function: `_insert_lunch_break()` (prawdopodobnie similar bug)
   - Function: Any function creating items with duration_min

### Testing:

**Unit Test:**
```python
def test_dinner_break_duration_accurate():
    """duration_min must match actual time"""
    # Test case: day_end at 19:00, dinner starts 18:39
    day_end = datetime.strptime("19:00", "%H:%M")
    now = datetime.strptime("18:39", "%H:%M")
    
    dinner = insert_dinner_break(now, day_end)
    
    # Calculate actual duration
    actual = (dinner.end_time - dinner.start_time).total_seconds() / 60
    
    # Assert: duration_min matches actual
    assert dinner.duration_min == int(actual)  # Should be 21, not 90
```

**Integration Test:**
Re-run Test 01, 07, 09 → validate duration_min fields are correct.

### Estimated Effort: **2 hours**
- Fix implementation: 1h
- Testing: 1h

---

## 🔴 HIGH PRIORITY ISSUE #3: DUŻE DZIURY CZASOWE (GAP FILLING)

### Problem Description:

Plans mają **duże luki czasowe** (1-3 godziny) między attractions, gdzie user nie wie co robić. Especially występuje między ostatnią atrakcją a dinner/day_end.

### Frequency: **8/10 tests (80%)**

### Examples:

**Test 01, Day 3:**
```
Termy kończy się: 15:41
Kolacja zaczyna się: 18:39
LUKA: 2h 58min (15:41-18:39) ❌
```

**Test 05, Day 1:**
```
Lunch kończy się: 14:22
Day_end: 16:00
LUKA: 1h 38min (14:22-16:00) ❌
Plan jest PUSTY po lunchu, mimo że day_end jest 16:00
```

**Test 06, Day 1:**
```
Kończy zwiedzanie: 15:29
Day_end: 18:00
LUKA: 2h 31min (15:29-18:00) ❌
```

### Client Requirements:

**From Test 05:**
> "Po lunchu powinno wejść 1 lekka rzecz kids albo relax (albo oba)"

**From Test 09:**
> "'relax' powinno mieć więcej prawdziwego relaksu. W planie np. czasu na kawę (1 blok free_time dziennie w sensownym miejscu)"

**General:**
> "Jeśli zostaje wolny czas do day_end, dodaj automatycznie free_time z sensowną etykietą: 'kolacja / spacer / zakupy'"

### Solution Strategy:

**1. Gap Detection:**
```python
def detect_time_gaps(timeline):
    gaps = []
    for i in range(len(timeline) - 1):
        current_end = timeline[i].end_time
        next_start = timeline[i + 1].start_time
        gap_duration = (next_start - current_end).total_seconds() / 60
        
        if gap_duration > 60:  # Gap > 1 hour
            gaps.append({
                "start": current_end,
                "end": next_start,
                "duration": gap_duration
            })
    return gaps
```

**2. Gap Filling Rules:**

| Gap Duration | Action | Example |
|--------------|--------|---------|
| 60-90 min | Add short POI (30-45min) OR coffee break | "Coffee & dessert at local cafe" |
| 90-150 min | Add medium POI (60-90min) OR shopping/walk | "Shopping on Krupówki" OR "Scenic walk" |
| 150+ min | Add full attraction OR structured free_time | "Thermal bath visit" OR "Dinner & evening leisure" |

**3. End-of-Day Handling:**

```python
def fill_end_of_day_gap(last_item_end, day_end):
    gap = (day_end - last_item_end).total_seconds() / 60
    
    if gap > 60:
        # Add structured free_time
        return {
            "type": "free_time",
            "start_time": last_item_end,
            "end_time": day_end,
            "duration_min": int(gap),
            "label": "Dinner and evening leisure",
            "description": "Time for dinner, relaxation, or exploring local area"
        }
    return None
```

**4. Context-Aware Gap Filling:**

```python
def suggest_gap_filler(gap_duration, time_of_day, user_profile):
    """Smart gap filling based on context"""
    
    if time_of_day >= "17:00":  # Evening
        return "Dinner preparation / Evening walk"
    
    elif user_profile.group.type == "family_kids":
        if gap_duration < 90:
            return "Playground visit / Ice cream break"
        else:
            return find_short_kids_attraction()
    
    elif user_profile.travel_style == "relax":
        if gap_duration < 90:
            return "Coffee & cake at mountain cafe"
        else:
            return find_relaxation_activity()  # spa, easy walk
    
    elif user_profile.travel_style == "adventure":
        return find_active_short_activity()  # short hike, bike rental
    
    else:
        return "Free time for shopping or local exploration"
```

### Files to Modify:

1. `app/domain/planner/engine.py`
   - Add: `detect_time_gaps(timeline)` function
   - Add: `fill_gap_with_poi(gap, user)` function
   - Add: `fill_gap_with_free_time(gap, context)` function
   - Integrate: Call gap filling BEFORE returning day plan

2. `app/domain/planner/quality_checker.py`
   - Add validation: Max gap allowed = 90 min (configurable)

### Testing:

**Unit Tests:**
```python
def test_gap_detection():
    """Detect gaps > 60 min"""
    timeline = [
        {"end_time": "15:41"},  # Termy
        {"start_time": "18:39"}  # Dinner
    ]
    gaps = detect_time_gaps(timeline)
    assert len(gaps) == 1
    assert gaps[0].duration == 178  # 2h 58min

def test_gap_filling_end_of_day():
    """Fill gap between last attraction and day_end"""
    last_item_end = datetime.strptime("15:29", "%H:%M")
    day_end = datetime.strptime("18:00", "%H:%M")
    
    filler = fill_end_of_day_gap(last_item_end, day_end)
    
    assert filler is not None
    assert filler["type"] == "free_time"
    assert "Dinner" in filler["label"]
```

**Integration Test:**
Re-run Test 01, 05, 06 → validate no gaps > 90 min.

### Estimated Effort: **6-8 hours**
- Gap detection implementation: 2h
- Gap filling strategies (POI + free_time): 3-4h
- Testing: 2h

---

## 🟡 HIGH PRIORITY ISSUE #4: why_selected PUSTE LUB GENERYCZNE

### Problem Description:

`why_selected` field ma **puste arrays []** lub **generyczne frazy** ("Quiet, peaceful destination") które nie odnoszą się do user preferences lub są nieprawdziwe dla danego POI.

### Frequency: **7/10 tests (70%)**

### Examples:

**Test 03: Empty why_selected**
```json
{"poi_name": "Oksza", "why_selected": []},  // ❌ EMPTY
{"poi_name": "Kaplica", "why_selected": []},  // ❌ EMPTY
{"poi_name": "Termy Gorący Potok", "why_selected": []},  // ❌ EMPTY
{"poi_name": "Termy Bukovina", "why_selected": []}  // ❌ EMPTY
```

**Test 05: Generic, Not Matching Preferences**
```json
{
  "preferences": ["kids_attractions", "relaxation"],
  "poi": "Wielka Krokiew",
  "why_selected": ["Must-see", "Low-crowd"]  // ❌ No mention of kids/relaxation
}
```

**Test 07: Wrong Profile Match**
```json
{
  "group": "friends",
  "travel_style": "adventure",
  "crowd_tolerance": 2,
  "poi": "Wielka Krokiew",
  "why_selected": ["Quiet, peaceful destination"]  // ❌ Contradicts profile!
}
```

**Test 08: Faktycznie Nieprawdziwe**
```json
{
  "poi": "Morskie Oko",
  "why_selected": ["Quiet, peaceful destination"]  // ❌ Morskie Oko to najpopularniejsze miejsce w Tatrach!
}
```

### Client Requirements:

**From Test 05:**
> "W preferences = kids_attractions + relaxation, a w why_selected nigdzie nie ma 'Matches your kids_attractions' albo 'Matches your relaxation'"

**From Test 06:**
> "W preferences = museum_heritage, nature_landscape, relaxation powinno być w why_selected:
> - 'Matches your museum_heritage preference'
> - 'Matches your nature_landscape preference'
> - 'Matches your relaxation preference'
> A tu głównie 'Must-see' i 'Low-crowd'."

**From Test 07:**
> "Może warto generować why_selected z mapowania?
> - crowd_tolerance=2 → 'moderate crowd ok'
> - travel_style=adventure → 'active / dynamic / experience-driven'
> - group friends → 'good for group / fun factor / shared experience'"

### Solution (Refinement 2.0):

**Problem #7 refinement (commit aac61c2)** dodał scoring signal functions, ale wciąż są gaps. Need:

**1. Eliminate Empty why_selected:**
```python
def explain_poi_selection(poi, user):
    reasons = []
    
    # Priority 1: Must-see
    if poi.priority_level == 12:
        reasons.append("Must-see attraction in Zakopane")
    
    # Priority 2: Preference match
    pref_reason = _explain_preference_match(poi, user)
    if pref_reason:
        reasons.append(pref_reason)
    
    # Priority 3: Crowd fit
    crowd_reason = _explain_crowd_fit(poi, user)
    if crowd_reason:
        reasons.append(crowd_reason)
    
    # Priority 4: Budget fit
    budget_reason = _explain_budget_fit(poi, user)
    if budget_reason:
        reasons.append(budget_reason)
    
    # Priority 5: Travel style
    style_reason = _explain_travel_style_match(poi, user)
    if style_reason:
        reasons.append(style_reason)
    
    # FALLBACK: Ensure at least 1 reason
    if len(reasons) == 0:
        reasons.append("Fits your travel plan timing and location")
    
    return reasons[:3]  # Top 3
```

**2. Stop Spamming "Quiet, peaceful":**

Current `_explain_travel_style_match()` prawdopodobnie ma hardcoded text. Fix:

```python
def _explain_travel_style_match(poi, user):
    """Generate reason based on travel_style + POI tags"""
    
    if user.travel_style == "relax":
        if "relaxation" in poi.tags or "spa" in poi.tags:
            return "Relaxing experience (matches your style)"
        # DON'T say "peaceful" for every POI
    
    elif user.travel_style == "adventure":
        if "active_sport" in poi.tags or "mountain_trails" in poi.tags:
            return "Active adventure (matches your style)"
    
    elif user.travel_style == "cultural":
        if "museum_heritage" in poi.tags or "history" in poi.tags:
            return "Cultural experience (matches your style)"
    
    # DON'T return generic phrase if no match
    return None
```

**3. Add Preference Text Mapping:**

```python
PREFERENCE_DISPLAY_NAMES = {
    "kids_attractions": "kids' attractions",
    "nature_landscape": "nature & landscape",
    "museum_heritage": "museums & heritage",
    "relaxation": "relaxation",
    "water_attractions": "water attractions",
    "history_mystery": "history & mystery",
    "active_sport": "active sports",
    "mountain_trails": "mountain trails",
    "local_food_experience": "local food experiences",
    "underground": "underground attractions"
}

def _explain_preference_match(poi, user):
    """Match POI tags to user preferences"""
    for pref in user.preferences[:3]:  # Top 3 preferences
        # Check if POI has matching tag
        if pref in poi.tags:
            pref_name = PREFERENCE_DISPLAY_NAMES.get(pref, pref)
            return f"Matches your {pref_name} preference"
    
    return None  # No match
```

**4. Add Profile-Based Reasons:**

```python
def _explain_group_fit(poi, user):
    """Generate reason based on group type"""
    
    if user.group.type == "friends" and user.travel_style == "adventure":
        if "active_sport" in poi.tags or "fun" in poi.tags:
            return "Great for group adventures"
    
    elif user.group.type == "family_kids":
        if "kids_attractions" in poi.tags:
            return "Perfect for families with children"
    
    elif user.group.type == "seniors":
        if "relaxation" in poi.tags and poi.difficulty_level <= 2:
            return "Comfortable pace for relaxed exploration"
    
    return None
```

### Files to Modify:

1. `app/domain/planner/explainability.py`
   - Function: `explain_poi_selection()` - add fallback for empty
   - Function: `_explain_travel_style_match()` - remove generic phrases
   - Function: `_explain_preference_match()` - add display name mapping
   - Function: `_explain_group_fit()` - NEW function

### Testing:

**Unit Tests:**
```python
def test_no_empty_why_selected():
    """Every POI must have at least 1 reason"""
    user = create_test_user(preferences=["museum_heritage"])
    poi = create_test_poi(tags=["random_tag"])  # No preference match
    
    reasons = explain_poi_selection(poi, user)
    
    assert len(reasons) >= 1  # Never empty
    assert reasons[0] != ""  # Not empty string

def test_preference_in_why_selected():
    """If user has preference X and POI has tag X, mention it"""
    user = create_test_user(preferences=["kids_attractions", "relaxation"])
    poi = create_test_poi(tags=["kids_attractions"])
    
    reasons = explain_poi_selection(poi, user)
    
    assert any("kids" in r.lower() for r in reasons)

def test_no_generic_for_adventure_profile():
    """Don't say 'peaceful' for adventure profile"""
    user = create_test_user(
        group_type="friends",
        travel_style="adventure",
        crowd_tolerance=2
    )
    poi = create_test_poi(crowd_level=3)
    
    reasons = explain_poi_selection(poi, user)
    
    assert not any("quiet" in r.lower() or "peaceful" in r.lower() for r in reasons)
```

**Integration Test:**
Re-run Test 03, 05, 06, 07, 08 → validate:
- 0 empty why_selected
- Preferences mentioned in why_selected
- No "peaceful" for adventure profiles

### Estimated Effort: **4-5 hours**
- Remove generic phrases: 1h
- Add preference mapping: 1h
- Add group/profile fit: 1h
- Ensure no empty: 1h
- Testing: 1h

---

## 🟡 HIGH PRIORITY ISSUE #5: PREFERENCJE IGNOROWANE

### Problem Description:

Engine wybiera POI które **nie pasują do user preferences**, zwłaszcza:
- `history_mystery` - praktycznie nie istnieje w planach
- `kids_attractions` - słabo realizowane (1-2 POI w 2-day plan)
- `relaxation` - brak term/spa mimo travel_style=relax
- `water_attractions` - akwarium jako "water na siłę"
- `active_sport + mountain_trails` - plan ma muzea zamiast hikes

### Frequency: **7/10 tests (70%)**

### Breakdown by Preference:

#### **A) history_mystery:**

**Test 04** (5 dni, preferences: nature + history_mystery + heritage):
> "W całym 5-dniowym planie jest natura OK, jest heritage OK, ale **mystery nie ma praktycznie nic**."

**Test 07** (2 dni, preferences: underground + history_mystery + heritage):
> "underground: 0 elementów (zrozumiałe, nie mamy)
> **history_mystery: praktycznie 0** (poza muzeami; za to jest Dom do góry nogami, papugarnia, mini zoo)"

**Client Suggestion:**
> "Może zróbmy regułę: jeśli w preferencjach jest underground/history_mystery, plan musi zawierać co najmniej X takich POI dziennie albo dać alternatywę."

#### **B) kids_attractions:**

**Test 05** (2 dni, family kids 3-6, preferences: kids_attractions + relaxation):
> "Kids_attractions są słabo realizowane:
> - Day 1: Rusinowa to nie kids_attractions (to natura/trail)
> - Day 2: Podwodny Świat OK, ale reszta to muzeum + Krokiew
> 
> **Jeśli preferences mają kids_attractions jako top, to plan powinien mieć przynajmniej 1 kids POI dziennie jako core.**"

#### **C) relaxation:**

**Test 05** (family, preferences: kids_attractions + relaxation, travel_style=relax):
> "preferences = kids_attractions + relaxation, a **w planie brak term / basenów / spa / strefy relaksu** w oba dni.
> I jeszcze travel_style=relax, a Day 2 to 'zaliczanie' (Krokiew + akwarium + muzeum)."

**Test 06** (seniors, preferences: heritage + relaxation + nature, travel_style=relax):
> "Brak realizacji preferencji 'relaxation' (mimo travel_style=relax)
> **W całym planie nie ma żadnej atrakcji/segmentu, który realnie wspiera relaxation: brak term / spa / łaźni / spokojnej strefy relaksu**"

**Test 09** (solo, preferences: nature + relaxation, travel_style=relax):
> "Dzień 1 to 'miasto + muzea + zoo + papugarnia'. To jest bardziej family / sightseeing niż **relax + nature**."

#### **D) water_attractions:**

**Test 10** (couples, preferences: water_attractions + relaxation + food, budget=1):
> "water_attractions: **Podwodny Świat (akwarium) to woda 'na siłę'**, ale to nie jest relaksująca atrakcja wodna w Zakopanem."
> 
> "Idealny szkielet dnia to:
> 1. **1 główna atrakcja wodna (termy)**
> 2. 1 spokojny spacer widokowy
> 3. 1 mocny punkt jedzeniowy
> 4. **mało muzeów**"

#### **E) active_sport + mountain_trails:**

**Test 03** (friends, preferences: active_sport + mountain_trails + history_mystery, travel_style=adventure):
> "Plan nie realizuje 'active_sport' i 'mountain_trails' w Day 1
> Day 1 to: Krokiew + muzeum + galeria + kaplica + termy. To jest **miks 'must-see + kultura + relaks', a nie 'friends + adventure + active_sport + mountain_trails'**."

---

### Root Cause Analysis:

**1. Scoring Weights Issue:**
- `priority_level=12` (must-see) overrides preferences
- Preference match gives tylko +5-8 points, ale must-see daje +20-30
- Result: Must-see POI (muzea, Krokiew) dominują plan

**2. POI Repository Gaps:**
- Może brakuje POI z tagami: `relaxation`, `history_mystery`, `water_attractions` (poza akwarium)?
- Need audit: Ile mamy POI per tag?

**3. travel_style Not Used:**
- `travel_style=relax` powinien drastycznie zwiększać weight dla: termy, spa, easy trails, free_time
- `travel_style=adventure` powinien zwiększać weight dla: active_sport, mountain_trails, long hikes
- Currently: travel_style ma minimalny wpływ na scoring

**4. No Minimum Coverage Rule:**
- Brak validation: "Top 3 preferences muszą mieć ≥1 POI dziennie"

---

### Solution:

**1. Increase Preference Weights:**

```python
def calculate_preference_score(poi, user):
    score = 0
    
    for pref in user.preferences[:3]:  # Top 3 preferences
        if pref in poi.tags:
            score += 20  # ✅ Increased from 5 to 20 (same as must-see)
    
    for pref in user.preferences[3:]:  # Other preferences
        if pref in poi.tags:
            score += 10  # ✅ Increased from 3 to 10
    
    return score
```

**2. Add travel_style Multipliers:**

```python
def apply_travel_style_modifier(score, poi, user):
    """Boost or penalize based on travel_style"""
    
    if user.travel_style == "relax":
        if "relaxation" in poi.tags or "spa" in poi.tags or "termy" in poi.tags:
            score *= 1.8  # 80% boost
        if "active_sport" in poi.tags:
            score *= 0.4  # 60% penalty
    
    elif user.travel_style == "adventure":
        if "active_sport" in poi.tags or "mountain_trails" in poi.tags:
            score *= 1.8  # 80% boost
        if "museum_heritage" in poi.tags:
            score *= 0.6  # 40% penalty (not impossible, but lower priority)
    
    elif user.travel_style == "cultural":
        if "museum_heritage" in poi.tags or "history" in poi.tags:
            score *= 1.5  # 50% boost
    
    return score
```

**3. Add Preference Coverage Validator:**

```python
def validate_preference_coverage(day_plan, user):
    """Ensure each day has ≥1 POI matching top 3 preferences"""
    top_prefs = user.preferences[:3]
    
    for pref in top_prefs:
        matched = [poi for poi in day_plan if pref in poi.tags]
        
        if len(matched) == 0:
            logger.warning(f"Day missing preference: {pref}")
            # Try to inject a POI matching this preference
            inject_preference_poi(day_plan, pref, user)
```

**4. Audit POI Repository:**

Run analysis:
```python
def audit_poi_tags():
    poi_list = load_all_poi()
    tag_counts = {}
    
    for poi in poi_list:
        for tag in poi.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    print("POI Tag Distribution:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: x[1]):
        print(f"{tag}: {count} POI")
```

If `relaxation` has only 2 POI, that's a problem. Need to:
- Add more POI with `relaxation` tag (termy, spa, easy walks)
- OR add tag aliases (e.g., tag termy as both `water_attractions` AND `relaxation`)

**5. Special Rules:**

```python
# Rule: If kids_attractions in top 3, ensure 1+ kids POI per day
if "kids_attractions" in user.preferences[:3]:
    min_kids_poi_per_day = 1

# Rule: If relaxation + travel_style=relax, ensure 1+ termy/spa per trip
if "relaxation" in user.preferences and user.travel_style == "relax":
    ensure_at_least_one_termy(trip_plan)
```

---

### Files to Modify:

1. **`app/domain/planner/scoring.py`**
   - Increase preference weights (5 → 20 for top 3)
   - Add `apply_travel_style_modifier()` function

2. **`app/domain/planner/engine.py`**
   - Add `validate_preference_coverage()` function
   - Call validation before returning day plan

3. **`data/zakopane_poi_extended_v1.xlsx`**
   - Audit tag distribution
   - Add missing tags (e.g., tag all termy as `relaxation`)

4. **`scripts/audit_poi_repository.py`** (NEW)
   - Create tool dla POI tag analysis

---

### Testing:

**Unit Tests:**
```python
def test_preference_weight_increase():
    """Preference match should score high"""
    user = create_test_user(preferences=["kids_attractions"])
    poi_match = create_test_poi(tags=["kids_attractions"], priority=8)
    poi_must_see = create_test_poi(tags=["other"], priority=12)
    
    score_match = calculate_score(poi_match, user)
    score_must_see = calculate_score(poi_must_see, user)
    
    # Preference match should be competitive with must-see
    assert score_match >= score_must_see * 0.8

def test_travel_style_relax_boosts_termy():
    """travel_style=relax should heavily favor termy"""
    user = create_test_user(travel_style="relax")
    poi_termy = create_test_poi(tags=["relaxation", "spa"])
    poi_museum = create_test_poi(tags=["museum_heritage"])
    
    score_termy = calculate_score(poi_termy, user)
    score_museum = calculate_score(poi_museum, user)
    
    assert score_termy > score_museum * 1.5  # At least 50% higher

def test_preference_coverage_kids():
    """If kids_attractions in top 3, day must have ≥1 kids POI"""
    user = create_test_user(preferences=["kids_attractions", "nature", "relax"])
    day_plan = generate_day_plan(user)
    
    kids_poi = [poi for poi in day_plan if "kids_attractions" in poi.tags]
    assert len(kids_poi) >= 1
```

**Integration Tests:**
Re-run Test 03, 04, 05, 06, 07, 09, 10 → validate:
- Top 3 preferences jsou realized (≥1 POI per day)
- travel_style=relax → plan má termy/spa
- travel_style=adventure → plan má hikes/active POI

---

### Estimated Effort: **6-8 hours**
- POI repository audit: 2h
- Increase preference weights: 1h
- Add travel_style modifiers: 2h
- Add coverage validator: 1-2h
- Testing: 2h

---

## 🟠 MEDIUM PRIORITY ISSUE #6: CROWD_TOLERANCE IGNOROWANE

### Problem Description:

`crowd_tolerance=1` (low tolerance) is not respected. Engine wybiera **popularne miejsca** (Morskie Oko, Krupówki, Wielka Krokiew) i oznacza je jako **"Low-crowd option"**, co jest faktycznie nieprawdziwe.

### Frequency: **5/10 tests (50%)**

### Examples:

**Test 04** (solo, crowd_tolerance=1):
> "W wielu miejscach powtarza się: **'Low-crowd option (fits crowd_tolerance: 1)' dla atrakcji, które w realu potrafią być tłoczne** (Krokiew, Krupówki, Morskie Oko w sezonie)."

**Test 08** (couples, crowd_tolerance=2):
> "'Quiet, peaceful destination' to jest prawie wszędzie, nawet przy **Morskim Oku, Krupówki/atrakcje na Krupówkach** i termach"

### Root Cause:

**1. Inaccurate POI crowd_level Data:**
- Morskie Oko, Krupówki, Wielka Krokiew should have `crowd_level=3` (high)
- Currently może mają `crowd_level=1-2`?

**2. Weak Crowd Penalty:**
```python
# Current (suspected):
if user.crowd_tolerance == 1 and poi.crowd_level == 3:
    score -= 5  # Too weak penalty
```

**3. why_selected Generic Logic:**
```python
# Current (broken):
if user.crowd_tolerance == 1:
    reasons.append("Low-crowd option")  # ❌ Says this for EVERY POI
```

### Solution:

**1. Audit POI crowd_level Data:**

Review `data/zakopane_poi_extended_v1.xlsx`:
```
Morskie Oko → crowd_level = 3 (very popular)
Krupówki center → crowd_level = 3
Wielka Krokiew → crowd_level = 3 (popular landmark)
Dolina Kościeliska → crowd_level = 1-2 (quiet trail)
Rusinowa Polana → crowd_level = 1 (off-beaten path)
```

**2. Stronger Crowd Penalty:**

```python
def apply_crowd_tolerance_penalty(score, poi, user):
    """Apply strong penalty for high-crowd POI when user has low tolerance"""
    
    if user.crowd_tolerance == 1:  # Low tolerance
        if poi.crowd_level == 3:  # High crowd
            score *= 0.2  # 80% penalty (very strong)
        elif poi.crowd_level == 2:  # Medium crowd
            score *= 0.6  # 40% penalty
    
    elif user.crowd_tolerance == 2:  # Medium tolerance
        if poi.crowd_level == 3:
            score *= 0.8  # 20% penalty (slight)
    
    # crowd_tolerance=3 → no penalty
    
    return score
```

**3. Fix why_selected Logic:**

```python
def _explain_crowd_fit(poi, user):
    """Only say 'Low-crowd' if POI actually has low crowd_level"""
    
    # Only say "Low-crowd" if crowd_level is ACTUALLY low
    if user.crowd_tolerance == 1 and poi.crowd_level <= 1:
        return "Low-crowd option (fits your crowd_tolerance: 1)"
    
    # If user is OK with crowds and POI is popular, that's fine
    elif user.crowd_tolerance >= 2 and poi.crowd_level == 3:
        return "Popular attraction (fits your crowd comfort)"
    
    # DON'T say "Low-crowd" for high crowd_level POI
    return None
```

### Files to Modify:

1. **`data/zakopane_poi_extended_v1.xlsx`**
   - Review and correct `crowd_level` column
   - Popular POI → crowd_level = 3

2. **`app/domain/planner/scoring.py`**
   - Strengthen `apply_crowd_tolerance_penalty()` function

3. **`app/domain/planner/explainability.py`**
   - Fix `_explain_crowd_fit()` to check actual crowd_level

### Testing:

**Unit Test:**
```python
def test_crowd_tolerance_low_avoids_popular():
    """crowd_tolerance=1 should avoid crowd_level=3 POI"""
    user = create_test_user(crowd_tolerance=1)
    poi_popular = create_test_poi(name="Morskie Oko", crowd_level=3)
    poi_quiet = create_test_poi(name="Rusinowa", crowd_level=1)
    
    score_popular = calculate_score(poi_popular, user)
    score_quiet = calculate_score(poi_quiet, user)
    
    # Quiet POI should score much higher
    assert score_quiet > score_popular * 2

def test_no_lowcrowd_label_for_popular_poi():
    """Don't say 'Low-crowd' for Morskie Oko"""
    user = create_test_user(crowd_tolerance=1)
    poi = create_test_poi(name="Morskie Oko", crowd_level=3)
    
    reasons = explain_poi_selection(poi, user)
    
    # Should NOT contain "Low-crowd"
    assert not any("low-crowd" in r.lower() for r in reasons)
```

**Integration Test:**
Re-run Test 04, 05, 06, 08 with crowd_tolerance=1 → validate:
- No "Low-crowd" for Morskie Oko, Krupówki, Krokiew
- Plan prioritizes less popular POI

### Estimated Effort: **3-4 hours**
- POI data audit: 1h
- Fix scoring penalty: 1h
- Fix why_selected logic: 1h
- Testing: 1h

---

## 🟢 LOW PRIORITY ISSUE #7: cost_estimate COMMUNICATION

### Problem Description:

`cost_estimate` field is accurate (fixed in Problem #8), ale **brak explicit communication** czy to jest "per person" czy "total for group".

### Client Feedback (Test 03):
> "Cost_estimate wygląda jak liczony 'na grupę', ale **musimy to przekazać w komunikacji**, że cost_estimate = total for group (bo inaczej będzie zamieszanie przy UI)."

### Solution:

**Option A: Add cost_breakdown Field (Recommended):**
```json
{
  "poi_name": "Wielka Krokiew",
  "cost_estimate": 100,
  "cost_breakdown": {
    "per_person": 25,
    "group_size": 4,
    "total": 100
  }
}
```

**Option B: Add Note in Day Summary:**
```json
{
  "day_summary": {
    "total_cost_estimate": 500,
    "cost_note": "Total for your group of 4 people"
  }
}
```

**Option C: Swagger Documentation:**
Update API docs to explicitly state: "cost_estimate represents total cost for the entire group"

### Recommendation: **Option A** (most explicit, best UX)

### Files to Modify:

1. `app/domain/planner/explainability.py`
   - Add `cost_breakdown` object to POI explanation

2. `app/api/routes/plan.py`
   - Update Swagger docs

### Testing:

Manual validation: Check response includes cost_breakdown.

### Estimated Effort: **1-2 hours**

---

## 📊 SUMMARY: FIX PRIORITY & TIMELINE

### **Sprint 1: Critical Timeline Bugs (Feb 19-20)**

| Bug | Priority | Effort | Status |
|-----|----------|--------|--------|
| #1 Parking Overlap | 🔴 P0 | 4-6h | ⏳ TODO |
| #2 dinner_break duration | 🔴 P0 | 2h | ⏳ TODO |
| #3 Gap Filling | 🔴 P1 | 6-8h | ⏳ TODO |

**Total: 12-16 hours (1.5-2 days)**

**Deliverable:** Timeline integrity restored, no overlaps, no gaps >90min

---

### **Sprint 2: Explainability & Preferences (Feb 21-22)**

| Issue | Priority | Effort | Status |
|-------|----------|--------|--------|
| #4 why_selected Refinement 2.0 | 🟡 P1 | 4-5h | ⏳ TODO |
| #5 Preference Coverage | 🟡 P1 | 6-8h | ⏳ TODO |

**Total: 10-13 hours (1.5 days)**

**Deliverable:** Personalization works, preferences realized, explainability accurate

---

### **Sprint 3: Polish & Testing (Feb 23-24)**

| Issue | Priority | Effort | Status |
|-------|----------|--------|--------|
| #6 Crowd_tolerance | 🟠 P2 | 3-4h | ⏳ TODO |
| #7 cost_estimate communication | 🟢 P3 | 1-2h | ⏳ TODO |
| Comprehensive Regression Testing | - | 4-6h | ⏳ TODO |

**Total: 8-12 hours (1-1.5 days)**

**Deliverable:** All 7 issues fixed, 100% test pass rate

---

### **TOTAL EFFORT: 30-41 hours (4-5 days)**

**Timeline:**
- Start: Feb 19, 2026 (Today)
- End: Feb 23-24, 2026
- UAT Round 3: Feb 25-26, 2026
- ETAP 2 Delivery: Feb 27-28, 2026 (before March 12 deadline)

---

## 🎯 ETAP 2 STATUS UPDATE

### **Original Scope:**
✅ Multi-day planning (2-7 days)  
✅ Editing (remove + replace + regenerate)  
✅ Versioning (snapshot + rollback)  
✅ PostgreSQL migration  
✅ Quality scoring + Explainability  
✅ Client feedback bugfixes Round 1 (12 problems) - COMPLETED  

### **New Scope (UAT Round 2):**
🔄 Client feedback bugfixes Round 2 (7 issues) - IN PROGRESS

### **Out of Scope:**
❌ Problem #12 (Małopolska POI expansion) - Deferred to ETAP 3

**Client Statement:**
> "Miałam mylne wyobrażenie, myślałam że podpięcie większej bazy nie będzie wymagało dodatkowe pracy. **Nie chcę Ci oczywiście dokładać tego co nie było przewidziane w naszej umowie.**"

**Interpretation:** Klientka rozumie że Małopolska expansion to nowy projekt, nie ETAP 2. Nie chce dokładać pracy poza umową.

### **Recommendation:**
- **Focus ETAP 2:** Fix 7 issues from UAT Round 2
- **Deliver Clean System:** Bug-free Zakopane planning system
- **Propose ETAP 3:** Małopolska expansion + other features (reorder, visual diff, Stripe, PDF, email)

---

## 📝 NEXT STEPS

### **Immediate Actions (Today, Feb 19):**

1. **Update Todo List:**
   - [ ] Bug #1: Fix parking overlap
   - [ ] Bug #2: Fix dinner_break duration
   - [ ] Bug #3: Implement gap filling
   - [ ] Issue #4: why_selected refinement 2.0
   - [ ] Issue #5: Preference coverage enforcement
   - [ ] Issue #6: Crowd_tolerance accuracy
   - [ ] Issue #7: cost_estimate communication

2. **Create Test Files:**
   - `test_parking_overlap_fix.py` (Bug #1 validation)
   - `test_dinner_duration_fix.py` (Bug #2 validation)
   - `test_gap_filling.py` (Bug #3 validation)
   - Update `test_uatproblem7_refinement.py` for Issue #4

3. **Start Sprint 1:**
   - Begin with Bug #1 (parking overlap) - highest frequency (90%)
   - Root cause investigation in `engine.py`
   - Implement fix + timeline validator
   - Run comprehensive tests

4. **Communication with Client:**
   - Confirm understanding: Małopolska = out of scope for ETAP 2
   - Set expectations: 7 issues will be fixed by Feb 23-24
   - Propose UAT Round 3: Feb 25-26

---

## 📎 FILES CREATED

1. **CLIENT_FEEDBACK_19_02_2026_UAT_ROUND2.md** (This document)
   - Complete analysis of 10 test scenarios
   - 7 issues documented with examples, root cause, solutions
   - Priority matrix, fix order, timeline estimates

2. **ANALIZA_UAT_ROUND2_RAPORT_PELNY.md** (Summary for user)
   - Executive summary for planning work
   - Sprint breakdown (3 sprints, 4-5 days)
   - Next steps

---

**Document Status:** ✅ COMPLETE  
**Action Required:** Start Sprint 1 (Bug #1-3 fixes)  
**Next Review:** After Sprint 1 completion (Feb 20, 2026)

---

*Prepared by: AI Analysis System*  
*Date: February 19, 2026*  
*Client: Karolina Sobotkiewicz*  
*Project: Travel Planner Backend - ETAP 2*
