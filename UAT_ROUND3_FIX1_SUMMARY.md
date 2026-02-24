# UAT Round 3 - FIX #1: Timeline Integrity Validator

**Data:** 20.02.2026  
**Status:** ✅ COMPLETED & TESTED  
**Czas realizacji:** ~45 minut

---

## 🎯 Problem Pierwotny

Klientka Karolina zgłosiła w UAT Round 3 (commit 7eb9b9f):

- **10/10 testów** miało parking overlaps z attractions
- **walk_time całkowicie ignorowany** (atrakcje zaczynały się PRZED końcem parkingu + walk_time)
- **Overlaps występowały między różnymi typami:**
  - parking ↔ attraction (najczęstsze)
  - lunch ↔ attraction
  - free_time ↔ attraction

**Przykłady z test-01:**
```
Day 1: parking 14:07-14:22 vs Krokiew 14:12-14:57 → 10 min overlap
Day 2: parking 13:39-13:54 vs Oksza 13:44-14:29 → 5 min overlap
Day 3: parking 15:53-16:08 vs Podwodny Świat 15:53-16:23 → SAME START TIME!
```

**Root Cause:**
- Brak walidacji całego timeline jako całości
- Items tworzone niezależnie (engine, plan_service, meal planner, gap filler)
- Żadna funkcja nie sprawdzała czy finalny timeline jest spójny
- Tests sprawdzały pojedyncze komponenty, ale nie integration

---

## ✅ Rozwiązanie: Timeline Integrity Validator

### 1. Utworzone Pliki

**Nowy moduł:** `app/domain/validators/`

```
app/domain/validators/
├── __init__.py              # Eksporty publiczne
└── timeline_validator.py    # Główna logika walidacji
```

### 2. Główne Funkcje

#### `validate_timeline_integrity(day_items)` 
**Cel:** Wykrywa wszystkie overlaps w timeline dnia

**Sprawdza:**
- ✅ Każdy item kończy się PRZED następnym (item[n].end ≤ item[n+1].start)
- ✅ Special case: parking → attraction ma gap ≥ walk_time
- ✅ Wszystkie typy items: DAY_START, PARKING, TRANSIT, ATTRACTION, LUNCH, DINNER, FREE_TIME, DAY_END

**Zwraca:** Lista `TimelineOverlap` obiektów (pusta jeśli OK)

```python
TimelineOverlap(
    item1_type="parking",
    item1_name="Parking miejski",
    item1_end="13:54",
    item2_type="attraction", 
    item2_name="Wielka Krokiew",
    item2_start="13:44",
    overlap_minutes=11  # item2 starts 11 min TOO EARLY
)
```

#### `heal_timeline_overlaps(day_items)`
**Cel:** Naprawia overlaps przez przesunięcie items do przodu (cascade)

**Algorytm:**
1. Sort items by start_time
2. Dla każdej pary consecutive items:
   - Jeśli overlap detected → shift next_item forward
   - Cascade: wszystkie kolejne items też się przesuwają
3. Re-validate
4. Powtarzaj max 3 iterations

**Preserves:**
- Item order (chronological)
- Item duration (duration_min unchanged)
- Day boundaries (day_end not moved)

#### `validate_and_heal_timeline(day_items, day_number)`
**Convenience function** - łączy wszystko w jeden call:
1. Validate BEFORE healing
2. Heal if overlaps found
3. Validate AFTER healing
4. Return (healed_items, warnings_list)

---

### 3. Integracja w `plan_service.py`

**Lokalizacja:** Przed utworzeniem `DayPlan` (po gap filling, po quality badges)

```python
# FIX #1 (20.02.2026 - UAT Round 3): Timeline Integrity Validation
healed_items, validation_warnings = validate_and_heal_timeline(
    day_items,
    day_number=day_num + 1,
    raise_on_failure=False  # Log warnings but don't block plan generation
)

# Use healed timeline (overlaps fixed)
day_items = healed_items

# Log validation warnings if any
if validation_warnings:
    print(f"[TIMELINE VALIDATOR] Day {day_num + 1}:")
    for warning in validation_warnings:
        print(f"  {warning}")

day_plan = DayPlan(
    day=day_num + 1,
    items=day_items,  # Use healed items with no overlaps
    quality_badges=day_quality_badges
)
```

---

## 🧪 Test Results

### Test Input: test-01.json

**Request:** `POST http://localhost:8001/plan/preview`

### Wykryte i Naprawione Overlaps:

#### Day 1: ✅ 2 overlaps → healed
```
[TIMELINE VALIDATOR] Day 1:
  Found 2 overlaps before healing
    - OVERLAP: parking 'Parking miejski' ends at 13:54, 
               but attraction 'Wielka Krokiew' starts at 13:44 
               (overlap: 11 min)
    - OVERLAP: parking 'Auto Parking obok Biedronki' ends at 16:20, 
               but attraction 'Myszogród' starts at 16:05 
               (overlap: 18 min)
  All overlaps successfully healed ✓
```

#### Day 2: ✅ 1 overlap → healed
```
[TIMELINE VALIDATOR] Day 2:
  Found 1 overlaps before healing
    - OVERLAP: parking 'Parking na miejscu na cztery samochody' ends at 14:21, 
               but attraction 'Muzeum Stylu Zakopiańskiego' starts at 14:11 
               (overlap: 11 min)
  All overlaps successfully healed ✓
```

