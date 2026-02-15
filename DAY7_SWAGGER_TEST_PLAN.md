# Day 7 - Editing API Endpoints - Test Plan

## ✅ Implementation Complete

**Date:** 18.02.2026  
**Feature:** Editing API endpoints with versioning

### Implemented

1. **Request Models** (in `app/api/routes/plan.py`)
   - `RemoveItemRequest(item_id: str, avoid_cooldown_hours: int = 24)`
   - `ReplaceItemRequest(item_id: str, strategy: str = "SMART_REPLACE", preferences: Dict[str, Any] = {})`

2. **API Endpoints**
   - `POST /plans/{plan_id}/days/{day_number}/remove` - Remove item + auto gap fill + save version
   - `POST /plans/{plan_id}/days/{day_number}/replace` - Replace item with SMART_REPLACE + save version

3. **Full Flow Implemented**
   - ✅ Load current plan from database
   - ✅ Apply edit (remove/replace) using PlanEditor service
   - ✅ Recalculate times automatic via reflow
   - ✅ Save as new version with change tracking
   - ✅ Return updated plan in response

4. **Error Handling**
   - 404: Plan not found
   - 400: Invalid day_number
   - 500: Internal server errors with detailed messages

5. **Version Tracking Integration**
   - Automatic version creation on each edit
   - Change type: "remove_item" or "replace_item"
   - Change summary: Descriptive text with item_id and day_number

---

## 🧪 Swagger Test Scenarios

### Prerequisites

1. Start development server:
   ```powershell
   cd "travel-planner-backend"
   .venv\Scripts\Activate.ps1
   uvicorn app.api.main:app --reload --port 8001
   ```

2. Open Swagger UI:
   ```
   http://localhost:8001/docs
   ```

3. Verify database connection (check .env file has correct DATABASE_URL)

---

### 📋 Test Scenario 1: Generate 3-Day Plan

**Endpoint:** `POST /plans/preview`

**Payload:**
```json
{
  "days": 3,
  "season": "winter",
  "visitor": {
    "age_group": "adults",
    "target_group": "couples",
    "physical_fitness": "active",
    "budget_level": 2,
    "interests": ["hiking", "culture", "nature"],
    "preferences": {
      "pace": "moderate",
      "kids_focused": false
    }
  },
  "context": {
    "weather": "sunny",
    "temperature": 5,
    "is_weekend": false,
    "constraints": {
      "start_time": "09:00",
      "end_time": "18:00",
      "max_daily_budget": 300
    }
  }
}
```

**Expected Result:**
- 3 days with unique POIs
- Core rotation working (Morskie Oko not always in Day 1)
- Premium penalties applied (KULIGI with penalty for budget=2)
- Version #1 created automatically

**What to verify:**
- Response status: 200 OK
- `plan.plan_id` exists (save this for next tests!)
- `plan.days` array has 3 elements
- Each day has items with `poi_id`, `start_time`, `end_time`
- No duplicate `poi_id` across all days

---

### 📋 Test Scenario 2: Remove Morskie Oko

**Endpoint:** `POST /plans/{plan_id}/days/1/remove`

Replace `{plan_id}` with the ID from Test 1.

**Payload:**
```json
{
  "item_id": "MORSKIE_OKO",
  "avoid_cooldown_hours": 24
}
```

**Expected Result:**
- Morskie Oko removed from Day 1
- Gap automatically filled with alternative POI
- Times recalculated (reflow)
- New version #2 created
- Response shows updated Day 1

**What to verify:**
- Response status: 200 OK
- Day 1 no longer contains "MORSKIE_OKO"
- Day 1 still has POIs (gap filled)
- Start/end times are consistent
- Version #2 exists (check `/plans/{plan_id}/versions` endpoint)

**If MORSKIE_OKO not in Day 1:**
Use any `poi_id` from Day 1 items instead.

---

### 📋 Test Scenario 3: Replace KULIGI

