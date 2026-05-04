# 🛡️ PREVENTION GUIDE: Avoiding Future Cap/Limit Issues

**Document Purpose:** Praktyczne wzorce i checklist'y aby uniknąć podobnych problemów przy rozwoju backendu.

**Created:** 01.05.2026  
**Based on:** Problem #7 investigation (free_time caps) + Problem #4 (termy limits) + Problem #6 (trail limits)

---

## 🎯 Core Principle: Single Source of Truth

### ❌ ANTI-PATTERN: Rozrzucona logika

```python
# engine.py - location 1
free_duration = min(120, gap)  # ❌ Different cap

# engine.py - location 2
free_duration = min(180, gap)  # ❌ Different cap

# plan_service.py - location 3
free_duration = min(90, gap)   # ❌ Different cap
```

**Problem:**
- 3 różne miejsca = 3 różne cap values
- Każda zmiana wymaga update w 3 miejscach
- Łatwo zapomnieć o jednej lokalizacji
- Niemożliwe do utrzymania przy rozwoju

### ✅ BEST PRACTICE: Centralized Helper

```python
# app/domain/planner/free_time_utils.py

from typing import Dict, Optional
from app.domain.planner.utils import time_to_minutes, minutes_to_time

# SINGLE SOURCE OF TRUTH dla cap value
FREE_TIME_MAX_DURATION_MIN = 60  # Client requirement: max 60 min

def create_free_time(
    start_min: int,
    duration_requested: int,
    context: Dict,
    description: str = "Czas wolny"
) -> Dict:
    """
    Creates free_time with consistent cap logic.
    
    USAGE: Use this function for ALL free_time creation in codebase.
    
    Args:
        start_min: Start time in minutes from midnight
        duration_requested: Desired duration (will be capped)
        context: Planning context with day_end_min, etc.
        description: Smart label for free_time
    
    Returns:
        Dict with free_time item
    """
    # STEP 1: Apply business rule cap (ALWAYS FIRST)
    capped_duration = min(duration_requested, FREE_TIME_MAX_DURATION_MIN)
    
    # STEP 2: Apply environmental constraint (day_end)
    day_end_min = context.get("day_end_min")
    if day_end_min:
        max_until_day_end = day_end_min - start_min
        capped_duration = min(capped_duration, max_until_day_end)
    
    # STEP 3: Apply minimum threshold
    if capped_duration < 5:
        return None  # Too short, skip
    
    end_min = start_min + capped_duration
    
    return {
        "type": "free_time",
        "start_time": minutes_to_time(start_min),
        "end_time": minutes_to_time(end_min),
        "duration_min": capped_duration,
        "description": description
    }

def get_free_time_max_cap() -> int:
    """Returns current max cap for validation."""
    return FREE_TIME_MAX_DURATION_MIN
```

**Usage w engine.py:**

```python
from app.domain.planner.free_time_utils import create_free_time

# PRZED: 6 różnych miejsc z różnymi cap values
free_duration = min(120, gap_duration, end - now)
plan.append({
    "type": "free_time",
    "start_time": minutes_to_time(now),
    "end_time": minutes_to_time(now + free_duration),
    "duration_min": free_duration,
    "description": "Czas wolny"
})

# PO: Jedna funkcja, spójny cap
free_time = create_free_time(
    start_min=now,
    duration_requested=gap_duration,
    context={"day_end_min": end},
    description=get_smart_label(plan, now, gap_duration, end)
)
if free_time:
    plan.append(free_time)
```

**Benefits:**
- ✅ Zmiana cap value w JEDNYM miejscu (FREE_TIME_MAX_DURATION_MIN)
- ✅ Spójna logika we WSZYSTKICH lokalizacjach
- ✅ Łatwe testowanie (mock jedna funkcja)
- ✅ Dokumentacja w jednym miejscu

---

## 🔢 Counter Pattern: Safe State Updates

