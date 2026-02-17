# BUGFIX: Overlapping Events Validation (16.02.2026)

## Problem

Klientka zgłosiła **CRITICAL BUG** w CLIENT FEEDBACK:
> Test 08 Day 6: free_time + museum występują jednocześnie (te same godziny)

**Przykład z planu:**
```json
{
  "type": "free_time",
  "start_time": "14:30",
  "end_time": "15:10"
},
{
  "type": "attraction",
  "name": "Muzeum Tatrzańskie",
  "start_time": "14:30",
  "end_time": "15:30"
}
```

**Impact:** Plan dnia zawiera konfliktujące wydarzenia, niemożliwe do wykonania.

---

## Root Cause

Funkcja `build_day()` w `engine.py`:
- Nie walidowała czasu przed dodaniem itemów do planu
- Mogła dodać nowy item (attraction, free_time, lunch) który nakłada się z istniejącymi
- Brak mechanizmu wykrywania konfliktów czasowych

**Miejsca problematyczne:**
1. Line ~1163: `plan.append(free_time)` - bez walidacji
2. Line ~1214: `plan.append(attraction)` - bez walidacji
3. Line ~758: `plan.append(lunch_break)` - bez walidacji

---

## Solution

**Krok 1: Funkcja walidacyjna** (`engine.py` line 42-74)

```python
def _check_time_overlap(plan, new_start_time, new_end_time):
    """
    Check if new item overlaps with existing items in plan.
    
    Args:
        plan: List of plan items (dicts with start_time/end_time)
        new_start_time: Start time string "HH:MM"
        new_end_time: End time string "HH:MM"
    
    Returns:
        tuple: (overlaps: bool, conflicting_item: dict or None)
    """
    new_start_min = time_to_minutes(new_start_time)
    new_end_min = time_to_minutes(new_end_time)
    
    for item in plan:
        if "start_time" not in item or "end_time" not in item:
            continue
        
        item_start_min = time_to_minutes(item["start_time"])
        item_end_min = time_to_minutes(item["end_time"])
        
        # Overlap condition: new starts before existing ends AND 
        # new ends after existing starts
        if new_start_min < item_end_min and new_end_min > item_start_min:
            return True, item
    
    return False, None
```

**Krok 2: Walidacja przed dodaniem free_time** (line ~1163)

```python
# BEFORE:
plan.append({"type": "free_time", ...})

# AFTER:
free_start_time = minutes_to_time(now)
free_end_time = minutes_to_time(now + free_duration)

overlaps, conflict = _check_time_overlap(plan, free_start_time, free_end_time)
if overlaps:
    print(f"[OVERLAP DETECTED] free_time conflicts...")
    now += 15  # Skip, advance time
    continue

plan.append({"type": "free_time", ...})
```

**Krok 3: Walidacja przed dodaniem attraction** (line ~1214)

```python
# BEFORE:
plan.append({"type": "attraction", ...})

# AFTER:
attraction_start_time = minutes_to_time(now)
attraction_end_time = minutes_to_time(now + best_duration)

overlaps, conflict = _check_time_overlap(plan, attraction_start_time, attraction_end_time)
if overlaps:
    print(f"[OVERLAP DETECTED] attraction conflicts...")
    used.add(poi_id(best))  # Mark as used to avoid retry
    now += 15
    continue

plan.append({"type": "attraction", ...})
```

**Krok 4: Walidacja przed dodaniem lunch_break** (line ~758)

```python
# BEFORE:
plan.append({"type": "lunch_break", ...})

# AFTER:
lunch_start_time = minutes_to_time(now)
lunch_end_time = minutes_to_time(min(end, now + LUNCH_DURATION_MIN))

overlaps, conflict = _check_time_overlap(plan, lunch_start_time, lunch_end_time)
if overlaps:
    print(f"[OVERLAP DETECTED] lunch conflicts...")
    # Adjust lunch time - move to after conflicting item
    conflict_end_min = time_to_minutes(conflict.get('end_time'))
    now = conflict_end_min

plan.append({"type": "lunch_break", ...})
```

---

## Testing

### **Unit Tests** - `test_overlap_validation.py`

**Test 1: _check_time_overlap function**
```
✅ 09:00-09:20 before attraction → NO OVERLAP
✅ 09:30-11:00 exact match → OVERLAP DETECTED
✅ 10:30-11:30 partial overlap → OVERLAP DETECTED
✅ 11:30-12:30 between items → NO OVERLAP
✅ 13:30-14:30 overlap with lunch → OVERLAP DETECTED
```

**Result:** 5/5 tests PASSED ✅

### **Integration Tests** - `build_day()` 

Generated plan:
```
Type                 Start      End        
----------------------------------------
accommodation_start  09:00      N/A       
free_time            09:00      09:40      
free_time            09:40      10:20      
...
lunch_break          13:00      13:40      
...
accommodation_end    17:00      N/A       
```

**Validation:** 0 overlapping events ✅

---

## Impact

**Fixed:**
- ✅ No more simultaneous events (free_time + attraction)
- ✅ Time continuity enforced throughout the day
- ✅ Conflicting items are skipped or rescheduled

**Cases handled:**
1. **free_time overlap:** Skip free_time, advance time by 15 min
2. **attraction overlap:** Mark POI as used, skip, advance time
3. **lunch overlap:** Adjust lunch time to after conflicting item

**Edge cases:**
- Items without time range (accommodation_start) are ignored
- Conflicts logged to console for debugging
- Automatic time adjustment for lunch_break

---

## Files Changed

1. **engine.py**:
   - Line 42-74: Added `_check_time_overlap()` function
   - Line ~758: Added validation before `lunch_break` append
   - Line ~1163: Added validation before `free_time` append
   - Line ~1214: Added validation before `attraction` append

2. **test_overlap_validation.py** (NEW):
   - Unit tests for `_check_time_overlap()`
   - Integration test for `build_day()`

---

## Knowledge for Future

**ALWAYS:**
- Validate time range before adding items to plan
- Check for overlaps with ALL existing plan items
- Log conflicts for debugging

**NEVER:**
- Add items to plan without time validation
- Assume `now` variable tracks time correctly (validate explicitly)

**Client's Requirement:**
> "No overlapping events - plan must be executable"

---

## Date: 16.02.2026
## Reported by: Karolina (klientka)
## Fixed by: AI Assistant
## Status: ✅ RESOLVED
