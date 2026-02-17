# CLIENT FEEDBACK - 16.02.2026 (Karolina)

## 📋 TEST SUITE - 10 Manual Tests

### TEST 01 - Family kids 6-10, 3 dni, standard, car
```json
{
  "budget": { "daily_limit": 500, "level": 2 },
  "daily_time_window": { "start": "09:00", "end": "19:00" },
  "group": { "type": "family_kids", "size": 4, "children_age": 8, "crowd_tolerance": 1 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["kids_attractions", "nature_landscape", "mountain_trails"],
  "transport_modes": ["car"],
  "travel_style": "balanced",
  "trip_length": { "days": 3, "start_date": "2026-02-20" }
}
```

### TEST 02 - Couples, 3 dni, premium, vibe: cultural + relax
```json
{
  "budget": { "daily_limit": 900, "level": 3 },
  "daily_time_window": { "start": "10:00", "end": "20:00" },
  "group": { "type": "couples", "size": 2, "crowd_tolerance": 2 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
  "transport_modes": ["car"],
  "travel_style": "cultural",
  "trip_length": { "days": 3, "start_date": "2026-02-20" }
}
```

### TEST 03 - Friends, 2 dni, standard, adventure + active
```json
{
  "budget": { "daily_limit": 600, "level": 2 },
  "daily_time_window": { "start": "09:00", "end": "21:00" },
  "group": { "type": "friends", "size": 4, "crowd_tolerance": 3 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["active_sport", "mountain_trails", "history_mystery"],
  "transport_modes": ["car"],
  "travel_style": "adventure",
  "trip_length": { "days": 2, "start_date": "2026-02-20" }
}
```

### TEST 04 - Solo, 5 dni, budżet low, balanced
```json
{
  "budget": { "daily_limit": 250, "level": 1 },
  "daily_time_window": { "start": "09:30", "end": "18:00" },
  "group": { "type": "solo", "size": 1, "crowd_tolerance": 1 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["nature_landscape", "history_mystery", "museum_heritage"],
  "transport_modes": ["car"],
  "travel_style": "balanced",
  "trip_length": { "days": 5, "start_date": "2026-02-20" }
}
```

### TEST 05 - Family kids 3-6, 2 dni, krótki dzień
```json
{
  "budget": { "daily_limit": 450, "level": 2 },
  "daily_time_window": { "start": "10:00", "end": "16:00" },
  "group": { "type": "family_kids", "size": 4, "children_age": 5, "crowd_tolerance": 1 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["kids_attractions", "relaxation"],
  "transport_modes": ["car"],
  "travel_style": "relax",
  "trip_length": { "days": 2, "start_date": "2026-02-20" }
}
```

### TEST 06 - Seniors, 3 dni, standard, spokojnie
```json
{
  "budget": { "daily_limit": 500, "level": 2 },
  "daily_time_window": { "start": "10:00", "end": "18:00" },
  "group": { "type": "seniors", "size": 2, "crowd_tolerance": 1 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["museum_heritage", "relaxation", "nature_landscape"],
  "transport_modes": ["car"],
  "travel_style": "relax",
  "trip_length": { "days": 3, "start_date": "2026-02-20" }
}
```

### TEST 07 - Underground + history
```json
{
  "budget": { "daily_limit": 500, "level": 2 },
  "daily_time_window": { "start": "09:00", "end": "19:00" },
  "group": { "type": "friends", "size": 4, "crowd_tolerance": 2 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["underground", "history_mystery", "museum_heritage"],
  "transport_modes": ["car"],
  "travel_style": "adventure",
  "trip_length": { "days": 2, "start_date": "2026-02-20" }
}
```

### TEST 08 - Maximum days 7
```json
{
  "budget": { "daily_limit": 600, "level": 2 },
  "daily_time_window": { "start": "09:00", "end": "20:00" },
  "group": { "type": "couples", "size": 2, "crowd_tolerance": 2 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["mountain_trails", "nature_landscape", "local_food_experience", "museum_heritage"],
  "transport_modes": ["car"],
  "travel_style": "balanced",
  "trip_length": { "days": 7, "start_date": "2026-02-20" }
}
```