**Endpoint:** `POST /plans/{plan_id}/days/2/replace`

**Payload:**
```json
{
  "item_id": "KULIGI_ZAKOPANE",
  "strategy": "SMART_REPLACE",
  "preferences": {}
}
```

**Expected Result:**
- KULIGI replaced with similar premium POI (e.g., SPA, fine dining)
- Replacement matches: similar duration, similar category, fits budget
- Times recalculated
- Version #3 created

**What to verify:**
- Response status: 200 OK
- Day 2 no longer contains "KULIGI_ZAKOPANE"
- Replacement POI has similar characteristics (check duration, category)
- Version #3 exists with change_summary mentioning "Replaced item KULIGI_ZAKOPANE"

**If KULIGI not in Day 2:**
Use any premium POI from any day (check Day 1-3 for premium items).

---

### 📋 Test Scenario 4: Rollback to Version #1

**Endpoint:** `POST /plans/{plan_id}/rollback`

**Payload:**
```json
{
  "target_version": 1
}
```

**Expected Result:**
- Plan reverted to original state (version #1)
- All edits (remove + replace) undone
- New version #4 created (rollback itself creates version)

**What to verify:**
- Response status: 200 OK
- Response shows `"new_version_number": 4`
- Get plan again (`GET /plans/{plan_id}`) and verify:
  - Original POIs back (Morskie Oko if it was there, KULIGI if it was there)
  - Plan structure matches version #1

---

### 📋 Test Scenario 5: Version History

**Endpoint:** `GET /plans/{plan_id}/versions`

**Expected Result:**
- List of all versions (4 versions: #1, #2, #3, #4)

**What to verify:**
- Version #1: change_type="generated", change_summary="Initial plan generation"
- Version #2: change_type="remove_item", change_summary contains "Removed item"
- Version #3: change_type="replace_item", change_summary contains "Replaced item"
- Version #4: change_type="rollback", change_summary contains "Rolled back to version 1"
- Sorted by version_number DESC (newest first)

---

## 🐛 Known Issues / TODOs

1. **User preferences extraction:** Currently hardcoded in endpoints (couples, budget=2). Should extract from original plan metadata.

2. **Context extraction:** Season/weather hardcoded. Should be extracted from plan or inferred from current date.

3. **Error handling:** If POI not found in day, returns generic error. Could be more specific.

4. **SMART_REPLACE:** Basic implementation. Day 9 will enhance with category/vibes matching.

---

## 📝 Test Results

### Test 1: Generate 3-Day Plan
- [ ] Status: _____
- [ ] plan_id: _____________________________
- [ ] Issues: ____________________________

### Test 2: Remove Item
- [ ] Status: _____
- [ ] Removed POI: _________________________
- [ ] Gap filled: Yes / No
- [ ] Issues: ____________________________

### Test 3: Replace Item
- [ ] Status: _____
- [ ] Replaced POI: ________________________
- [ ] New POI: ____________________________
- [ ] Issues: ____________________________

### Test 4: Rollback
- [ ] Status: _____
- [ ] Rolled back successfully: Yes / No
- [ ] Issues: ____________________________

### Test 5: Version History
- [ ] Status: _____
- [ ] All 4 versions present: Yes / No
- [ ] Issues: ____________________________

---

## ✅ If All Tests Pass

1. No regressions (Etap 1 features still work)
2. Editing API working correctly
3. Versioning integrated properly
4. Ready for commit

**Next:** Day 8 - Regenerate Range with Pinned Items

---

## 📚 Related Files

- Implementation: `app/api/routes/plan.py` (lines 256-521)
- Core Logic: `app/application/services/plan_editor.py`
- Dependencies: `app/api/dependencies.py` (get_plan_editor)
- Version Repository: `app/infrastructure/repositories/plan_version_repository.py`

---

**Created:** 18.02.2026  
**Author:** GitHub Copilot (Day 7 Implementation)
