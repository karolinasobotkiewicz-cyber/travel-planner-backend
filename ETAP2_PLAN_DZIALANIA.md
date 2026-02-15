# 🎯 ETAP 2 - PLAN DZIAŁANIA (3 TYGODNIE)

**Start:** 12.02.2026 (środa)  
**Koniec:** 05.03.2026 (tydzień 2) + 12.03.2026 (tydzień 3 - poprawki)  
**Status:** 🟢 In Progress - Day 1 COMPLETED ✅  
**Deadline:** 12.03.2026  
**Last Updated:** 12.02.2026 11:52 AM

## 📊 PROGRESS TRACKER

- ✅ **Day 1 (12.02):** PostgreSQL Setup - COMPLETED
- ⏸️ **Day 2 (13.02):** Repository Migration - PENDING
- ⏸️ **Day 3 (14.02):** Multi-day Planning Core - PENDING

---

## 📋 ZAKRES ZAAKCEPTOWANY PRZEZ KLIENTKĘ (10-11.02.2026)

### ✅ MUST-HAVE (w 3 tygodnie):
- Multi-day planning (2-7 dni) z cross-day POI tracking
- FILL_GAP / SMART_REPLACE / Regenerate range z pinned items
- Versioning (snapshot + rollback + lista wersji)
- Editing MVP (remove + replace + full reflow)
- PostgreSQL migration
- Quality scoring + Explainability (why_selected, badges)

### 🔄 DEFER DO PHASE 3 (po 12.03):
- ❌ Reorder (drag & drop) - UX pokaże czy potrzebne
- ❌ Visual diff - rollback + historia wystarczy
- ❌ Lunch flexibility
- ❌ Stripe real integration - mock wystarczy na start
- ❌ PDF generation - defer do post-launch
- ❌ Email delivery - defer do post-launch
- ❌ Auth system - guest flow wystarczy na start

### ⚠️ KRYTYCZNE: ZACHOWAĆ ETAP 1
Wszystkie funkcje Etap 1 MUSZĄ działać po zmianach:
- ✅ Premium Experience (KULIGI penalties)
- ✅ Core POI rotation (priority_level=12)
- ✅ Single-day planning
- ✅ Scoring system (15+ modules)
- ✅ Hard filters (seasonality, target_group, intensity)
- ✅ Gap filling
- ✅ Energy management
- ✅ Opening hours validation

---

## 📅 TYDZIEŃ 1: FOUNDATION (12-16.02.2026)

### **Dzień 1 (Środa 12.02) - PostgreSQL Setup** ✅ COMPLETED

- [x] ~~Zainstaluj PostgreSQL lokalnie~~ → **Supabase Cloud (Europa/Frankfurt)**
- [x] Setup psycopg2-binary (v2.9.9) ✅
- [x] Zainstaluj Alembic dla migracji (v1.13.1) ✅
- [x] ~~Utwórz database lokalnie~~ → **Supabase: travel-planner-prod** ✅
- [x] Stwórz schema migrations w `alembic/versions/` ✅
- [x] Zdefiniuj tabele: ✅
  - `plans` (id UUID, location, group_type, days_count, budget_level, created_at, updated_at, trip_metadata JSON)
  - `plan_versions` (id UUID, plan_id FK, version_number UNIQUE per plan, days_json, created_at, change_type, parent_version_id, change_summary)
  - ~~`poi_cache`~~ → **Deferred (Excel loader wystarczy)**
- [x] Test connection + podstawowe INSERT/SELECT ✅
- [x] **BONUS:** PlanPostgreSQLRepository + PlanVersionRepository implemented ✅
- [x] **BONUS:** Health endpoint with DB check ✅
- [x] Commit: "feat(etap2): PostgreSQL setup - models, migrations, repositories" ✅

**✅ Output:** Database działa w produkcji (Render), tabele utworzone, connection pooler working

**⏱️ Time Spent:** ~8 hours (including troubleshooting IPv6/pooler issues)

**📝 NOTATKI - DZIEŃ 1:**