### TEST 09 - Crowd_tolerance skrajnie niska
```json
{
  "budget": { "daily_limit": 500, "level": 2 },
  "daily_time_window": { "start": "09:00", "end": "19:00" },
  "group": { "type": "solo", "size": 1, "crowd_tolerance": 1 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["nature_landscape", "relaxation"],
  "transport_modes": ["car"],
  "travel_style": "relax",
  "trip_length": { "days": 3, "start_date": "2026-02-22" }
}
```

### TEST 10 - Budget tight + premium preferencje
```json
{
  "budget": { "daily_limit": 200, "level": 1 },
  "daily_time_window": { "start": "10:00", "end": "18:00" },
  "group": { "type": "couples", "size": 2, "crowd_tolerance": 2 },
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "preferences": ["water_attractions", "relaxation", "local_food_experience"],
  "transport_modes": ["car"],
  "travel_style": "relax",
  "trip_length": { "days": 2, "start_date": "2026-02-22" }
}
```

---

## 🔴 CRITICAL BUGS (12 Problems)

### ✅ PROBLEM #1: cost_estimate Inconsistent (FIXED 16.02.2026)

**Issue:**
Ten sam POI ma różne `cost_estimate` w zależności od testu, mimo że `ticket_info` jest identyczne.

**Examples:**
- **Wielka Krokiew**: raz `cost_estimate: 90`, innym razem `25` przy bilecie normalnym 25
- **Podwodny Świat**: raz `cost_estimate: 104`, innym razem `28`
- **Termy Gorący Potok**: raz `208`, innym razem `59`
- **Dom do góry nogami**: `cost_estimate: 0`, `ticket_normal: 21`

**Root Cause:**
System czasem liczy dla całej grupy (np. 2+2), czasem dla 1 osoby. Brakuje kontekstu.

**Status:** ✅ FIXED (16.02.2026)
**Fix:** BUGFIX_free_entry_logic_16_02_2026.md

---

### ✅ PROBLEM #2: Overlapping Events (FIXED 16.02.2026)

**Issue:**
Test 08 Day 6: free_time + museum występują jednocześnie.

**Example:**
```
• free_time 09:00-09:40
• free_time 09:40-10:20
• jednocześnie Muzeum Tatrzańskie 09:18-10:18
```

**Impact:** Plan zawiera konfliktujące wydarzenia, niemożliwe do wykonania.

**Status:** ✅ FIXED (16.02.2026)
**Fix:** BUGFIX_overlapping_events_16_02_2026.md

---

### ✅ PROBLEM #3: Missing Transits Between Distant Locations (VERIFIED WORKING)

**Issue:**
Test 06 Day 1: Kaplica kończy się 11:43, Oksza startuje 11:52. Nie ma transit, choć to inna lokalizacja.

**Examples:**
- Test 06 Day 1: Kaplica → Oksza (brak transit)
- Test 07 Day 2: Myszogród (Krupówki) → Termy Gorący Potok (Szaflary) - tylko start term 15:36 po Myszogrodzie 15:35, brak przejazdu 30+ minut

**Status:** ✅ VERIFIED WORKING (16.02.2026)
**Note:** Comprehensive tests (5 scenarios) confirmed all adjacent POI have transits, including very distant pairs (15.90 km). Issue may have been auto-fixed by Problems #1-2.

---

### 🔄 PROBLEM #4: Time Gaps/Teleports (HIGH PRIORITY - IN PROGRESS)

**Issue:**
Oś czasu ma "dziury", które nie są opisane. W wielu miejscach plan ma przerwy między transit a attraction, ale nie ma wpisu typu buffer/walk/queue/free_time.

**Examples:**
- **Test 01**: transit kończy się 10:11, następna atrakcja startuje 10:26 → **brak wyjaśnienia 15 minut**
- **Test 06 Day 1**: Kaplica kończy się 11:43, Oksza startuje 11:52 → **9 minut luki**
- **Test 10 Day 1**: Dom → Krokiew nie ma transit, różnica 4 min (11:48-11:52)

**Client Requirement:**
> "Może prowadźmy jawny typ bufora, np.:
> • type: "buffer" z reason: "parking_walk" | "tickets_queue" | "restroom" | "photo_stop" | "traffic_margin"
> albo automatycznie generuj free_time zawsze, gdy jest luka > X minut."

