# 🔍 ANALIZA FEEDBACKU KLIENTKI - 02.02.2026

## 📋 LISTA PROBLEMÓW

### ✅ PROBLEM #1: Błędny parking_walk_time_min
**Opis:**
- W POI (Excel): `parking_walk_time_min = 1`
- W planie JSON: `"walk_time_min": 5`

**Lokalizacja:**
```python
# app/application/services/plan_service.py
# Line 235:
walk_time = first_attraction.get("poi", {}).get("parking_walk_time_min", 5)

# Line 366:
walk_time = poi_dict.get("parking_walk_time_min", 5)
```

**Root Cause:**
- DEFAULT VALUE = 5 gdy brak danych
- Ale dane ISTNIEJĄ w POI (= 1), więc powinno brać 1, nie 5

**Impact:** MEDIUM - niepoprawne czasy, zwiększa duration niepotrzebnie

---

### ✅ PROBLEM #2: Niepotrzebny free_time przed otwarciem atrakcji
**Opis:**
```
09:46 -> 09:56 transit (10 min)
09:56 -> 10:22 FREE_TIME (26 min) ❌ NIEPOTRZEBNE
10:22 -> atrakcja (otwarta od 10:00)
```

**Root Cause:**
- Gap filling nie sprawdza godzin otwarcia POI
- Wstawia free_time zamiast wcześniej zacząć atrakcję o 10:00

**Impact:** HIGH - marnowany czas, nieprofesjonalny plan

---

### ✅ PROBLEM #3: Błędne nazwy w Transit "to"
**Opis:**
```json
{
  "type": "transit",
  "from": "Podwodny Świat",
  "to": "DINO PARK"  ❌ BŁĄD
},
{
  "type": "attraction",
  "name": "Dom do góry nogami"  ← faktyczna następna atrakcja
}
```

**Root Cause:**
- Transit item generowany PRZED wstawieniem POI przez gap filling
- `to_name` wskazuje na planned destination, ale gap filling wstawia POI przed nią
- Kolejność:
  1. Engine generuje plan: [Transit to DINO, DINO Park]
  2. Gap filling wstawia: [Transit to DINO, **Dom do góry nogami**, DINO Park]
  3. Transit "to" nie jest aktualizowany!

**Lokalizacja:**
```python
# app/application/services/plan_service.py
# Line 517-519:
from_name=from_poi.name,
to_name=to_poi.name,  ← To jest poprawne PRZED gap filling, ale nie PO
```

**Impact:** CRITICAL - mylące dla użytkownika, błędna nawigacja

---

### ✅ PROBLEM #4: Błędne nazwy "from" po lunch
**Opis:**
```json
{
  "type": "attraction",
  "name": "Myszogród"  ← ostatnia przed lunchem
},
{
  "type": "lunch_break"
},
{
  "type": "transit",
  "from": "DINO PARK"  ❌ BŁĄD - powinno być "Myszogród"
}
```

**Root Cause:**
- Identyczny problem jak #3
- Transit tracking nie jest aktualizowany po gap filling

**Impact:** CRITICAL - błędna lokalizacja startowa

---

### ✅ PROBLEM #5: Kulig w środku dnia (sprzeczne z pro_tip)
**Opis:**
- Kulig zaplanowany na 15:54-16:54 (dzień)
- Pro_tip: "Najlepszy klimat kuligu jest po zmroku"

**Root Cause:**
- `recommended_time_of_day` nie ma wartości "evening/night"
- Time-of-day scoring nie premiuje atrakcji wieczornych
- Brak penalizacji dla kuligu w dzień

**Lokalizacja:**
```python
# app/domain/scoring/time_of_day_scoring.py
# Tylko: morning, midday, afternoon
# Brak: evening, night
```

**Impact:** MEDIUM - suboptymalne doświadczenie użytkownika

---

### ✅ PROBLEM #6: Brak atrakcji CORE w planie
**Opis:**
- Plan ma 0 atrakcji z `priority_level = "core"`
- `must_see_score` i `priority_level` nie wpływają realnie na scoring

**Root Cause:**
- `priority_level` jest czytany z POI ale NIE używany w scoring
- Brak boost/penalty dla core vs secondary vs optional

**Lokalizacja:**
```python
# app/domain/scoring/*.py
# Brak użycia priority_level w żadnym module scoring
```

