# 📋 Feedback Karoliny - Enhancement Requests (29.01.2026)

**Data:** 29.01.2026  
**Status:** ✅ Day_start fix VERIFIED | ⚠️ 2h gaps PROBLEM | 🔧 6 enhancement requests

---

## 🚨 CRITICAL ISSUE: 2-godzinne luki w planie

**Problem:**
```
"Teraz jak robiłam testy to np. mam 2-godzinną lukę w środku dnia 
i to z perspektywy produktu słaby plan."
```

**✅ EXACT TEST CASE (Received from Client):**
```json
{
  "location": "Zakopane",
  "group": {"type": "family_kids"},
  "travel_style": "adventure",
  "preferences": ["outdoor"],
  "daily_time_window": {"start": "09:00", "end": "19:00"},
  "transport": ["car"]
}
```

**Observed Gap:**
- **14:48** Tatra Family (activity ends)
- **16:53** Góralski Ślizg (next activity starts)
- **Gap:** 2h 5min ❌

**Oczekiwanie klientki:**
- ❌ NIE: 2h pusta luka
- ✅ TAK: Regeneracja 10-15 min LUB mniejsze przerwy
- ✅ FALLBACK: Jeśli brak POI → free time max 40 min, NIE 2h

**Root Cause (hypothesis):**
- Engine nie znajduje POI pasujących do scoringu w oknie 14:48-16:53
- Góralski Ślizg może otwierać się dopiero o 16:53 (opening hours)
- Zostawia pustą lukę zamiast trybu fallback
- Body state recovery może być za agresywny

**Action Required:**
1. ✅ Test case confirmed - reproduce with exact parameters
2. Investigate: 
   - Check opening_hours for all POI (especially Góralski Ślizg)
   - Check scoring for POI in 14:48-16:53 window
   - Is threshold too high? Is body_state blocking matches?
3. Implement fallback mechanism:
   - Jeśli brak high-scoring POI → lower threshold (50%)
   - Jeśli dalej brak → "free time / spacer / kawa" max 40 min
   - Never leave 2h gap

**Priority:** 🔴 CRITICAL (product quality issue)

---

## ✅ APPROVED: Indoor/Outdoor Enhancement

**Feedback:** "Jest jak najbardziej ok :)"

**Action:** Implement space (indoor/outdoor) scoring module (OPCJA B)

---

## 🔧 Enhancement Request #1: recommended_time_of_day Scoring

**Problem:**
```
"Silnik obecnie układa atrakcje losowo w czasie, nawet jeśli atrakcja 
jest typowo poranna albo wieczorna"
```

**Data Available:**
- `POI.recommended_time_of_day`: morning / midday / afternoon / evening

**Proposal:**
```python
if current_time_of_day in poi.recommended_time_of_day:
    score += X  # bonus points
else:
    score -= X  # penalty for wrong time
```

**Implementation:**
- Create `time_of_day_scoring.py` module
- Map current time → time_of_day category
- Apply bonus/penalty based on match
- Integrate with main scoring pipeline

**Effort:** ~2-3h
**Priority:** 🟡 MEDIUM (UX improvement)

---

## 🔧 Enhancement Request #2: peak_hours Consideration

**Problem:**
```
"Fajnie jakby silnik brał to pod uwagę"
```

**Data Available:**
- `POI.peak_hours`: godziny szczytu
- `user.crowd_tolerance`: 0-3

**Proposal:**
```python
if current_time in poi.peak_hours and user.crowd_tolerance >= 3:
    score -= penalty  # avoid peak if user dislikes crowds
```

**Implementation:**
- Extend `crowd_scoring.py` module
- Check current_time against peak_hours
- Apply penalty based on crowd_tolerance
- Consider: bonus for low crowd_tolerance users at off-peak

**Effort:** ~1-2h
**Priority:** 🟡 MEDIUM (UX improvement)

---

## 🔧 Enhancement Request #3: weather_dependency Scoring

**Problem:**
```
"weather_dependency = high + zła pogoda → mocna kara
weather_dependency = low → bonus przy złej pogodzie"
```

**Data Available:**
- `POI.weather_dependency`: high / medium / low
- `context.weather`: condition, precip, temp

**Proposal:**
```python
if weather.precip == True:  # bad weather
    if poi.weather_dependency == "high":
        score -= high_penalty  # outdoor activity in rain
    elif poi.weather_dependency == "low":
        score += bonus  # indoor activity - good choice
```

**Implementation:**
- Create `weather_scoring.py` module
- Map weather.precip → bad_weather flag
- Apply penalties/bonuses based on dependency level
- Consider temperature extremes too