**🔧 TECHNICZNE DECYZJE:**
1. **Supabase zamiast lokalnego PostgreSQL** - łatwiejsze dla klientki, bez lokalnej instalacji
2. **Transaction Pooler (port 6543)** - IPv4 compatibility (Windows + Render nie wspierają IPv6)
3. **Manual migration execution** - Alembic autogenerate nie działało lokalnie przez brak IPv6
4. **SQLAlchemy 2.0.25 + NullPool** - serverless-friendly configuration dla Render Free
5. **dotenv loading w connection.py** - automatyczne ładowanie .env dla lokalnego developmentu

**❌ PROBLEMY NAPOTKANE:**
1. **IPv6 connectivity** - Direct connection (db.*.supabase.co:5432) nie działa na Windows/Render
   - **Rozwiązanie:** Transaction Pooler (aws-1-eu-west-1.pooler.supabase.com:6543)
2. **Pooler "Tenant not found" errors** - niepoprawny format username/password
   - **Rozwiązanie:** Format `postgres.{project_ref}:{password}@pooler:6543`
3. **ConfigParser interpolation error** - `%` w URL-encoded password konflikt z Alembic ini parser
   - **Rozwiązanie:** Używać `create_engine()` bezpośrednio w env.py zamiast `set_main_option()`
4. **SQLAlchemy reserved keywords** - `metadata` kolumna konflikt z `Base.metadata`
   - **Rozwiązanie:** Renamed to `trip_metadata`
5. **`__table_args__` syntax error** - defined as class instead of tuple
   - **Rozwiązanie:** `__table_args__ = (UniqueConstraint(...),)` not `class __table_args__:`

**✅ CO DZIAŁA:**
- Production health endpoint: `https://travel-planner-backend-xbsp.onrender.com/health`
- Response: `{"status":"ok","database":"connected","version":"2.0.0"}` ✅
- Tables in Supabase: `plans`, `plan_versions`, `alembic_version` ✅
- Connection string (working): `postgresql://postgres.usztzcigcnsyyatguxay:%40ManTrav%2197@aws-1-eu-west-1.pooler.supabase.com:6543/postgres`

**📂 PLIKI UTWORZONE:**
- `app/infrastructure/database/models.py` - Plan + PlanVersion ORM models
- `app/infrastructure/database/connection.py` - SQLAlchemy engine + session factory
- `app/infrastructure/database/__init__.py` - Module exports
- `app/infrastructure/repositories/plan_repository_postgresql.py` - PostgreSQL repository implementation
- `app/infrastructure/repositories/plan_version_repository.py` - Version management repository
- `alembic/` - Migration framework directory
- `alembic/versions/360e3cae0377_*.py` - Initial schema migration
- `migration_manual.sql` - Manual SQL for Supabase (executed ✅)
- `DZIEN_1_RAPORT_PROBLEMOW.md` - Troubleshooting documentation

**🚀 DEPLOYMENT:**
- GitHub: Pushed commit `566d10b` ✅
- Render: Auto-deployed, DATABASE_URL configured ✅
- Supabase: Tables created via SQL Editor ✅

**⚠️ KNOWN ISSUES:**
- RLS (Row Level Security) warnings w Supabase - **OK to ignore** (backend ma pełny dostęp przez credentials)
- Local connection nie działa (IPv6 issue) - **OK, rozwój będzie na Render/cloud**

**📚 LESSONS LEARNED:**
1. Zawsze sprawdzaj czy cloud provider wspiera IPv6 (większość free tiers = NIE)
2. Supabase pooler wymaga specyficznego formatu `postgres.{ref}:password@pooler:port`
3. URL-encoding hasła krytyczne dla connection strings (@→%40, !→%21)
4. ConfigParser w Pythonie ma issues z % characters (używać raw strings lub unikać set_main_option)
5. NullPool recommended dla serverless/short-lived connections (Render Free, Supabase pooler)

**🎯 GOTOWOŚĆ DO DAY 2:**
- ✅ Database ready
- ✅ Repositories implemented (PlanPostgreSQLRepository, PlanVersionRepository)
- ✅ Production deployment verified
- ✅ Health check passing
- ⏭️ **Next:** Integrate repositories with FastAPI endpoints (Day 2)

---