**Proposed Solution:**
Add buffer items to explain all time gaps:
- `parking_walk`: 5-15 min (walking from parking to attraction entrance)
- `tickets_queue`: 5-20 min (waiting in line at popular attractions)
- `restroom`: 5-10 min (bathroom breaks after long attractions)
- `photo_stop`: 5-15 min (photo opportunities at scenic locations)
- `traffic_margin`: 5-10 min (buffer for unexpected delays)

**Priority:** 🔴 HIGH
**Status:** 🔄 IN PROGRESS (16.02.2026)

---

### PROBLEM #5: why_selected Illogical (HIGH PRIORITY)

**Issue:**
`why_selected` zawiera nielogiczne argumenty niepasujące do POI.

**Examples:**
- **Test 02**: Dom do góry nogami ma "Great for museum_heritage lovers" + "Breathtaking mountain views"
  - To jest atrakcja "instagramowa/krótka", nie punkt widokowy ani muzeum
- **Test 01**: Wielka Krokiew jako "nature_landscape lovers" jest naciągane (to bardziej active_sport / landmark / viewpoint)

**Client Suggestion:**
> "Może słownik why_selected powinien być generowany z tagów POI? Albo dodać walidację: jeśli POI nie ma tagu nature_landscape / mountain_trails / viewpoint, to nie wolno używać argumentów o widokach górskich."

**Solution:**
Walidacja why_selected względem tagów POI:
- Jeśli POI nie ma tagu `nature_landscape`, `mountain_trails`, `viewpoint` → NIE używaj argumentów o widokach górskich
- Jeśli POI nie ma tagu `museum_heritage` → NIE używaj argumentów o muzeach
- Generuj why_selected tylko z faktycznych tagów i atrybutów POI

**Priority:** 🔴 HIGH
**Files:** `app/domain/planner/explainability.py`

---

### PROBLEM #6: quality_badges Inconsistent (MEDIUM PRIORITY)

**Issue:**
Ten sam POI raz ma `must_see`/`core_attraction`, innym razem nic.

**Impact:** Rozwala spójność planu i expectations użytkownika.

**Solution:**
- Standardize badge generation logic
- Badge powinien być deterministyczny dla danego POI + user profile
- Cache badges per POI to ensure consistency

**Priority:** 🟡 MEDIUM
**Files:** `app/domain/planner/explainability.py`

---

### PROBLEM #7: Brakuje Time Continuity Validator (HIGH PRIORITY)

**Issue:**
Generator powinien automatycznie sprawdzać:
- Czy `start_time` kolejnego itemu = `end_time` poprzedniego albo jest wstawiony buffer/free_time
- Czy nie ma nakładek
- Czy czasy są w granicach dnia (`day_start` → `day_end`)

**Current Problem:**
Często `day_end` jest dużo później niż ostatnia atrakcja (np. kończy się ~17:04, a `day_end` 19:00), ale nie ma "co się dzieje po drodze".

**Solution:**
1. Validator sprawdzający ciągłość czasu przed zwróceniem planu
2. Jeśli zostaje wolny czas do `day_end`, dodaj automatycznie `free_time` z sensowną etykietą: "kolacja / spacer / zakupy"

**Priority:** 🔴 HIGH
**Files:** `app/domain/planner/engine.py`, `app/application/services/plan_service.py`

---

### PROBLEM #8: Lunch Time Constraint (MEDIUM PRIORITY)

**Issue:**
Test 07 Day 1: lunch o 16:15 po termach i mini-zoo wygląda nienaturalnie. Lunch powinien być zdecydowanie wcześniej (12:00-14:30).

**Solution:**
Enforce lunch time window constraint: 12:00-14:30
- Jeśli plan nie ma lunch w tym oknie, system powinien:
  1. Spróbować wstawić lunch w odpowiednim miejscu
  2. Jeśli niemożliwe, zaraportować warning

**Priority:** 🟡 MEDIUM
**Files:** `app/domain/planner/engine.py`

---

### PROBLEM #9: Max 1 Termy/Day For Seniors (MEDIUM PRIORITY)