### ❌ ANTI-PATTERN: Counter After Continue

```python
# POI added to plan
plan.append({"type": "attraction", "name": "Termy"})

# Special case handling
if should_add_lunch:
    add_lunch()
    continue  # ⚠️ SKIPS CODE BELOW

# Counter increment - NEVER REACHED!
if is_termy(poi):
    termy_count += 1  # ❌ Skipped!
```

**Problem:**
- Continue jumps to next iteration
- Counter never increments
- Limit check becomes useless
- Silent failure (no error, just wrong behavior)

### ✅ BEST PRACTICE: Update State Before Continue

```python
# POI added to plan
plan.append({"type": "attraction", "name": "Termy"})

# IMMEDIATELY update ALL state (counters, flags, tracking)
if is_termy(poi):
    termy_count += 1
    print(f"[COUNTER] Termy added: {poi_name(poi)}, total={termy_count}/{max_termy}")

if is_trail(poi):
    trail_count += 1
    print(f"[COUNTER] Trail added: {poi_name(poi)}, total={trail_count}/{max_trails}")

# Update global tracking
used_poi_ids.add(poi_id(poi))

# NOW safe to use continue/break
if should_add_lunch:
    add_lunch()
    continue  # ✅ All counters already updated

# Rest of loop code...
```

**General Template:**

```python
# 1. Main action (append, modify, etc.)
perform_action(item)

# 2. IMMEDIATELY update ALL state
update_counters(item)
update_flags(item)
update_tracking_structures(item)
log_action(item)

# 3. NOW safe for early exit
if special_condition:
    handle_special_case()
    continue  # or break, return

# 4. Regular flow continues
regular_processing()
```

**Code Review Checklist:**

```
When reviewing loops with state updates:

□ Find all continue/break/return statements in loop
□ Identify all state variables updated in loop (counters, flags, sets, etc.)
□ Verify ALL state updates happen BEFORE first continue/break
□ Check if any code after continue is meant to execute (indicates bug)
□ Add logging immediately after state update for debugging
□ Test edge cases where early exit is triggered
```

---

## 🎯 Multi-Path Filter Pattern

### ❌ ANTI-PATTERN: Filter Only Main Path

```python
# Main loop filter
if termy_count >= max_termy:
    filtered = [p for p in filtered if not is_termy(p)]

for poi in filtered:
    # Main scoring logic
    score = calculate_score(poi)
    candidates.append((poi, score))

# BUT: Special logic bypasses main loop!
if high_priority_needed:
    # Core rotation - NO FILTER!
    best = max(rotation_pool, key=lambda p: p["priority_level"])  # ⚠️ Can pick termy!
    plan.append(best)

# AND: Variety logic also bypasses!
if variety_needed:
    # Variety selection - NO FILTER!
    candidates = [p for p in all_poi if abs(score(p) - best_score) < 0.01]  # ⚠️ Can pick termy!
    best = random.choice(candidates)
    plan.append(best)
```

**Problem:**
- Limit checked in main path only
- Alternative paths (core rotation, variety, fallback) bypass limit
- Result: Limit not enforced across ALL scenarios

### ✅ BEST PRACTICE: Filter ALL Paths