**Impact:** HIGH - najważniejsze atrakcje pomijane

---

### ✅ PROBLEM #7: Za dużo atrakcji dziennie (brak limitu)
**Opis:**
- Plan ma 10+ atrakcji dziennie dla family_kids
- Brak hard/soft limits per group type

**Wymagania klientki:**
```
family_kids: 4-6 atrakcji (max 7)
  - 1-2 core
  - 2-3 lekkie
  - 1 długa
  - >6 = kara, >7 = hard stop

seniors: 3-5 atrakcji (max 5)
  - 1 must see
  - 2-3 spokojne
  - >5 = hard stop

solo: 5-7 atrakcji
  - 2 core
  - 3-4 secondary
  - 7 = kara, >7 możliwe przy długim dniu

couples: 5-6 atrakcji (max 6)
  - 1-2 must see
  - 2-3 klimatyczne
  - 6 = kara jakościowa

friends: 6-8 atrakcji (max 8)
  - 2 core
  - 3-4 aktywne
  - 1-2 wieczorne
  - >8 = hard stop
```

**Root Cause:**
- Brak limitu atrakcji w `build_day()`
- Engine generuje tyle, ile się zmieści w time window

**Impact:** CRITICAL - przeładowanie planu, zmęczenie użytkownika

---

### ✅ PROBLEM #8: Target group nie działa
**Opis:**
- Plan dla seniorów zawiera atrakcje bez "seniors" w `Target group`
- Filtracja/scoring nie uwzględnia target_group realnie

**Root Cause:**
- `target_group` istnieje w POI model
- `family_fit.py` sprawdza target_group TYLKO dla family_kids
- Brak scoring dla innych grup (seniors, solo, couples, friends)

**Lokalizacja:**
```python
# app/domain/scoring/family_fit.py
# Line 11:
if user.get("target_group") != "family_kids":
    return 0  ← Inne grupy dostają 0 bonus/penalty!
```

**Impact:** HIGH - niepasujące atrakcje dla grupy docelowej

---

## 🎯 PRIORYTETYZACJA

| Problem | Priorytet | Complexity | Impact | Risk |
|---------|-----------|------------|--------|------|
| **#7 Limity atrakcji** | 🔥 CRITICAL | HIGH | CRITICAL | LOW |
| **#6 Priority_level** | 🔥 CRITICAL | MEDIUM | HIGH | LOW |
| **#3/#4 Transit names** | 🔥 CRITICAL | MEDIUM | CRITICAL | MEDIUM |
| **#8 Target group** | ⚠️ HIGH | MEDIUM | HIGH | LOW |
| **#2 Free_time before open** | ⚠️ HIGH | LOW | HIGH | LOW |
| **#1 Parking walk_time** | 🟡 MEDIUM | LOW | MEDIUM | LOW |
| **#5 Kulig timing** | 🟡 MEDIUM | MEDIUM | MEDIUM | LOW |

---

## 📐 PLAN NAPRAWY

### ETAP 1: Quick Wins (LOW complexity, HIGH impact)
**Czas: 1-2h**

#### FIX #1: Parking walk_time_min
```python
# app/application/services/plan_service.py
# BEFORE:
walk_time = poi_dict.get("parking_walk_time_min", 5)

# AFTER:
walk_time = int(poi_dict.get("parking_walk_time_min") or 5)
# Jeśli None lub 0, użyj 5
```

#### FIX #2: Free_time przed otwarciem
```python
# app/application/services/plan_service.py
# W _fill_gaps_in_items():
# Przed dodaniem free_time, sprawdź:
if next_item_type == 'attraction':
    next_poi = items[next_idx].get('poi')
    opening_time = get_opening_time(next_poi, context['date'])
    if opening_time and current_end < opening_time:
        # Zamiast free_time, przesuń atrakcję wcześniej
        items[next_idx]['start_time'] = minutes_to_time(opening_time)
        continue  # Skip gap filling
```

---

### ETAP 2: Core Features (MEDIUM complexity, CRITICAL impact)
**Czas: 4-6h**