### **Dzień 2 (Czwartek 13.02) - Repository Migration**
- [ ] Backup istniejących repositories (in-memory)
- [ ] Utwórz `app/infrastructure/database/`
  - `connection.py` (SQLAlchemy engine setup)
  - `models.py` (SQLAlchemy ORM models)
- [ ] Update `PlanRepository`:
  - Zmień z in-memory dict na PostgreSQL
  - Zachowaj interface (metody save/get/list bez zmian)
  - Dependency injection via FastAPI Depends
- [ ] Update `POIRepository`:
  - Opcjonalnie cache zakopane.xlsx w DB
  - LUB zostaw Excel loader (szybsza implementacja)
- [ ] Test Etap 1 features:
  - `POST /plan/preview` musi działać identycznie
  - Premium Experience penalties працują
  - Core POI rotation працює
- [ ] Commit: "feat: migrate PlanRepository to PostgreSQL"

**Output:** Etap 1 działa z PostgreSQL, zero regressji

---

### **Dzień 3 (Piątek 14.02) - Multi-day Planning Core**
- [ ] Utwórz `plan_multiple_days()` w `engine.py`
  - Cross-day POI tracking (avoid duplicates)
  - Day-to-day energy management
  - Core POI distribution across days (nie wszystkie w Day 1)
- [ ] Update `PlanService.generate_plan()`:
  - Jeśli `trip_length.days > 1` → wywołaj `plan_multiple_days()`
  - Jeśli `days == 1` → stary `build_day()` (zachować Etap 1)
- [ ] Test cases:
  - 1-day plan = Etap 1 behavior (regression test)
  - 3-day plan = unique POI każdego dnia, core rotation
  - 7-day plan = sensowna dystrybucja, energy balance
- [ ] Commit: "feat: multi-day planning with cross-day tracking"

**Output:** Multi-day działa, Etap 1 bez zmian

---

### **Dzień 4 (Sobota 15.02) - Versioning System**
- [ ] Utwórz `PlanVersionRepository`:
  - `save_version(plan_id, days, change_type)` → nowy snapshot
  - `list_versions(plan_id)` → wszystkie wersje
  - `get_version(plan_id, version_num)` → konkretna wersja
  - `rollback_to_version(plan_id, version_num)` → restore as new
- [ ] API endpoints w `app/api/routes/plan.py`:
  - `GET /plans/{id}/versions` → lista wersji
  - `GET /plans/{id}/versions/{num}` → pełny snapshot
  - `POST /plans/{id}/rollback` → rollback + create new version
- [ ] Update `POST /plan/preview`:
  - Po wygenerowaniu planu → auto-save version #1
- [ ] Test:
  - Generate plan → version #1
  - Edit plan → version #2
  - Rollback to #1 → creates version #3 (copy of #1)
- [ ] Commit: "feat: plan versioning with snapshot + rollback"

**Output:** Versioning działa, rollback testowany

---

### **Dzień 5 (Niedziela 16.02) - Quality + Explainability**
- [ ] Utwórz `app/domain/planner/quality_checker.py`:
  - `validate_day_quality(day_plan)` → badges (has_must_see, good_variety, realistic_timing)
  - `check_poi_quality(poi, context, user)` → quality_badges per POI
- [ ] Utwórz `app/domain/planner/explainability.py`:
  - `explain_poi_selection(poi, score_breakdown, user)` → top 3 reasons
  - Parse score_breakdown → natural language
  - Przykład: ["Must-see attraction", "Perfect for couples", "Great for hiking lovers"]
- [ ] Extend API response models:
  - `AttractionItem` → add `why_selected: List[str]`, `quality_badges: List[str]`
  - `DayPlan` → add `quality_badges: List[str]`
- [ ] Test:
  - Generate plan → sprawdź `why_selected` fields
  - Verify badges logic (must_see, core_attraction, perfect_timing)
- [ ] Commit: "feat: quality scoring + explainability"

**Output:** Każdy POI ma `why_selected`, plany mają quality badges

---

## 📅 TYDZIEŃ 2: EDITING + REGENERATION (17-23.02.2026)

