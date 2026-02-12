# 🧠 ETAP 2 - CONTEXT MEMORY (START)

**Data utworzenia:** 11.02.2026  
**Status:** Pre-implementation (plan gotowy)  
**Start implementation:** 12.02.2026  
**Deadline:** 12.03.2026 (3 tygodnie)

---

## 📋 KLUCZOWE USTALENIA Z KLIENTKĄ

### **Decision Timeline:**
- **08.02.2026:** Klientka wysłała zakres Etap 2 (multi-day, versioning, editing, monetization)
- **10.02.2026:** Przesłano ofertę 9k PLN z 4 opcjami
- **10.02.2026:** Klientka zadała 4 pytania clarification (reorder? diff? regeneracja? timeline?)
- **10.02.2026:** Odpowiedziano punkt po punkcie
- **11.02.2026:** Klientka zaakceptowała **OPCJA 1: MVP (9k PLN)**

### **Finalna decyzja klientki (11.02.2026):**
✅ **W ZAKRESIE (9k PLN):**
- Multi-day planning (2-7 dni)
- FILL_GAP / SMART_REPLACE / Regenerate range z pinned items
- Versioning (snapshot + rollback + lista wersji)
- Editing MVP (remove + replace + full reflow)
- PostgreSQL migration
- Quality scoring + Explainability

❌ **DEFER DO PHASE 3:**
- Reorder (drag & drop) → "zostawmy jako opcję rozszerzenia po Etapie 2, jeśli zobaczymy że UX tego mocno potrzebuje"
- Visual diff → "możemy na razie odłożyć - rollback + historia wersji wystarczą"
- Lunch flexibility
- Real Stripe integration
- PDF generation
- Email delivery
- Advanced auth

### **Timeline Decision:**
- Oryginalnie: 7 tygodni (mid-Feb → early April)
- **User zmienił na: 3 TYGODNIE** (2 tyg dev + 1 tyg poprawki)
- **Target: 12.03.2026**

---

## 🎯 SCOPE ETAP 2 - DETAILED

### **1. Multi-day Planning**
**Cel:** Umożliwić planowanie 2-7 dniowych wycieczek

**Implementacja:**
- Nowa funkcja `plan_multiple_days()` w `engine.py`
- Cross-day POI tracking (unikaj duplikatów między dniami)
- Core POI rotation across days (nie wszystkie core w Day 1)
- Day-to-day energy management (reset energy każdego dnia, ale pamiętaj累積疲労)
- Day vibe calculation (łącz adventure + relaxation w smart sposób)

**Test scenarios:**
- 1-day plan → stary `build_day()` (Etap 1 bez zmian)
- 3-day plan → unique POI każdego dnia, sensowna dystrybucja
- 7-day plan → full week, energy balance, core rotation

**API:**
- `POST /plan/preview` już istnieje, update logic inside
- `trip_length.days` = 1-7 (walidacja)

---

### **2. Editing System**

#### **2.1 Remove Item**
**Cel:** Usuń POI z dnia, wypełnij gap, przelicz czasy

**Flow:**
1. Remove item from day_plan
2. Mark POI on avoid_cooldown list (default 24h)
3. Attempt gap fill (soft attraction lub free time)
4. Recalculate wszystkie czasy (reflow)
5. Save as new version

**API:**
- `POST /plans/{id}/days/{day}/remove`
- Request: `{item_id, avoid_cooldown_hours}`

#### **2.2 Replace Item**
**Cel:** Zamień POI na podobny

**Strategies:**
- `SMART_REPLACE` (default): podobna kategoria, vibes, target_group
- `RANDOM`: losowy z dostępnych
- `MANUAL`: user podaje poi_id

**Flow:**
1. Remove old POI
2. Find similar POI (similarity scoring)
3. Insert at same time slot (adjust if duration differs)
4. Recalculate times (reflow)
5. Save as new version

**API:**
- `POST /plans/{id}/days/{day}/replace`
- Request: `{item_id, strategy, manual_poi_id?}`

#### **2.3 Regenerate Time Range**
**Cel:** Re-plan fragment dnia, keep pinned items