#### FIX #6: Priority_level scoring
```python
# app/domain/scoring/preferences.py
def calculate_priority_bonus(poi: Dict, user: Dict) -> float:
    """
    Bonus za priority_level:
    - core: +30
    - secondary: +10
    - optional: 0
    """
    priority = poi.get('priority_level', '').lower()
    if priority == 'core':
        return 30
    elif priority == 'secondary':
        return 10
    return 0
```

```python
# app/domain/planner/engine.py
# W calculate_poi_score():
priority_bonus = calculate_priority_bonus(p, user)
score += priority_bonus
```

#### FIX #8: Target group scoring dla wszystkich grup
```python
# app/domain/scoring/type_matching.py (nowy moduł lub rozszerz family_fit.py)
def calculate_target_group_match(poi: Dict, user: Dict) -> float:
    """
    Match POI target_group z user group:
    - perfect match: +20
    - no match: -10
    - neutral: 0
    """
    user_group = user.get('target_group', '')
    poi_target_groups = poi.get('target_groups', [])
    
    if user_group in poi_target_groups:
        return 20  # Bonus
    elif len(poi_target_groups) > 0:
        return -10  # Penalty - POI ma target group ale nie pasuje
    return 0  # Neutral - POI bez target group
```

---

### ETAP 3: Complex Fixes (HIGH complexity, CRITICAL impact)
**Czas: 6-8h**

#### FIX #7: Limity atrakcji dziennie
```python
# app/domain/planner/engine.py
# Nowa stała:
GROUP_ATTRACTION_LIMITS = {
    'family_kids': {'soft': 6, 'hard': 7, 'core_min': 1, 'core_max': 2},
    'seniors': {'soft': 5, 'hard': 5, 'core_min': 1, 'core_max': 1},
    'solo': {'soft': 7, 'hard': 8, 'core_min': 2, 'core_max': 2},
    'couples': {'soft': 6, 'hard': 6, 'core_min': 1, 'core_max': 2},
    'friends': {'soft': 8, 'hard': 8, 'core_min': 2, 'core_max': 2},
}

def build_day(...):
    limits = GROUP_ATTRACTION_LIMITS[user['target_group']]
    core_count = 0
    total_count = 0
    
    for p in sorted_pois:
        # Hard stop
        if total_count >= limits['hard']:
            break
        
        # Soft limit penalty
        if total_count >= limits['soft']:
            score -= 50  # Heavy penalty
        
        # Core limits
        is_core = p.get('priority_level') == 'core'
        if is_core:
            if core_count >= limits['core_max']:
                continue  # Skip, za dużo core
            core_count += 1
        
        # Add POI...
        total_count += 1
    
    # Penalty jeśli brak minimum core
    if core_count < limits['core_min']:
        # Penalty to plan (lower priority)
        pass
```

#### FIX #3/#4: Transit names tracking po gap filling
```python
# app/application/services/plan_service.py
# Po _fill_gaps_in_items(), wywołaj:
def _update_transit_destinations(items: List[Any]) -> List[Any]:
    """
    Update transit 'to' names after gap filling inserted new POI.
    """
    for i, item in enumerate(items):
        if item.type != ItemType.TRANSIT:
            continue
        
        # Find next attraction after this transit
        next_attr = None
        for j in range(i + 1, len(items)):
            if items[j].type == ItemType.ATTRACTION:
                next_attr = items[j]
                break
        
        if next_attr:
            # Update transit destination
            item.to_name = next_attr.name
            item.to_lat = next_attr.lat
            item.to_lng = next_attr.lng
    
    return items

# W generate_plan():
items = self._fill_gaps_in_items(...)
items = self._update_transit_destinations(items)  ← NOWE
```

---

### ETAP 4: Nice-to-have (MEDIUM complexity, MEDIUM impact)
**Czas: 2-3h**

#### FIX #5: Evening/night time scoring
```python
# app/domain/scoring/time_of_day_scoring.py
# Dodaj evening/night:
def calculate_time_of_day_penalty(...):
    recommended = poi.get("recommended_time_of_day", [])
    
    # Map hours to time periods
    if 6 <= hour < 10:
        current_period = 'morning'
    elif 10 <= hour < 13:
        current_period = 'midday'
    elif 13 <= hour < 17:
        current_period = 'afternoon'
    elif 17 <= hour < 20:
        current_period = 'evening'
    else:
        current_period = 'night'
    
    if recommended and current_period not in recommended:
        if current_period in ['morning', 'night'] and 'afternoon' in recommended:
            return -20  # Strong penalty
        return -10  # Medium penalty
    
    return 0
```