**Effort:** ~2-3h
**Priority:** 🟢 HIGH (data-driven, clear UX benefit)

---

## 🔧 Enhancement Request #4: seasonality Filtering

**✅ DECISION CONFIRMED: Hard Filter**

**Problem:**
```
"jeśli current season ∉ seasonality → twardy filtr albo duża kara"
```

**Client Decision:**
```
"Hard filter (czyli POI jest całkowicie pominięty jeśli nie sezon)"
```

**Data Available:**
- `POI.seasonality`: list of seasons (e.g., ["summer", "winter"])
- `context.date`: current date → derive season

**Implementation:**
```python
def derive_season(date: datetime) -> str:
    month = date.month
    if 3 <= month <= 5:
        return "spring"
    elif 6 <= month <= 8:
        return "summer"
    elif 9 <= month <= 11:
        return "fall"
    else:
        return "winter"

# In POI filtering stage (BEFORE scoring):
current_season = derive_season(context.date)

if poi.seasonality and current_season not in poi.seasonality:
    # Hard filter - exclude POI completely
    continue  # Skip this POI
```

**Placement:**
- Apply in `plan_service.py` BEFORE scoring
- Filter out POI early (don't waste scoring computation)

**Effort:** ~1-2h
**Priority:** 🟡 MEDIUM (data utilization)

---

## 🔧 Enhancement Request #5: type + travel_style/group Matching

**Problem:**
```
"Brakuje powiązania z travel_style, group_type, intensity
Np.: seniors + park rozrywki → kara
     family_kids + muzeum bez kids_only → neutral / lekka kara"
```

**Data Available:**
- `POI.type`: attraction type
- `user.group.type`: solo, couples, friends, family_kids, seniors
- `user.travel_style`: cultural, adventure, relax, balanced

**Proposal - Simple Mapping:**
```python
BONUS_MATRIX = {
    "family_kids": {
        "park_rozrywki": +10,
        "zoo": +10,
        "interactive_museum": +5
    },
    "seniors": {
        "intensive_activity": -10,
        "park_rozrywki": -5,
        "cultural": +5
    },
    "couples": {
        "cultural": +5,
        "relax": +5,
        "romantic": +10
    }
}

score += BONUS_MATRIX.get(user.group.type, {}).get(poi.type, 0)
```

**Implementation:**
- Create `type_matching_scoring.py` module
- Define bonus/penalty matrix (tunable)
- Integrate with family_fit scoring (extend existing)
- Consider: intensity field from POI

**Effort:** ~3-4h
**Priority:** 🟢 HIGH (critical for family_kids/seniors UX)

---

## 🔧 Enhancement Request #6: budget_type Perception

**✅ DECISION CONFIRMED: Premium Categories with Multipliers**

**Problem:**
```
"Obecnie silnik patrzy chyba tylko na ticket price, 
a brakuje logiki budget perception"
```

**Client Examples:**
```
"Termy/aquapark/SPA: 1.3x
Parki rozrywki/kolejki (np. Dzikie Wąwozy): 1.4x  
Extreme/premium activities: 1.5x
Można też użyć poi.activity_style, poi.budget_type jeśli są dostępne."
```

**Current State:**
- `budget_scoring.py` uses `poi.ticket_price`
- Compares with `user.budget.total_budget`

**Implementation:**
```python
# Budget perception multipliers by activity characteristics
PERCEPTION_MULTIPLIERS = {
    # Based on POI type
    "type": {
        "termy": 1.3,
        "aquapark": 1.3,
        "spa": 1.3,
        "park_rozrywki": 1.4,
        "kolejka": 1.4,
        "extreme": 1.5
    },
    # Based on activity_style field
    "activity_style": {
        "premium": 1.5,
        "luxury": 1.6,
        "extreme": 1.5
    },
    # Based on budget_type field
    "budget_type": {
        "premium": 1.3,
        "expensive": 1.4
    }
}

# Apply multiplier based on available POI fields
def calculate_perceived_cost(poi):
    base_price = poi.ticket_price
    multiplier = 1.0
    
    # Check type
    if poi.type in PERCEPTION_MULTIPLIERS["type"]:
        multiplier = max(multiplier, PERCEPTION_MULTIPLIERS["type"][poi.type])
    
    # Check activity_style
    if hasattr(poi, 'activity_style') and poi.activity_style in PERCEPTION_MULTIPLIERS["activity_style"]:
        multiplier = max(multiplier, PERCEPTION_MULTIPLIERS["activity_style"][poi.activity_style])
    
    # Check budget_type
    if hasattr(poi, 'budget_type') and poi.budget_type in PERCEPTION_MULTIPLIERS["budget_type"]:
        multiplier = max(multiplier, PERCEPTION_MULTIPLIERS["budget_type"][poi.budget_type])
    
    return base_price * multiplier

# Use in budget_scoring.py
perceived_cost = calculate_perceived_cost(poi)
# Compare with user.budget instead of raw ticket_price
```

**Effort:** ~2h
**Priority:** 🟡 MEDIUM (nice-to-have refinement)

---

## 📌 Enhancement Request #7: pro_tip Display

**Problem:**
```
"jeśli POI jest wybrane → pro_tip do UI"
```

**Current State:**
- `POI.pro_tip` field exists in data
- NOT passed to frontend in PlanResponse

**Fix Required:**
- Update `PlanResponse` model - add `pro_tip` field to Activity
- Ensure `pro_tip` is included when POI is scheduled
- Frontend can display as tooltip/card

**Implementation:**
- Modify `app/domain/models/plan.py` - Activity model
- Ensure engine passes `pro_tip` when creating activity
- Test: verify pro_tip in API response

**Effort:** ~1h
**Priority:** 🟢 HIGH (easy win, data already exists)

---

## 📊 Summary & Prioritization

| Request | Effort | Priority | Impact |
|---------|--------|----------|--------|
| **2h gaps FIX** | 4-6h | 🔴 CRITICAL | Product quality |
| **pro_tip display** | 1h | 🟢 HIGH | Easy win |
| **weather_dependency** | 2-3h | 🟢 HIGH | Data-driven UX |
| **type matching** | 3-4h | 🟢 HIGH | Family/seniors UX |
| **indoor/outdoor** | 1.5h | ✅ APPROVED | Balanced feature |
| **time_of_day** | 2-3h | 🟡 MEDIUM | UX improvement |
| **peak_hours** | 1-2h | 🟡 MEDIUM | Crowd optimization |
| **seasonality** | 1-2h | 🟡 MEDIUM | Data utilization |
| **budget perception** | 2h | 🟡 MEDIUM | Refinement |

**Total Effort:** ~17-26 hours

---

## 🎯 Recommended Approach

### Phase 1: CRITICAL (4-6h)
1. **Investigate 2h gaps** - reproduce issue, find root cause
2. **Implement fallback mechanism** - never leave >40 min gaps
3. **Test & verify** - ensure no more 2h empty periods

### Phase 2: Quick Wins (2-3h)
1. **pro_tip display** - 1h, easy frontend value
2. **indoor/outdoor scoring** - 1.5h, already approved

### Phase 3: High-Value Enhancements (8-10h)
1. **weather_dependency** - 2-3h, clear UX benefit
2. **type + group matching** - 3-4h, critical for families/seniors
3. **time_of_day scoring** - 2-3h, natural planning

### Phase 4: Polish (4-6h)
1. **peak_hours** - 1-2h
2. **seasonality** - 1-2h
3. **budget perception** - 2h

---

## ❓ Questions for User

1. **Priorytet:** Czy robimy wszystko teraz (17-26h) czy etapami?
2. **2h gaps:** Czy masz przykładowy test case gdzie to się dzieje? (user inputs + expected vs actual)
3. **Seasonality:** Hard filter czy penalty? (exclude vs deprioritize)
4. **Budget:** Ile czasu na total effort? (deadline considerations)

---

## 📧 Draft Response dla Klientki

```
Cześć Karolino,

Super że day_start działa! ✅

Odnośnie 2h luk - to jest faktycznie problem. Przeanalizuję 
dlaczego engine zostawia tak długie gaps i zaimplementuję:
1. Fallback mechanism (lower scoring threshold)
2. Free time max 40 min (jak sugerowałaś)
3. Nigdy nie zostawiać >2h pustego czasu

Wszystkie 6 enhancement requests są jak najbardziej sensowne:
✅ Pro_tip - 1h (easy win)
✅ Weather_dependency - 2-3h (high value)
✅ Type matching - 3-4h (critical dla families/seniors)
✅ Time_of_day - 2-3h
✅ Peak_hours - 1-2h
✅ Seasonality - 1-2h
✅ Budget perception - 2h

Indoor/outdoor robimy zgodnie z wcześniejszą propozycją.

Total effort: ~17-26h

Proponuję podejście etapowe:
1. Fix 2h gaps (CRITICAL) - 4-6h
2. Quick wins (pro_tip, indoor/outdoor) - 2-3h
3. High-value enhancements - 8-10h
4. Polish - 4-6h

Daj znać jak widzisz priorytet i timeline!

Pozdrawiam,
Mateusz
```