```python
def apply_limit_filters(poi_list: List[Dict], context: Dict) -> List[Dict]:
    """
    Applies ALL active limits to POI list.
    
    USAGE: Call this function on EVERY candidate list before selection,
    regardless of code path (main loop, core rotation, variety, fallback).
    
    Args:
        poi_list: List of POI candidates
        context: Tracking context with counters and limits
    
    Returns:
        Filtered list with limits enforced
    """
    filtered = poi_list.copy()
    
    # Filter 1: Termy limit
    if context["termy_count"] >= context["max_termy"]:
        filtered = [p for p in filtered if not is_termy_spa(p)]
        print(f"[FILTER] Termy limit reached ({context['termy_count']}/{context['max_termy']}), excluded termy")
    
    # Filter 2: Trail limit
    if context["trail_count"] >= context["max_trails"]:
        filtered = [p for p in filtered if not is_trail(p)]
        print(f"[FILTER] Trail limit reached ({context['trail_count']}/{context['max_trails']}), excluded trails")
    
    # Filter 3: Already visited
    filtered = [p for p in filtered if poi_id(p) not in context["used_poi_ids"]]
    
    return filtered


# MAIN LOOP - apply filters
candidates = apply_limit_filters(all_poi, context)
for poi in candidates:
    score = calculate_score(poi)
    # ... scoring logic

# CORE ROTATION - apply filters
rotation_pool = get_high_priority_poi()
rotation_pool = apply_limit_filters(rotation_pool, context)  # ✅ Filters applied
if rotation_pool:
    best = max(rotation_pool, key=lambda p: p["priority_level"])
    plan.append(best)

# VARIETY LOGIC - apply filters
variety_candidates = get_variety_candidates()
variety_candidates = apply_limit_filters(variety_candidates, context)  # ✅ Filters applied
if variety_candidates:
    best = random.choice(variety_candidates)
    plan.append(best)

# FALLBACK LOGIC - apply filters
fallback_pool = get_fallback_poi()
fallback_pool = apply_limit_filters(fallback_pool, context)  # ✅ Filters applied
if fallback_pool:
    best = fallback_pool[0]
    plan.append(best)
```

**Benefits:**
- ✅ Limits enforced on EVERY code path
- ✅ Single function to update when adding new limits
- ✅ Easy to test (mock one function)
- ✅ Clear logging of what was filtered

**Code Review Checklist:**

```
When adding new POI selection logic:

□ Identify ALL code paths that select POI (main, rotation, variety, fallback)
□ Verify apply_limit_filters() called BEFORE selection in each path
□ Check that filters use consistent detection (is_termy_spa(), is_trail())
□ Test with limit=0 to verify filtering works
□ Add logging to show which POI were excluded by which filter
□ Verify limits checked in SAME ORDER in all paths
```

---

## 📏 Duration Logic Order Pattern

### ❌ ANTI-PATTERN: Constraints Before Caps

```python
# Calculate desired duration
duration = calculate_gap(start, end)

# Check environmental constraint FIRST
if end_time_proposed > day_end:
    duration = day_end - start  # ⚠️ Can be >60 min!

# Apply business cap SECOND (TOO LATE!)
duration = min(duration, 60)  # ❌ Already overridden by day_end
```

**Problem:**
- day_end constraint can override business cap
- If gap to day_end = 120 min, duration = 120 (not 60!)
- Cap becomes useless

### ✅ BEST PRACTICE: Caps First, Then Constraints

```python
def calculate_capped_duration(
    duration_requested: int,
    hard_cap: int,
    day_end_min: Optional[int],
    current_min: int,
    min_threshold: int = 5
) -> int:
    """
    Calculates duration with proper order: hard cap → constraints → threshold.
    
    Order matters:
    1. Business rule cap (MUST be enforced)
    2. Environmental constraints (day_end, etc.)
    3. Minimum threshold (quality check)
    
    Args:
        duration_requested: Desired duration
        hard_cap: Business requirement max (e.g., 60 min)
        day_end_min: End of day in minutes (constraint)
        current_min: Current time in minutes
        min_threshold: Minimum viable duration
    
    Returns:
        Capped duration respecting all rules in correct order
    """
    # STEP 1: Apply business rule cap (ALWAYS FIRST)
    duration = min(duration_requested, hard_cap)
    
    # STEP 2: Apply environmental constraints (SECOND)
    if day_end_min:
        max_until_day_end = day_end_min - current_min
        duration = min(duration, max_until_day_end)
    
    # STEP 3: Apply minimum threshold (LAST)
    if duration < min_threshold:
        return 0  # Signal that duration too short
    
    return duration


# Usage example:
duration = calculate_capped_duration(
    duration_requested=gap_to_end,  # Could be 180 min
    hard_cap=60,                     # Business rule: max 60 min
    day_end_min=day_end_min,         # Constraint: don't exceed day_end
    current_min=now
)

if duration > 0:
    add_free_time(now, duration)
```