---

## 🚨 RYZYKA I UWAGI

### ⚠️ Risk #1: Transit names fix może złamać istniejące testy
**Mitigacja:**
- Dodaj testy dla gap filling + transit tracking
- Sprawdź wszystkie transit assertions w testach

### ⚠️ Risk #2: Limity atrakcji mogą generować puste plany
**Mitigacja:**
- Jeśli za mało POI spełnia kryteria, złagodź limity
- Fallback: ignoruj soft limit jeśli za mało core POI

### ⚠️ Risk #3: Priority_level scoring może faworyzować tylko core
**Mitigacja:**
- Balance: core bonus = 30, ale secondary też dostaje +10
- Max 2 core dziennie (hard limit)

---

## ✅ TESTING STRATEGY

### Unit Tests:
1. `test_parking_walk_time()` - weryfikuj poprawne użycie POI data
2. `test_free_time_skip_before_opening()` - gap filling respektuje opening hours
3. `test_priority_bonus()` - core > secondary > optional
4. `test_target_group_match()` - seniors dostają senior POI
5. `test_attraction_limits()` - hard/soft limits per group

### Integration Tests:
1. `test_transit_names_after_gap_filling()` - transit "to" match next attraction
2. `test_full_plan_family_kids()` - max 7 atrakcji, 1-2 core
3. `test_full_plan_seniors()` - max 5 atrakcji, 1 core
4. `test_evening_attractions()` - kulig po zmroku

---

## 📊 SUKCES METRICS

✅ **FIX #1 Success**: parking_walk_time w planie = POI data  
✅ **FIX #2 Success**: 0 free_time items przed otwarciem atrakcji  
✅ **FIX #3/4 Success**: 100% transit "to" match next attraction name  
✅ **FIX #5 Success**: Kuligi tylko po 17:00  
✅ **FIX #6 Success**: Każdy plan ma ≥1 core attraction  
✅ **FIX #7 Success**: family_kids: 4-7 atrakcji, seniors: 3-5, etc.  
✅ **FIX #8 Success**: Seniorzy dostają POI z "seniors" w target_group  

---

## 🎯 EXECUTION PLAN

### Dzień 1 (2-3h):
- ✅ FIX #1: Parking walk_time
- ✅ FIX #2: Free_time przed otwarciem

### Dzień 2 (4-6h):
- ✅ FIX #6: Priority_level scoring
- ✅ FIX #8: Target group dla wszystkich

### Dzień 3 (6-8h):
- ✅ FIX #7: Limity atrakcji
- ✅ FIX #3/4: Transit names tracking

### Dzień 4 (2-3h):
- ✅ FIX #5: Evening/night scoring
- ✅ Testing + deployment

**Total: 14-20h (~2-3 dni robocze)**

---

## 📝 DOKUMENTACJA DLA PRZYSZŁOŚCI

### Kontekst decyzji:
1. **Dlaczego transit tracking?**  
   Gap filling dynamicznie wstawia POI, ale transit items były generowane wcześniej.  
   Musimy aktualizować references po modyfikacji kolejności.

2. **Dlaczego hard limits?**  
   Badania UX pokazują, że >8 atrakcji dziennie = zmęczenie i negatywne doświadczenie.  
   Seniorzy potrzebują więcej czasu na każdą atrakcję.

3. **Dlaczego priority_level ≠ must_see_score?**  
   - `priority_level` = business decision (core, secondary, optional)
   - `must_see_score` = crowd wisdom (1-10 rating)
   - Oba powinny wpływać na scoring, ale inaczej

---

## 🔄 ITERATION NOTES

Po wdrożeniu tych fixów, monitoruj:
- Feedback klientki na nowe plany
- Balance scoring (czy core nie dominuje zbyt moczo?)
- Edge cases (co jeśli tylko 2 core POI w mieście?)

Możliwe dalsze iteracje:
- Dynamic limits based on day length (dłuższy dzień = więcej atrakcji)
- Weather-based attraction prioritization
- Alternative routes (variant parameter)

---

**Status**: 📋 READY FOR IMPLEMENTATION  
**Author**: AI Assistant  
**Date**: 02.02.2026  
**Version**: 1.0  