### **Dzień 6 (Poniedziałek 17.02) - Editing Core Logic**
- [ ] Utwórz `app/application/services/plan_editor.py`:
  - `remove_item(day_plan, item_id, avoid_cooldown_hours=24)`
  - `replace_item(day_plan, item_id, strategy="SMART_REPLACE")`
  - `_recalculate_times(day_plan)` → full reflow po edycji
  - `_attempt_gap_fill(day_plan, gap_start, gap_duration)` → fill removed item
- [ ] Logika SMART_REPLACE:
  - Znajdź POI z tej samej kategorii
  - Similar target_groups, intensity, duration
  - Respect `avoid_cooldown` (nie wstaw właśnie usuniętego)
- [ ] Test cases:
  - Remove POI → gap fill → czasy przeliczone
  - Replace POI → podobny wstawiony → sensowny match
- [ ] Commit: "feat: plan editing - remove + replace + reflow"

**Output:** Editing logic działa, gap fill + reflow testowane

---

### **Dzień 7 (Wtorek 18.02) - Editing API Endpoints**
- [ ] API endpoints w `app/api/routes/plan.py`:
  - `POST /plans/{id}/days/{day}/remove` → remove item + save version
  - `POST /plans/{id}/days/{day}/replace` → replace item + save version
- [ ] Request models:
  - `RemoveItemRequest(item_id, avoid_cooldown_hours)`
  - `ReplaceItemRequest(item_id, strategy, preferences)`
- [ ] Flow:
  1. Load current plan
  2. Apply edit (remove/replace)
  3. Recalculate times (reflow)
  4. Save as new version
  5. Return updated plan
- [ ] Test via Swagger:
  - Generate 3-day plan
  - Remove Morskie Oko → gap filled + version #2
  - Replace KULIGI → similar POI + version #3
  - Rollback to #1 → version #4
- [ ] Commit: "feat: editing API endpoints with versioning"

**Output:** API editing działa via Swagger

---

### **Dzień 8 (Środa 19.02) - Regenerate Range with Pinned**
- [ ] Extend `plan_editor.py`:
  - `regenerate_time_range(day_plan, from_time, to_time, pinned_items)`
- [ ] Logika:
  1. Extract items w zakresie `from_time`-`to_time`
  2. Keep pinned_items (mark as locked)
  3. Re-run planning dla tego fragmentu (mini `build_day`)
  4. Merge z resztą dnia (przed + fragment + po)
  5. Recalculate wszystkie czasy (reflow)
- [ ] API endpoint:
  - `POST /plans/{id}/days/{day}/regenerate`
  - Request: `{from_time, to_time, pinned_items: [id1, id2]}`
- [ ] Test:
  - Generate plan Day 2: 8:00-20:00
  - Regenerate 14:00-17:00, pin Gubałówka
  - Verify: Gubałówka na miejscu, reszta nowa
- [ ] Commit: "feat: regenerate time range with pinned items"

**Output:** Regenerate range działa, pinned items nietknięte

---

### **Dzień 9 (Czwartek 20.02) - SMART_REPLACE Enhancement**
- [ ] Enhance replace logic:
  - Dodaj category matching (nature → nature, culture → culture)
  - Dodaj vibes matching (relaxing → relaxing, adventure → adventure)
  - Respect time_of_day preferences (rano lekkie, wieczór intensywne)
- [ ] Utwórz `app/domain/planner/similarity.py`:
  - `find_similar_poi(removed_poi, candidates, user_preferences)`
  - Scoring: category (30%), target_group (25%), intensity (20%), duration (15%), vibes (10%)
- [ ] Test:
  - Replace Morskie Oko → powinno dać inny hiking POI (Dolina Kościeliska)
  - Replace KULIGI → powinno dać premium experience (SPA / fine dining)
  - Replace museum → inny kultur POI
- [ ] Commit: "feat: SMART_REPLACE with category + vibes matching"

**Output:** SMART_REPLACE inteligentnie dobiera podobne POI

---