**Rule of Thumb:**

```
Priority order (high → low):
1. Hard business caps (60 min for free_time) - NEVER override
2. Environmental constraints (day_end, accommodation_start) - Can reduce, not increase
3. Quality thresholds (min 5 min duration) - Final validation
```

**Code Review Checklist:**

```
When reviewing duration calculation logic:

□ Hard cap applied FIRST (before any constraints)
□ Hard cap uses min(), not conditional assignment
□ Environmental constraints applied SECOND
□ Constraints also use min() (reduce only, never increase)
□ Minimum threshold checked LAST
□ Return 0 or None if duration below threshold (don't create invalid item)
□ Test with large gap (>120 min) to verify cap enforced
```

---

## 🔍 Comprehensive Code Search Pattern

### ❌ ANTI-PATTERN: Assume One Location

```python
# Developer thinks: "I'll fix free_time cap in plan_service.py"

# plan_service.py - Fixed ✅
gap_duration = min(gap, 60)

# Test result: ❌ Still failing - 120 min blocks found!

# Why? ENGINE also creates free_time with different cap!
```

**Problem:**
- Assumption that one location handles all cases
- No systematic search for all relevant code
- Incomplete fix

### ✅ BEST PRACTICE: Systematic Search

**Step 1: Find ALL item creation locations**

```bash
# Search for item type creation
grep_search: '"type": "free_time"'  # Engine (dict format)
grep_search: 'FreeTimeItem('         # Service (Pydantic format)

# Results: 8 matches in engine, 6 matches in service
# Total: 14 locations creating free_time!
```

**Step 2: Review EACH location**

```python
# Create checklist for each location:
locations = [
    {"file": "engine.py", "line": 476, "context": "validation", "cap": None},
    {"file": "engine.py", "line": 3212, "context": "gap filling", "cap": 120},
    {"file": "engine.py", "line": 3801, "context": "after culture", "cap": 120},
    {"file": "engine.py", "line": 4002, "context": "end-of-day", "cap": 180},
    {"file": "plan_service.py", "line": 1290, "context": "small gap", "cap": None},
    {"file": "plan_service.py", "line": 1552, "context": "main gap", "cap": 60},
    {"file": "plan_service.py", "line": 1679, "context": "post-dinner", "cap": 90},
    # ... etc
]

# Fix EACH location that doesn't match requirement (60 min)
```

**Step 3: Verify consistency**

```python
# After fixes, verify all locations use same cap:
for location in locations:
    assert location["cap"] == 60, f"Inconsistent cap at {location['file']}:{location['line']}"
```

**Search Pattern Template:**

```python
def find_all_item_creation_locations(item_type: str) -> List[Dict]:
    """
    Systematically finds ALL code locations creating specific item type.
    
    Returns list of locations with file, line, context, current logic.
    """
    locations = []
    
    # Search 1: Dict format (engine layer)
    dict_pattern = f'"type": "{item_type}"'
    dict_matches = grep_search(dict_pattern, include_pattern="app/domain/")
    locations.extend(parse_matches(dict_matches, "engine"))
    
    # Search 2: Pydantic format (service layer)
    pydantic_class = f"{item_type.title().replace('_', '')}Item("
    pydantic_matches = grep_search(pydantic_class, include_pattern="app/application/")
    locations.extend(parse_matches(pydantic_matches, "service"))
    
    # Search 3: Function calls (helper utilities)
    helper_pattern = f"create_{item_type}"
    helper_matches = grep_search(helper_pattern)
    locations.extend(parse_matches(helper_matches, "helper"))
    
    return locations
```