**Issue:**
Test 06 Day 3: Termy Zakopiańskie + Chochołowskie Termy tego samego dnia. To nie ma sensu.

**Client Requirement:**
> "Dla profilu 'senior-friendly' ustawmy limit: max 1 kompleks termalny dziennie"

**Solution:**
- Hard limit: max 1 termy per day dla `target_group: "seniors"`
- Optional: Apply same rule for other groups (user preference)

**Priority:** 🟡 MEDIUM
**Files:** `app/domain/planner/engine.py`

---

### PROBLEM #10: Standardize start_time/end_time Fields (LOW PRIORITY)

**Issue:**
W danych pojawiają się różne "style":
- `time` w `day_start`/`day_end`, a reszta `start_time`/`end_time`
- Czasem `free_time` ma `label`, czasem "Czas wolny: …" w labelu, a czasem jest go brak

**Client Suggestion:**
> "Wszystkie itemy (włącznie z day_start/day_end) mają start_time/end_time"

**Solution:**
Standardize all items to use `start_time`/`end_time`:
```json
{
  "type": "day_start",
  "start_time": "09:00",
  "end_time": "09:00",
  ...
}
```

**Priority:** 🟢 LOW
**Files:** `app/domain/planner/engine.py`, `app/application/services/plan_service.py`

---

### PROBLEM #11: Empty Days Detection (MEDIUM PRIORITY)

**Issue:**
Test 08 Day 7: praktycznie sam `free_time` co 40 minut (15 bloków). To wygląda jak fallback generatora, gdy nie ma pomysłów lub filtr zbyt restrykcyjny.

**Client Requirement:**
> "Jeżeli nie ma atrakcji → plan powinien powiedzieć wprost:
> 'Brak dopasowanych atrakcji w promieniu X km spełniających warunki Y'
> i zaproponować poluzowanie filtrów.
> free_time powinien być maks 1-2 bloki dziennie, nie 15."

**Solution:**
1. Detect empty/sparse days (>50% free_time)
2. Return error message suggesting filter relaxation
3. Limit free_time to max 2 blocks per day

**Priority:** 🟡 MEDIUM
**Files:** `app/domain/planner/engine.py`

---

### PROBLEM #12: Parking References Validation (LOW PRIORITY)

**Issue:**
W części dni parking jest jako osobny item, ale potem atrakcje wskazują parking "z innego świata" lub generują parking "na miejscu" bez potwierdzenia.

**Solution:**
- Validate parking references: każda atrakcja z `parking` powinien wskazywać na istniejący parking item
- Jeśli brak parking item, nie generuj `parking` reference w attraction

**Priority:** 🟢 LOW
**Files:** `app/application/services/plan_service.py`

---

## 📊 TEST RESULTS SUMMARY

### Test 01 (3 dni, family kids)
**Positives:**
- Dobry rozkład dnia
- Różnorodność: sport + indoor + dziecięce + natura + relaks
- Dni 2-3 mają sens: duży hike + regeneracja w mieście

**Problems:**
- ❌ cost_estimate rozjazd (FIXED)
- ❌ why_selected nie trafia (Wielka Krokiew jako "nature_landscape lovers")
- ❌ Za dużo krótkich free_time jako zapychacz
- ❌ Braki w osi czasu (transit kończy 10:11, atrakcja startuje 10:26)

---

### Test 02 (3 dni, couples)
**Positives:**
- Rusinowa Polana + Krokiew: fajny duet
- Sensowne czasy startu (10:00)
- Dzień 3 spójny: muzeum + Oksza + Atma + termy

**Problems:**
- ❌ Persona "para" nie trzyma się atrakcji (Dom do góry nogami, Mini Zoo)
- ❌ why_selected błędy semantyczne
- ❌ cost_estimate niespójne (FIXED)
- ❌ Zbyt dużo free_time bez powodu

---

### Test 03 (2 dni, friends)
**Positives:**
- Dolina Kościeliska + Krokiew + termy: sensowny zestaw
- Czasówki generalnie OK