### **Dzień 10 (Piątek 21.02) - Integration Testing**
- [ ] End-to-end scenarios:
  - **Scenario 1: Multi-day planning**
    - Generate 5-day plan
    - Verify unique POI każdego dnia
    - Verify core rotation (Morskie Oko nie w Day 1 zawsze)
    - Check premium penalties working across days
  - **Scenario 2: Editing workflow**
    - Generate plan → version #1
    - Remove 2 POI → gaps filled → version #2
    - Replace 1 POI → SMART_REPLACE → version #3
    - Regenerate fragment 15-18h → pinned work → version #4
    - Rollback to #2 → version #5
    - Verify każda wersja zapisana poprawnie
  - **Scenario 3: Regression (Etap 1)**
    - Test budget=1 → KULIGI penalty -40
    - Test budget=2 → KULIGI penalty -20
    - Test core rotation w single-day plan
    - Ensure zero regressji
- [ ] Bugfixes wykrytych problemów
- [ ] Performance check (query times, memory usage)
- [ ] Commit: "test: E2E scenarios + regression tests"

**Output:** Wszystkie scenariusze działają, zero regressji Etap 1

---

### **Dzień 11-12 (Weekend 22-23.02) - Documentation**
- [ ] Update `README.md`:
  - Database setup instructions (PostgreSQL + Alembic)
  - Multi-day planning usage
  - Editing API examples
  - Versioning examples
- [ ] API docs w Swagger:
  - Descriptions dla nowych endpoints
  - Request/response examples
  - Error codes + handling
- [ ] Utwórz `ETAP2_FEATURES.md`:
  - Co zostało zaimplementowane
  - Jak używać każdej funkcji
  - Test scenarios + expected behavior
- [ ] Code comments:
  - Docstrings dla `plan_multiple_days()`
  - Docstrings dla `PlanEditor` methods
  - In-line comments w kluczowych miejscach
- [ ] Commit: "docs: Etap 2 features + API documentation"

**Output:** Dokumentacja kompletna, łatwe onboarding

---

## 📅 TYDZIEŃ 3: TESTING + BUGFIXES (24.02 - 05.03.2026)

### **Dzień 13-14 (24-25.02) - Comprehensive Testing**
- [ ] Unit tests:
  - `test_multi_day_planning.py` (cross-day tracking, core rotation, energy)
  - `test_plan_editor.py` (remove, replace, reflow, gap fill)
  - `test_versioning.py` (snapshot, rollback, list)
  - `test_regenerate_range.py` (pinned items, time range)
  - `test_smart_replace.py` (similarity matching, category)
- [ ] Integration tests:
  - PostgreSQL transactions (rollback on error)
  - API error handling (404, 400, 500)
  - Concurrent requests (race conditions?)
- [ ] Performance tests:
  - 7-day plan generation time (<2s?)
  - 50 versions in DB (query speed OK?)
  - Large POI datasets (100+ items)
- [ ] Commit: "test: comprehensive unit + integration tests"

**Output:** Pełne pokrycie testami, wszystkie PASS

---

### **Dzień 15-16 (26-27.02) - Bugfixes + Edge Cases**
- [ ] Fix wykrytych bugów z testów
- [ ] Edge cases:
  - Co jeśli brak POI do gap fill? (free time zamiast POI)
  - Co jeśli brak similar POI do replace? (keep gap + suggest manual)
  - Co jeśli rollback do nieistniejącej wersji? (404 error)
  - Co jeśli regenerate range = cały dzień? (re-plan całości)
  - Co jeśli pinned items kolidują czasowo? (error + message)
- [ ] Input validation:
  - Date ranges (trip_length.days 1-7)
  - Time ranges (from_time < to_time)
  - Item IDs exist w planie
- [ ] Error messages user-friendly:
  - Nie internal errors, tylko "Cannot find similar POI, try manual selection"
- [ ] Commit: "fix: edge cases + validation + error handling"

**Output:** Stabilny build, error handling solid

---

### **Dzień 17-18 (28.02 - 01.03) - Deployment Prep**
- [ ] Environment variables:
  - `DATABASE_URL` (PostgreSQL connection string)
  - `ENV` (dev / staging / prod)
- [ ] Render.com config update:
  - Add PostgreSQL database (Render managed lub external)
  - Update `requirements.txt` (psycopg2-binary, alembic)
  - Auto-run migrations on deploy (alembic upgrade head)
- [ ] Health check endpoint:
  - `GET /health` → {db: connected, version: 2.0}