**Flow:**
1. Extract items w zakresie `from_time` - `to_time`
2. Mark pinned_items as locked (don't touch)
3. Run mini-planning dla fragmentu (use `build_day` logic)
4. Merge: before_range + new_fragment + after_range
5. Recalculate wszystkie czasy (global reflow)
6. Save as new version

**API:**
- `POST /plans/{id}/days/{day}/regenerate`
- Request: `{from_time, to_time, pinned_items: [id1, id2]}`

---

### **3. Versioning System**

**Cel:** Track history, umożliw rollback

**Database schema:**
```
plan_versions:
  - id (UUID)
  - plan_id (FK → plans.id)
  - version_number (INT, auto-increment per plan)
  - days_json (JSONB, full snapshot)
  - created_at (TIMESTAMP)
  - change_type (ENUM: initial, regenerated, edited, rollback)
  - parent_version_id (UUID, nullable)
```

**Operations:**
- **save_version:** Po każdej zmianie → nowy rekord
- **list_versions:** GET wszystkie wersje dla plan_id
- **get_version:** GET konkretną wersję (full snapshot)
- **rollback:** Copy old version → create as new version

**API:**
- `GET /plans/{id}/versions` → array of version metadata
- `GET /plans/{id}/versions/{num}` → full days_json
- `POST /plans/{id}/rollback` → {to_version: 3} → creates version #(next)

**NIE MA:**
- Visual diff (comparison "co się zmieniło")
- Smart merge (conflict resolution)

---

### **4. Quality + Explainability**

**Cel:** Powiedz userowi DLACZEGO dane POI zostało wybrane

#### **4.1 Quality Checker**
**File:** `app/domain/planner/quality_checker.py`

**Badges:**
- `has_must_see` → dzień ma POI z must_see > 80
- `good_variety` → diverse categories (nie same muzea)
- `realistic_timing` → czasy są achievable (no rush)
- `core_attraction` → ma core POI (priority_level=12)
- `premium_experience` → ma premium POI (KULIGI, SPA)

**API extension:**
- `DayPlan.quality_badges: List[str]`

#### **4.2 Explainability Service**
**File:** `app/domain/planner/explainability.py`

**Logic:**
1. Parse `score_breakdown` (z engine.py)
2. Convert to natural language
3. Pick top 3 reasons

**Examples:**
- "Must-see attraction" (must_see > 80)
- "Perfect for couples" (target_group match)
- "Great for hiking lovers" (travel_style bonus > 20)
- "Optimal time for this activity" (time_of_day score > 15)
- "Weather-appropriate" (weather_fit > 10)

**API extension:**
- `AttractionItem.why_selected: List[str]`
- `AttractionItem.quality_badges: List[str]`

---

### **5. PostgreSQL Migration**

**Cel:** Przejście z in-memory na PostgreSQL

**Setup:**
- Docker / lokalna instalacja PostgreSQL
- Database: `travel_planner_dev` (dev), `travel_planner_prod` (prod)
- Alembic dla migracji

**Tables:**
```sql
-- Plans table
CREATE TABLE plans (
  id UUID PRIMARY KEY,
  location VARCHAR(255) NOT NULL,
  group_type VARCHAR(50),
  days_count INT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB
);

-- Plan versions
CREATE TABLE plan_versions (
  id UUID PRIMARY KEY,
  plan_id UUID REFERENCES plans(id),
  version_number INT NOT NULL,
  days_json JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  change_type VARCHAR(50),
  parent_version_id UUID REFERENCES plan_versions(id),
  UNIQUE(plan_id, version_number)
);

-- Optional: POI cache
CREATE TABLE poi_cache (
  id UUID PRIMARY KEY,
  location VARCHAR(255),
  poi_data JSONB,
  updated_at TIMESTAMP DEFAULT NOW()
);
```

**Migration approach:**
1. Create SQLAlchemy models
2. Update repository interfaces (same methods, different implementation)
3. Test Etap 1 features (zero regressji)
4. Deploy

**Rollback plan:**
- Keep in-memory repositories as backup
- Feature flag dla DB enable/disable

---

### **6. Regeneration Features**

#### **6.1 FILL_GAP (już działa - Etap 1)**
**File:** `app/domain/planner/engine.py` (lines 1154, 1194, 1246-1247)

**Logic:**
- Po hard attractions, szukaj luk >40 min
- Wypełnij soft attractions (museums, cafes, viewpoints)
- Jeśli brak soft → free_time

**Status:** ✅ Działa w Etap 1, zachować

#### **6.2 SMART_REPLACE (nowe - Etap 2)**
**File:** `app/application/services/plan_editor.py` lub `similarity.py`

**Logic:**
1. Analyze removed POI:
   - Category (nature, culture, food, adventure)
   - Target groups
   - Intensity level
   - Duration
   - Vibes (relaxing, exciting, romantic)
2. Find candidates:
   - Same location
   - Not on avoid_cooldown list
   - Match time_of_day constraints
3. Score similarity:
   - Category match: 30%
   - Target group match: 25%
   - Intensity match: 20%
   - Duration match: 15%
   - Vibes match: 10%
4. Pick top match

**Fallback:** Jeśli brak good match (score <50%) → random lub gap

#### **6.3 Regenerate Range (nowe - Etap 2)**
**Flow:**
1. Parse time range (from_time, to_time)
2. Extract current items in range
3. Keep pinned_items (locked = true)
4. Remove non-pinned items
5. Run mini-planning:
   - Available POI = pool - used_in_other_days - avoid_cooldown
   - Time budget = to_time - from_time - pinned_duration
   - Constraints = same as initial planning
6. Insert new POI around pinned items
7. Merge: before + regenerated_fragment + after
8. Global reflow (recalculate all times)

**Edge cases:**
- Pinned items kolidują czasowo → error "Cannot regenerate, pinned items overlap"
- Time range = cały dzień → re-plan całego dnia
- Brak POI do wypełnienia → free_time slots

---

## ⚠️ CRITICAL: ZACHOWAĆ ETAP 1

### **Features które MUSZĄ działać po zmianach:**

#### **1. Premium Experience (KULIGI)**
- File: `app/domain/planner/scoring/budget.py`
- Function: `calculate_premium_penalty(poi, budget_level)`
- Penalties:
  - Budget = 1 → penalty -40
  - Budget = 2 → penalty -20
  - Budget >= 3 → penalty 0
- Test: `test_premium_experience.py` (5/5 PASS)

#### **2. Core POI Rotation**
- File: `app/domain/planner/engine.py`
- Function: `is_core_poi(poi)` + rotation logic
- Logic: Random selection from top 5 core attractions (priority_level=12)
- Test: `test_core_rotation.py` (5 unique POI w 10 runs)

#### **3. Single-day Planning**
- File: `app/domain/planner/engine.py`
- Function: `build_day(pois, user, context)`
- Scoring: 15+ modules (budget, family_fit, crowd, intensity, preferences, travel_style, weather, etc.)
- Filters: Hard (seasonality, target_group, intensity) + Soft (budget, crowd)
- Gap filling: >40 min luki wypełnione
- Energy management: realistic energy tracking

#### **4. API Contracts**
- Endpoint: `POST /plan/preview`
- Input: `TripInput` (location, group, trip_length, budget, preferences, travel_style)
- Output: `PlanResponse` (days[], metadata)
- Item types: day_start, parking, transit, attraction, lunch_break, free_time, day_end

### **Regression Testing Strategy:**
- Po każdej zmianie → run `test_premium_experience.py` + `test_core_rotation.py`
- Before merge → full regression suite
- Before production deploy → E2E test Etap 1 scenarios

---

## 📊 PROGRESS TRACKING

### **Daily Log Format:**
```
## Day X (DD.MM.YYYY) - [Task Name]

**Planned:**
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

**Completed:**
- [x] Task 1 ✅
- [x] Task 2 ✅
- [ ] Task 3 ⏳ (in progress, 60% done)

**Blockers:**
- 🐛 Bug in X function (investigating)
- ⏰ Task Y taking longer (need +2h)

**Commits:**
- abc1234: "feat: implement X"
- def5678: "test: add tests for Y"

**Notes:**
- Discovered edge case Z, handling tomorrow
- Performance concern in function W, needs optimization

**Tomorrow:**
- [ ] Finish Task 3
- [ ] Start Task 4
- [ ] Fix bug in X
```

### **Weekly Report Format (for klientka):**
```
## Tydzień X: DD-DD.MM.2026

**Completed:**
- ✅ Feature A (implemented + tested)
- ✅ Feature B (60% done, on track)

**In Progress:**
- 🔄 Feature C (blocked on Y, workaround found)

**Blockers:**
- None / [describe if any]

**Next Week:**
- Feature D (estimated 3 days)
- Feature E (estimated 2 days)

**Risks:**
- None / [describe if timeline at risk]

**Demo:**
- [Link to Swagger / screenshots / video]
```

---

## 🚀 IMPLEMENTATION PRIORITY

### **Week 1 Priority (Must-have dla core functionality):**
1. **PostgreSQL setup** - foundation dla versioning
2. **Repository migration** - zachować Etap 1
3. **Multi-day planning** - core feature Etap 2
4. **Versioning system** - enable editing workflow
5. **Quality + Explainability** - user value

### **Week 2 Priority (Must-have dla editing):**
1. **Editing core logic** - remove + replace + reflow
2. **Editing API** - endpoints + versioning integration
3. **Regenerate range** - pinned items logic
4. **SMART_REPLACE** - similarity matching
5. **Integration testing** - E2E scenarios

### **Week 3 Priority (Stabilizacja + deployment):**
1. **Comprehensive testing** - unit + integration + performance
2. **Bugfixes** - edge cases + error handling
3. **Deployment prep** - Render config + DB setup
4. **UAT with klientka** - feedback + iterations
5. **Production deployment** - go live

---

## 🔗 KEY FILES TO TRACK

### **Implementation Files:**
- `app/domain/planner/engine.py` → multi-day planning logic
- `app/application/services/plan_editor.py` → editing operations
- `app/application/services/similarity.py` → SMART_REPLACE logic
- `app/domain/planner/quality_checker.py` → quality badges
- `app/domain/planner/explainability.py` → why_selected reasons
- `app/infrastructure/database/models.py` → SQLAlchemy ORM
- `app/infrastructure/repositories/plan_repository.py` → PostgreSQL repo
- `app/infrastructure/repositories/plan_version_repository.py` → versioning repo
- `app/api/routes/plan.py` → API endpoints (editing, versioning)

### **Test Files:**
- `tests/test_multi_day_planning.py` → multi-day logic tests
- `tests/test_plan_editor.py` → editing tests
- `tests/test_versioning.py` → versioning tests
- `tests/test_regenerate_range.py` → regeneration tests
- `tests/test_smart_replace.py` → similarity tests
- `tests/test_premium_experience.py` → Etap 1 regression (MUST PASS)
- `tests/test_core_rotation.py` → Etap 1 regression (MUST PASS)

### **Documentation Files:**
- `ETAP2_PLAN_DZIALANIA.md` → ten dokument (master plan)
- `ETAP2_PROGRESS.md` → daily log (create on Day 1)
- `ETAP2_FEATURES.md` → feature guide (create on Day 11-12)
- `ETAP2_UAT_FEEDBACK.md` → UAT results (create on Day 19-20)
- `README.md` → update z Etap 2 instructions

### **Configuration Files:**
- `alembic/versions/` → DB migrations
- `requirements.txt` → add psycopg2-binary, alembic
- `.env` → DATABASE_URL variable
- `render.yaml` / Render dashboard → deployment config

---

## 🎯 DEFINITION OF DONE (12.03.2026)

### **Feature DoD:**
- [ ] Code implemented + committed
- [ ] Unit tests written + passing
- [ ] Integration test passing
- [ ] Etap 1 regression tests passing
- [ ] Documented (docstrings + README)
- [ ] Code reviewed (self-review checklist)
- [ ] Deployed to staging + smoke tested

### **Etap 2 DoD:**
- [ ] All must-have features complete
- [ ] Test coverage >80%
- [ ] Zero critical bugs
- [ ] Etap 1 features working (100% regression pass)
- [ ] API response time <2s (7-day plan)
- [ ] DB query time <500ms
- [ ] Deployed to production
- [ ] UAT approved by klientka
- [ ] Documentation complete (README + feature guide)
- [ ] Handoff materials ready (video + guidelines)

---

## 📞 STAKEHOLDERS

**Developer (Mateusz):**
- Email: ngencode.dev@gmail.com
- Role: Implementation + testing + deployment
- Responsibility: Deliver Etap 2 by 12.03.2026

**Client (Karolina):**
- Role: Product owner + UAT tester
- Involvement: UAT (02-03.03), feedback, final approval
- Decision maker: Phase 3 scope, timeline extensions

**End Users:**
- Role: Travel planners using the app
- Involvement: Post-launch feedback (Phase 3+)

---

## ✅ NEXT STEPS

1. **Dzisiaj (11.02):**
   - [x] Plan działania gotowy ✅
   - [x] Context memory zapisany ✅
   - [ ] User review planu (czy coś zmienić?)

2. **Jutro (12.02) - Day 1:**
   - [ ] PostgreSQL setup lokalnie
   - [ ] Alembic init + pierwsza migracja
   - [ ] Test connection
   - [ ] Create `ETAP2_PROGRESS.md` (daily log start)

3. **Weekly (every Friday):**
   - [ ] Send report do Karoliny
   - [ ] Review progress vs plan
   - [ ] Adjust timeline if needed

---

**Status:** 🟢 READY TO START  
**Confidence Level:** 🟢 HIGH (plan is realistic, scope is clear, Etap 1 stable)  
**Risk Level:** 🟡 MEDIUM (3 tyg to aggressive, ale doable if prioritize ruthlessly)

---

## 🧠 MEMORY CHECKPOINT

**Co zapamiętać:**
1. Etap 1 MUSI działać po zmianach (test_premium_experience + test_core_rotation)
2. Reorder + Visual diff + Stripe + PDF + Email → Phase 3 (nie teraz)
3. Klientka zaakceptowała MVP 9k PLN, nie rozszerzenia
4. Timeline: 3 tygodnie (12.02 → 12.03.2026)
5. FILL_GAP już działa (Etap 1), SMART_REPLACE + Regenerate to dodam (Etap 2)
6. Versioning: snapshot + rollback TAK, visual diff NIE
7. Editing: remove + replace TAK, reorder NIE
8. Multi-day: 2-7 dni, cross-day tracking, core rotation
9. PostgreSQL: migration must preserve Etap 1 behavior
10. Daily commits, weekly reports, UAT day 19-20

**Następna akcja:** 12.02.2026 (jutro) → PostgreSQL Setup (Day 1)

---

END OF CONTEXT MEMORY