**Problems:**
- ❌ Atrakcja po termach o 20:17 (Wystawa Figur Woskowych) - nielogiczne
- ❌ Free_time przed tranzytem (19:33-19:55) - mechaniczny klocek
- ❌ cost_estimate: 0 dla Domu (FIXED)

**Recommendation:**
Po termach tylko kolacja/relaks, zero zwiedzania.

---

### Test 04 (2 dni, solo)
**Positives:**
- ✅ Persona "solo" najlepiej zrealizowana
- ✅ Dzień 1 ma dobrą dramaturgię
- ✅ Dzień 2 spójny

**Problems:**
- ❌ cost_estimate: 0 (FIXED)
- ❌ Brak tranzytu mini zoo → kaplica
- ❌ Za ciasne przejścia (22 min bez opisu)

---

### Test 05 (2 dni, family kids, short day)
**Positives:**
- ✅ Krótki, prosty, ma sens
- ✅ Logiczny ciąg Day 2

**Problems:**
- ❌ cost_estimate niespójne (FIXED)
- ❌ Brak free_time/buforów w końcówce Day 2

---

### Test 06 (3 dni, seniors)
**Positives:**
- ✅ Logika "zwiedzanie + termy"
- ✅ Dobre core punkty

**Problems:**
- ❌ Brak tranzytów (Kaplica → Oksza, Oksza → Lunch)
- ❌ **2 termy w Day 3** - nie ma sensu dla seniorów

**Recommendation:**
Max 1 kompleks termalny dziennie dla seniorów.

---

### Test 07 (2 dni, friends)
**Positives:**
- ✅ Dzień 2 z Doliną dobry

**Problems:**
- ❌ Lunch o 16:15 nienaturalny (powinien 12:00-14:30)
- ❌ cost_estimate: 0 (FIXED)
- ❌ Brak tranzytu Myszogród → Termy (30+ min)

**Recommendation:**
Walidator dystansu/czasu + przesunięcie startu lub zmiana POI.

---

### Test 08 (7 dni, couples)
**Positives:**
- ✅ Dni 1-4 mają sens tematycznie

**Problems:**
- ❌ **Day 6 overlap** - plan logicznie popsuty (FIXED)
- ❌ Day 5: 3 bloki free_time po 40 min (18:00-20:00)
- ❌ **Day 7: pusty dzień** - wolny czas w pociętych kawałkach

---

### Test 09 (3 dni, solo)
**Positives:**
- ✅ Dobry balans: Rusinowa + Dolina + miasto + termy
- ✅ Dla solo ma sens

**Problems:**
- ❌ cost_estimate: 0 (FIXED)
- ❌ Luki bez tranzytów
- ❌ Termy + oddalone atrakcje wymagają walidacji czasu

---

### Test 10 (2 dni, couples)
**Positives:**
- ✅ Bardzo sensowny Day 1
- ✅ Day 2: Rusinowa + Termy Bukovina logiczne

**Problems:**
- ❌ Brak przejazdów (Dom → Krokiew: 4 min różnicy)
- ❌ Brak transit Mini Zoo → Kaplica
- ❌ cost_estimate niespójne (FIXED)

---

## 📅 IMPLEMENTATION ROADMAP

### Phase 1: CRITICAL FIXES (16.02.2026)
- [x] Problem #1: cost_estimate calculation - FIXED
- [x] Problem #2: Overlapping events - FIXED
- [x] Problem #3: Transit validation - VERIFIED WORKING
- [ ] Problem #4: Time gaps/buffers - **IN PROGRESS**
- [ ] Problem #5: why_selected logic - HIGH priority
- [ ] Problem #7: Time continuity validator - HIGH priority

### Phase 2: MEDIUM FIXES (17-18.02.2026)
- [ ] Problem #6: quality_badges consistency
- [ ] Problem #8: Lunch time constraint
- [ ] Problem #9: Max 1 termy/day for seniors
- [ ] Problem #11: Empty days detection

### Phase 3: LOW PRIORITY (19-20.02.2026)
- [ ] Problem #10: Standardize fields
- [ ] Problem #12: Parking references validation

---

**Date:** 16.02.2026  
**Author:** Karolina (Client)  
**Status:** Active Development  
**Priority:** 🔴 HIGH - Multiple critical bugs affecting user experience