- [ ] Staging deployment:
  - Deploy to Render staging environment
  - Run E2E tests on staging
  - Verify PostgreSQL connection
- [ ] Commit: "chore: deployment config + health check"

**Output:** Staging deployment successful, DB connected

---

### **Dzień 19-20 (02-03.03) - User Acceptance Testing**
- [ ] Prepare test scenarios for klientka:
  - Scenario A: Generate 3-day Zakopane trip (couples, budget=2, hiking)
  - Scenario B: Remove 1 POI, check gap fill + reflow
  - Scenario C: Replace KULIGI, check SMART_REPLACE result
  - Scenario D: Regenerate Day 2 fragment 14-17h, pin Gubałówka
  - Scenario E: Rollback to version #1
- [ ] UAT with klientka:
  - Walkthrough via Swagger or Postman
  - Gather feedback (UX, logic, bugs)
  - Prioritize issues (blocker vs nice-to-have)
- [ ] Quick iterations:
  - Fix blockers same-day
  - Nice-to-have → backlog (Phase 3)
- [ ] Document feedback w `ETAP2_UAT_FEEDBACK.md`

**Output:** Klientka testuje, feedback zebrany

---

### **Dzień 21 (04.03) - Final Bugfixes**
- [ ] Fix UAT feedback (blockers only)
- [ ] Re-test kritycznych scenariuszy
- [ ] Update dokumentacji jeśli logika się zmieniła
- [ ] Code cleanup:
  - Remove dead code
  - Remove debug prints
  - Format code (black, isort)
- [ ] Final regression test (Etap 1 + 2)
- [ ] Commit: "fix: UAT feedback + final cleanup"

**Output:** Build stabilny, gotowy do production

---

### **Dzień 22 (05.03) - Production Deployment**
- [ ] Merge feature branch → main
- [ ] Production deployment via Render.com
- [ ] Monitor logs (errors, performance)
- [ ] Smoke tests na production:
  - Generate plan works
  - Edit plan works
  - Versioning works
- [ ] Backup database (safety)
- [ ] Tag release: `v2.0.0-etap2`
- [ ] Commit: "release: Etap 2 production deployment"

**Output:** ✅ ETAP 2 LIVE NA PRODUCTION

---

## 📅 TYDZIEŃ 3+ (BONUS): POPRAWKI + SUPPORT (06-12.03.2026)

### **Po Production Launch:**
- [ ] Monitor production (błędy, performance issues)
- [ ] Fix critical bugs (<24h response)
- [ ] Gather user feedback (jeśli już są użytkownicy)
- [ ] Minor improvements (jeśli mamy czas):
  - Pagination dla `/plans/{id}/versions` (jeśli >100 wersji)
  - Async job dla gap fill (jeśli wolno)
  - Cache dla POI similarity (jeśli wolno)
- [ ] Prepare Phase 3 backlog:
  - Reorder (drag & drop) - jeśli UX pokaże potrzebę
  - Visual diff - jeśli users pytają
  - Stripe real integration
  - PDF generation
  - Email delivery

**Output:** Stabilny production, gotowy na users

---

## 🎯 SUCCESS CRITERIA (12.03.2026)

### ✅ MUST BE DONE:
- [x] Multi-day planning (2-7 dni) działa
- [x] Cross-day POI tracking (no duplicates)
- [x] Core POI rotation across days
- [x] Editing (remove + replace + reflow)
- [x] SMART_REPLACE (category + vibes matching)
- [x] Regenerate range with pinned items
- [x] Versioning (snapshot + rollback + list)
- [x] Quality scoring + Explainability
- [x] PostgreSQL migration
- [x] All Etap 1 features work (zero regressji)
- [x] Deployed to production
- [x] Full test coverage
- [x] Documentation complete

### ⚠️ DEFERRED TO PHASE 3:
- [ ] Reorder (drag & drop)
- [ ] Visual diff
- [ ] Lunch flexibility
- [ ] Real Stripe integration
- [ ] PDF generation
- [ ] Email delivery
- [ ] Advanced auth system

---

## 📊 DAILY CHECKLIST