**Code Review Checklist:**

```
When fixing duration/limit issues:

□ Use grep_search to find ALL relevant code locations
□ Search both dict format and Pydantic format
□ Check both engine layer and service layer
□ Create spreadsheet/checklist of all locations found
□ Review each location for consistency
□ Fix ALL locations, not just obvious one
□ After fixes, search again to verify no missed locations
□ Add comment to each location referencing FIX number for traceability
```

---

## 🧪 Testing Pattern: Comprehensive Before & After

### ❌ ANTI-PATTERN: Test Only Happy Path

```python
# Test 1: Normal scenario
response = call_api(test_01.json)
assert "days" in response  # ✅ PASS

# Developer: "Looks good, ship it!"

# Klientka: "free_time has 120 min blocks!" ❌
```

**Problem:**
- Only tested that plan generates
- Didn't verify duration caps
- Didn't check edge cases (end-of-day gaps, post-dinner, etc.)

### ✅ BEST PRACTICE: Comprehensive Validation

```python
def test_free_time_caps_comprehensive(test_file: str, max_cap: int = 60):
    """
    Comprehensive test for free_time duration caps.
    
    Validates:
    - No free_time block exceeds max_cap
    - Cap enforced in all scenarios (gaps, post-dinner, end-of-day)
    - Logs all violations with context (day, time, duration)
    
    Returns:
        (pass: bool, violations: List[Dict], max_found: int)
    """
    response = generate_plan(test_file)
    violations = []
    max_found = 0
    
    for day in response["days"]:
        for item in day["items"]:
            if item["type"] == "free_time":
                duration = item["duration_min"]
                
                # Track max duration found
                if duration > max_found:
                    max_found = duration
                
                # Check for violations
                if duration > max_cap:
                    violations.append({
                        "day": day["day"],
                        "time": f"{item['start_time']}-{item['end_time']}",
                        "duration": duration,
                        "exceeds_by": duration - max_cap
                    })
    
    # Report results
    if violations:
        print(f"❌ FAIL: Found {len(violations)} free_time blocks exceeding {max_cap} min")
        for v in violations:
            print(f"  Day {v['day']}: {v['time']} = {v['duration']} min (exceeds by {v['exceeds_by']} min)")
    else:
        print(f"✅ PASS: All free_time blocks ≤{max_cap} min (max found: {max_found} min)")
    
    return len(violations) == 0, violations, max_found


# Comprehensive test suite
def test_all_problems():
    """Tests all 7 klientka problems."""
    results = {
        "problem_1": test_trail_lunch_timing(),
        "problem_2": test_no_day_start_free_time(),
        "problem_3": test_end_of_day_gaps(),
        "problem_4": test_termy_limit(),
        "problem_5": test_no_technical_buffers(),
        "problem_6": test_trail_limit(),
        "problem_7": test_free_time_caps_comprehensive("test-01.json", max_cap=60),
    }
    
    all_pass = all(results.values())
    
    if all_pass:
        print("🎉 ALL 7 PROBLEMS RESOLVED!")
    else:
        print("⚠️ SOME PROBLEMS STILL EXIST")
        for problem, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {problem}: {status}")
    
    return all_pass
```

**Test Coverage Checklist:**

```
For duration cap testing:

□ Test with small gap (<60 min) - should use full gap
□ Test with medium gap (60-120 min) - should cap at 60
□ Test with large gap (>120 min) - should cap at 60
□ Test end-of-day scenario (gap to 19:00)
□ Test post-dinner scenario (after 18:00)
□ Test validation scenario (time continuity fix)
□ Verify MAX duration found (not just pass/fail)
□ Log ALL violations with context (day, time, duration)
□ Test across multiple days (multi-day consistency)
□ Test different profiles (family_kids, mountain_hiking, culture_food)
```

---

