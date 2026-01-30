# 🎯 ODPOWIEDZI KLIENTKI - Test Case & Decisions (29.01.2026)

**Data:** 29.01.2026 wieczór  
**Status:** ✅ Wszystkie odpowiedzi otrzymane  
**Next Step:** Implementacja rozpoczyna się

---

## 🔴 CRITICAL: 2h Gaps - Exact Test Case

**Input Parameters:**
```json
{
  "location": "Zakopane",
  "group": {
    "type": "family_kids"
  },
  "travel_style": "adventure",
  "preferences": ["outdoor"],
  "daily_time_window": {
    "start": "09:00",
    "end": "19:00"
  },
  "transport": ["car"]
}
```

**Observed Problem:**
```
14:48: "Tatra Family" ENDS
       ↓
      ~2H GAP (~125 min)
       ↓
16:53: "Góralski Ślizg" STARTS
```

**Analysis:**
- Gap: 14:48 → 16:53 = **2 godziny 5 minut**
- User preferences: adventure + outdoor + family_kids
- Both POI fit profile (Tatra Family, Góralski Ślizg)
- Time window: 09:00-19:00 (plenty of time available)

**Root Cause Hypothesis:**
1. **Scoring eliminuje wszystkie POI między 14:48-16:53**
   - Możliwe: body_state recovery too aggressive
   - Możliwe: crowd/budget/preferences scoring too restrictive
   
2. **Opening hours constraint**
   - Góralski Ślizg może otwierać się dopiero o 16:53?
   - Jeśli tak, to brak fallback dla 14:48-16:53 window

3. **Brak fallback mechanism**
   - Engine nie próbuje lower threshold
   - Engine nie dodaje "free time" activity

**Action Plan:**
1. Reproduce locally z exact inputs
2. Debug scoring dla POI w window 14:48-16:53
3. Check opening_hours dla wszystkich Zakopane POI
4. Implement fallback mechanism:
   - Try lower scoring threshold
   - Add "free time" (max 40 min) jeśli brak POI
   - Never leave >40 min without activity

**Priority:** 🔴 CRITICAL  
**Effort:** 4-6h  
**Status:** ⏳ Ready to implement

---

## ✅ DECISION: Seasonality = Hard Filter

**Question:** Hard filter vs penalty?

**Answer:** **Hard filter (exclude completely)**

**Implementation:**
```python
# seasonality_filter.py
def filter_by_season(pois, current_date):
    """
    Hard filter: exclude POI jeśli poza sezonem.
    """
    current_season = derive_season(current_date)  # winter, spring, summer, fall
    
    filtered = []
    for poi in pois:
        if poi.seasonality:  # If seasonality defined
            if current_season not in poi.seasonality:
                continue  # EXCLUDE - hard filter
        
        filtered.append(poi)
    
    return filtered
```

**Usage:**
- Apply BEFORE scoring (early filter)
- Example: Aquapark (seasonality: ["summer"]) → excluded in winter
- Reduces computation (no scoring dla out-of-season POI)

**Priority:** 🟡 MEDIUM  
**Effort:** 1-2h  
**Status:** ✅ Decision confirmed

---

## ✅ DECISION: Budget Perception Examples

**Question:** Które typy POI "feel expensive"?

**Answer - Premium Categories:**

### 1. Wellness & Relax
```python
"Termy / aquaparki / SPA"
→ perception_multiplier = 1.3
```

### 2. Adventure & Activities
```python
"Parki rozrywki"
"Kolejki linowe"
"Aktywności eventowe / ekstremalne"
  - pontony
  - skutery
  - snowmobile
  - kuligi z dodatkami
→ perception_multiplier = 1.4
```

### 3. Based on POI Fields
```python
if poi.activity_style in ["extreme", "premium"]:
    perception_multiplier = 1.5

if poi.budget_type == "premium":
    perception_multiplier = 1.5
```

**Implementation:**
```python
# budget_perception.py
PERCEPTION_BY_TYPE = {
    "termy": 1.3,
    "aquapark": 1.3,
    "spa": 1.3,
    "park_rozrywki": 1.4,
    "kolejka_linowa": 1.4,
    "water_sports": 1.4,
    "winter_sports": 1.4,
    "extreme_activity": 1.5
}

PERCEPTION_BY_STYLE = {
    "extreme": 1.5,
    "premium": 1.5
}

def get_perceived_cost(poi):
    base_cost = poi.ticket_price or 0
    
    # Check type
    multiplier = PERCEPTION_BY_TYPE.get(poi.type, 1.0)
    
    # Check activity_style
    if poi.activity_style in PERCEPTION_BY_STYLE:
        multiplier = max(multiplier, PERCEPTION_BY_STYLE[poi.activity_style])
    
    # Check budget_type
    if poi.budget_type == "premium":
        multiplier = max(multiplier, 1.5)
    
    return base_cost * multiplier
```

**Usage in budget_scoring.py:**
```python
# OLD:
cost = poi.ticket_price

# NEW:
cost = get_perceived_cost(poi)
```

**Priority:** 🟡 MEDIUM  
**Effort:** 2h  
**Status:** ✅ Examples confirmed

---

## 📊 Updated Implementation Plan

### Phase 1: CRITICAL (4-6h) - START ASAP
1. **Reproduce 2h gap** - exact test case
2. **Debug scoring** - why no POI between 14:48-16:53
3. **Implement fallback** - lower threshold + max 40 min free time
4. **Test & verify** - with klientka's input

### Phase 2: Quick Wins (2-3h)
1. **pro_tip display** - 1h (easy win)
2. **indoor/outdoor scoring** - 1.5h (approved)

### Phase 3: High-Value (8-10h)
1. **weather_dependency** - 2-3h
2. **type + group matching** - 3-4h
3. **time_of_day scoring** - 2-3h

### Phase 4: Polish (4-6h)
1. **seasonality hard filter** - 1-2h (decision: hard filter ✅)
2. **peak_hours** - 1-2h
3. **budget perception** - 2h (examples provided ✅)

**Total Effort:** ~18-25h  
**All decisions confirmed** ✅

---

## 🎯 Immediate Action Items

**NOW:**
1. ✅ Zanotować odpowiedzi klientki (DONE)
2. 🔄 Create test case file dla 2h gap reproduction
3. 🔄 Start debugging 2h gap issue
4. 🔄 Implement fallback mechanism

**NEXT:**
- Quick wins (pro_tip, indoor/outdoor)
- High-value enhancements
- Polish features

---

## 📧 Confirmation Email Draft

```
Cześć Karolino,

Dzięki za odpowiedzi! ✅

Mam wszystko co potrzebne:

1. ✅ Test case dla 2h gap - będę debugować 
   (Tatra Family 14:48 → Góralski Ślizg 16:53)

2. ✅ Seasonality = hard filter (exclude POI poza sezonem)

3. ✅ Budget perception examples - świetnie!

Zaczynam od CRITICAL issue (2h gaps), potem quick wins 
(pro_tip, indoor/outdoor), a następnie high-value enhancements.

Timeline: ~18-25h total, będę informował o postępach.

Daj znać jeśli masz pytania!

Pozdrawiam,
Mateusz
```