**Każdego dnia:**
1. ☕ Morning: Review plan dnia
2. 🚀 Work: Implement tasks dla dnia
3. ✅ Test: Zweryfikuj że działa + regression test Etap 1
4. 💾 Commit: Push progress (1-3 commity/dzień)
5. 📝 EOD: Update progress w tym dokumencie (✅ done tasks)
6. 🧠 Memory: Update `ETAP2_PROGRESS.md` (daily log)

**Jeśli problem:**
- 🐛 Bug > 2h → skip to next task, wróć później
- ⏰ Task > estimated time → simplify lub defer
- ❓ Blocked → document blocker, move to next

**Communication z klientką:**
- 📧 Weekly update (every Friday): progress + blockers + next week plan
- 🚨 Critical issues: notify same-day
- ✅ Milestone completion: demo + feedback

---

## 🔥 RISK MITIGATION

### **Ryzyko 1: PostgreSQL migration breaks Etap 1**
- **Mitigation:** Test po każdej zmianie, keep interface identical
- **Backup plan:** Rollback to in-memory if production broken

### **Ryzyko 2: Multi-day planning zbyt wolne**
- **Mitigation:** Profile performance, optimize queries
- **Backup plan:** Cache POI data, simplify scoring

### **Ryzyko 3: SMART_REPLACE nie matchuje dobrze**
- **Mitigation:** Iteracyjnie tuning similarity weights
- **Backup plan:** Fallback to random POI jeśli brak good match

### **Ryzyko 4: 3 tygodnie za mało czasu**
- **Mitigation:** Priorytetyzuj must-have, defer nice-to-have
- **Backup plan:** Extend o 3-5 dni jeśli klientka OK

### **Ryzyko 5: UAT feedback wymaga dużych zmian**
- **Mitigation:** Test wcześnie (day 19-20), quick iterations
- **Backup plan:** Phase 3 dla non-critical feedback

---

## 📈 METRICS TO TRACK

**Development progress:**
- ✅ Tasks completed / total (daily)
- 🐛 Bugs found / fixed (weekly)
- 📦 Commits pushed (daily)
- ⏱️ Actual time vs estimated (per task)

**Quality metrics:**
- ✅ Test coverage (target: >80%)
- 🐛 Critical bugs (target: 0 before production)
- ⚡ API response time (target: <2s for 7-day plan)
- 💾 DB query time (target: <500ms)

**Business metrics:**
- ✅ Etap 1 regression tests (target: 100% PASS)
- 🎯 Feature completion (target: 100% must-have)
- 📅 Timeline adherence (target: delivery by 12.03)

---

## 📞 CONTACT & ESCALATION

**Developer (Ty):**
- Daily work: implement features, test, commit
- Daily updates: update progress document
- Weekly reports: send to klientka (Friday EOD)

**Klientka (Karolina):**
- UAT testing: day 19-20 (02-03.03)
- Feedback: respond <24h if blockers
- Approval: final sign-off (05.03 before prod deploy)

**Escalation:**
- Blocker >1 day → notify klientka
- Timeline risk → propose extension or cut scope
- Critical bug in production → hotfix <2h

---

## ✅ FINAL DELIVERABLES (12.03.2026)

1. **Working Backend:**
   - Multi-day planning API
   - Editing API (remove + replace + regenerate)
   - Versioning API (list + get + rollback)
   - PostgreSQL database (production)
   - Deployed on Render.com

2. **Documentation:**
   - `README.md` updated
   - `ETAP2_FEATURES.md` (feature guide)
   - `ETAP2_UAT_FEEDBACK.md` (test results)
   - Swagger docs complete
   - Code docstrings

3. **Tests:**
   - Unit tests (>80% coverage)
   - Integration tests (E2E scenarios)
   - Regression tests (Etap 1 PASS)

4. **Handoff Materials:**
   - Video walkthrough (30-45 min)
   - Code review guidelines
   - Phase 3 backlog (reorder, diff, Stripe, PDF, Email)

---

**Status:** 🟢 READY TO START  
**Next Action:** 12.02.2026 (jutro) → Day 1: PostgreSQL Setup  
**Developer:** Mateusz Zurowski (ngencode.dev@gmail.com)  
**Client:** Karolina Sobotkiewicz