## 📝 Documentation Pattern: Traceability

### ❌ ANTI-PATTERN: No Context in Code

```python
# Code change with no documentation
free_duration = min(60, gap)  # ❌ Why 60? When added? By whom?
```

**Problem:**
- Future developer doesn't know why 60
- Can't find related fixes or issues
- Might change to 90 thinking it's optimization

### ✅ BEST PRACTICE: Traceable Comments

```python
# CRITICAL FIX (01.05.2026): Changed cap from 120 to 60 min (CLIENT FEEDBACK - Problem #7)
# Client requirement: All free_time blocks must be ≤60 min
# Root cause: Multiple cap values (120, 180, uncapped) across 6 locations
# Solution: Apply consistent 60 min cap to ALL free_time creation paths
# Related: FIX #4, FIX #9, FIX #17
# Commit: 811e4aa
# Test: response-ALL-7-PROBLEMS-FINAL.json shows max=60 min ✅
free_duration = min(60, gap_duration, end - now)
```

**Comment Template:**

```python
# [FIX TYPE] ([DATE]): [WHAT CHANGED] ([WHY])
# [Requirement/Context]
# Root cause: [Root cause explanation]
# Solution: [Solution approach]
# Related: [Related FIX numbers, issues, PRs]
# Commit: [Commit hash]
# Test: [Test file/result that validates fix]
[CODE]
```

**Commit Message Template:**

```
[SEVERITY]: [Summary] - [Details] (Problem #X)

Root cause: [Detailed explanation of root cause]

Solutions:
[File 1]:
- Line X: [location] - [change description]
- Line Y: [location] - [change description]

[File 2]:
- Line X: [location] - [change description]

Result: [What's fixed] ✅
Test: [Test that validates] ✅

Resolves: [Issue/Feedback reference]
Related: [Related FIX numbers]
```

**Benefits:**
- ✅ Future developers understand WHY
- ✅ Easy to find related changes (grep for FIX #X)
- ✅ Can trace back to commit and test results
- ✅ Prevents accidental reversion ("Why 60? Let's make it configurable!")

---

## 🚀 Pre-Commit Checklist

Before committing duration/limit changes:

```
Code Quality:
□ All constants extracted to top of file (FREE_TIME_MAX_DURATION_MIN = 60)
□ All creation locations use same cap value
□ Comments added at each location with FIX reference
□ Logic order correct (cap → constraints → threshold)
□ State updates before continue/break

Testing:
□ Comprehensive test run (all 7 problems)
□ Edge cases tested (end-of-day, post-dinner, validation)
□ Max duration logged and verified
□ Test with multiple profiles (family_kids, mountain_hiking, etc.)
□ Previous tests still pass (no regression)

Documentation:
□ Code comments include date, reason, FIX number
□ Commit message follows template
□ Test results referenced in commit message
□ Related issues/FIX numbers linked

Deployment:
□ Changes pushed to origin/main
□ All tests passing on remote
□ Client notified if ready for testing
```

---

## 📚 Additional Resources

**Related Documents:**
- `LESSONS_LEARNED_PROBLEM7_FREE_TIME_CAPS_01_05_2026.md` - Detailed investigation
- `QUICK_REFERENCE_FIXES_01_05_2026.md` - All 4 problems fixed today
- `CLIENT_FEEDBACK_30_01_2026.md` - Original 7 problems from client

**Code Locations:**
- `app/domain/planner/engine.py` - Core planning algorithm
- `app/application/services/plan_service.py` - Service orchestration
- `app/api/mappers/trip_mapper.py` - Request mapping

**Test Files:**
- `Testy_Klientki/test-01.json` - family_kids profile test
- `Testy_Klientki/response-ALL-7-PROBLEMS-FINAL.json` - Validated response

---

**Prevention Guide created:** 01.05.2026  
**Next review:** When adding new item types or duration logic  
**Maintenance:** Update when new patterns discovered