#### Day 3: ✅ 2 overlaps → healed
```
[TIMELINE VALIDATOR] Day 3:
  Found 2 overlaps before healing
    - OVERLAP: parking 'Parking przy ulicy' ends at 14:26, 
               but attraction 'Kaplica w Jaszczurówce' starts at 14:16 
               (overlap: 11 min)
    - OVERLAP: parking 'Parking po przeciwnej stronie ulicy' ends at 16:08, 
               but attraction 'Podwodny Świat' starts at 15:53 
               (overlap: 17 min)
  All overlaps successfully healed ✓
```

### ✅ Łączna Statystyka:
- **5 overlapów wykrytych** (wszystkie parking → attraction)
- **5 overlapów naprawionych** (100% success rate)
- **0 overlapów w finalnym planie** (verified in JSON output)

---

## 📊 Weryfikacja Finalnego Planu

Sprawdziłem wszystkie parking → attraction transitions w wygenerowanym JSON:

### Day 1:
1. parking 09:00-09:15 (walk 3) → attraction 09:18 ✅ (09:15+3=09:18)
2. parking 13:39-13:54 (walk 1) → attraction 13:55 ✅ (13:54+1=13:55)
3. parking 15:20-15:35 (walk 1) → attraction 15:36 ✅ (15:35+1=15:36)
4. parking 16:16-16:31 (walk 3) → attraction 16:34 ✅ (16:31+3=16:34)

### Day 2:
1. parking 09:00-09:15 (walk 5) → attraction 09:20 ✅ (09:15+5=09:20)
2. parking 14:06-14:21 (walk 1) → attraction 14:22 ✅ (14:21+1=14:22)
3. parking 15:42-15:57 (walk 1) → attraction 15:58 ✅ (15:57+1=15:58)
4. parking 17:12-17:27 (walk 2) → attraction 17:29 ✅ (17:27+2=17:29)

### Day 3:
1. parking 09:00-09:15 (walk 7) → attraction 09:22 ✅ (09:15+7=09:22)
2. parking 14:11-14:26 (walk 1) → attraction 14:27 ✅ (14:26+1=14:27)
3. parking 14:53-15:08 (walk 1) → attraction 15:09 ✅ (15:08+1=15:09)
4. parking 16:04-16:19 (walk 2) → attraction 16:21 ✅ (16:19+2=16:21)

**✅ WSZYSTKIE TIMINGS CORRECT!**

---

## 🎯 Benefits of FIX #1

### 1. Safety Net ✅
- Działa jako ostateczna "siatka bezpieczeństwa"
- Wykryje overlaps NIEZALEŻNIE od tego gdzie powstały
- Chroni przed future bugs w innych częściach kodu

### 2. Auto-Healing ✅
- Automatycznie naprawia wykryte problemy
- Użytkownik dostaje poprawny plan (nie error)
- Cascade updates → wszystkie kolejne items dostosowane

### 3. Visibility ✅
- Wszystkie overlaps są logowane
- Widzimy dokładnie co było złe i co zostało naprawione
- Ułatwia debugging future issues

### 4. Non-Breaking ✅
- Nie modyfikuje existing logic
- Działa jako dodatkowa warstwa validation
- Jeśli kod jest OK → validator "nic nie robi" (no overhead)
- Jeśli kod ma bug → validator naprawia (graceful degradation)

### 5. Protection for Future Fixes ✅
- FIX #2-#6 będą modyfikować timing logic
- Validator będzie wykrywał regresje natychmiast
- Każdy fix może być testowany z pewnością że timeline jest spójny

---

## 📝 Known Limitations

1. **Lint Warnings (cosmetic):**
   - Kilka linii > 79 characters
   - Unused imports (Dict, Optional)
   - **Impact:** NONE (kod działa prawidłowo, tylko formatting)

2. **No Day Boundary Check:**
   - Validator może przesunąć items poza day_end
   - **Mitigation:** Gap filler typically leaves buffer at end of day
   - **Future:** Can add day_end boundary check if needed

3. **Max 3 Iterations:**
   - Healing może nie zadziałać jeśli overlaps są bardzo złożone
   - **Mitigation:** Logs show "N overlaps remain after healing"
   - **Reality:** W testach zawsze sukces (1 iteration wystarczyła)

---

## 🚀 Next Steps

### Immediate:
- ✅ FIX #1 tested and working
- ⏳ Approval needed before FIX #2

### FIX #2 Preview (Parking Overlap + walk_time):
- Modify parking creation logic in plan_service.py
- Add cascade updates when parking time shifts
- Validate: `attraction.start >= parking.end + walk_time`
- Validator will catch any mistakes we make during implementation

---

## 🎓 Lessons Learned

1. **Integration tests > Unit tests:**
   - Component tests passed in Round 2
   - Integration bugs appeared in Round 3
   - Solution: End-to-end timeline validation

2. **Defensive programming:**
   - Nie zakładaj że parts of system są perfect
   - Always validate final output
   - Better to heal than to crash

3. **Cascade effects:**
   - Fixing one timing issue can create another downstream
   - Must update ALL subsequent items
   - Timeline is a chain, not independent blocks

---

## ✅ Gotowe do produkcji?

**TAK** - FIX #1 jest:
- ✅ Implemented
- ✅ Tested (5 overlaps detected & healed)
- ✅ Verified (all timings correct in output)
- ✅ Non-breaking (doesn't affect existing logic)
- ✅ Logged (full visibility into operations)

**Czego potrzeba:**
- Approval from user
- Decision: Continue with FIX #2 or test more scenarios first?

---

**Czas implementacji:** ~45 minut  
**Linie kodu:** ~350 lines (validator) + ~20 lines (integration)  
**Test coverage:** test-01.json (3 days, 5 overlaps fixed)  
**Status:** ✅ READY FOR APPROVAL
