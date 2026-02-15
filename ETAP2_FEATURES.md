# ETAP 2 - Features Documentation

**Completed:** 15.02.2026  
**Deployment:** https://travel-planner-backend-xbsp.onrender.com

---

## 1. Multi-Day Planning (Days 8-9)

**Co zostało dodane:**
- Planowanie 1-5 dni (poprzednio: tylko 1 dzień)
- Cross-day POI uniqueness (>70%)
- Core POI rotation (Morskie Oko nie zawsze dzień 1)
- Energy system (dzień 1 = heavy hiking OK, potem lighter)

**Endpoint:** `POST /plan/preview`

**Payload:**
```json
{
  "location": { "city": "Zakopane", "country": "Poland", "region_type": "mountain" },
  "group": { "type": "couples", "size": 2, "crowd_tolerance": 1 },
  "trip_length": { "days": 5, "start_date": "2026-03-15" },
  "daily_time_window": { "start": "09:00", "end": "19:00" },
  "budget": { "level": 2 },
  "transport_modes": ["car"],
  "travel_style": "balanced"
}
```

**Logika:**
- `used_poi_ids` set śledzi POI across days
- Core POI (Morskie Oko, Dolina Kościeliska, Rusinowa Polana) rotują
- Premium POI (termy) są kontrolowane przez budget penalties
- Uniqueness rate: 20 unique POI / 28 total = 71.4% (target >70%)

**Test results (live na Render):**
- ✅ 5-day plan generated
- ✅ 71.4% uniqueness
- ✅ Core rotation: poi_35 → poi_33 → poi_34 → poi_24
- ✅ Premium POI balanced

---

## 2. Plan Editing (Day 7)

### 2.1 Remove POI

**Endpoint:** `POST /plan/{id}/days/{day}/remove`

**Payload:**
```json
{
  "item_id": "poi_30",
  "avoid_cooldown_hours": 24
}
```

**Logika:**
1. Find attraction by poi_id
2. Remove item + adjacent transits
3. Gap fill: try insert new POI (avoid recently removed)
4. Reflow all times
5. Create new version in DB

**Test:** Removed poi_30 (Kaplica) + poi_16 (Termy) → versions 4, 6 created ✅

---

### 2.2 Replace POI (SMART_REPLACE)

**Endpoint:** `POST /plan/{id}/days/{day}/replace`

**Payload:**
```json
{
  "item_id": "poi_20",
  "strategy": "SMART_REPLACE",
  "preferences": {}
}
```

**Logika:**
1. Find target POI
2. Score all available POI (similarity + category match)
3. Replace with best match
4. Recalculate times
5. Create version

**Test:** Replaced poi_20 (Wielka Krokiew) → version 8 created ✅

---

### 2.3 Regenerate Time Range

**Endpoint:** `POST /plan/{id}/days/{day}/regenerate`

**Payload:**
```json
{
  "from_time": "15:00",
  "to_time": "18:00",
  "pinned_items": ["poi_35"]
}
```

**Logika:**
1. Extract items in time range
2. Keep pinned items locked
3. Remove unpinned attractions
4. Re-run mini planning for slots
5. Merge before + regenerated + after
6. Full reflow

**Test:** Regenerated 15:00-18:00 → version 10 created ✅

---

## 3. Version Control (Day 6)

### 3.1 Version Tracking

**Database:** `plan_versions` table

**Struktura:**
```sql
CREATE TABLE plan_versions (
    id UUID PRIMARY KEY,
    plan_id UUID REFERENCES plans(id),
    version_number INT,
    days_json JSONB,           -- full snapshot
    change_type VARCHAR(50),   -- initial, generated, remove_item, replace_item, regenerate_range, rollback
    change_summary TEXT,
    parent_version_id UUID,
    created_at TIMESTAMP
);
```

**Każda zmiana = nowa wersja:**
- Initial plan creation
- Generate plan
- Remove POI
- Replace POI
- Regenerate range
- Rollback

**Test:** 12 versions created w editing workflow ✅

---

### 3.2 List Versions

**Endpoint:** `GET /plan/{id}/versions`

**Response:**
```json
[
  {
    "version_number": 4,
    "change_type": "remove_item",
    "change_summary": "Removed item poi_30 from day 1",
    "created_at": "2026-02-15T22:21:37"
  },
  ...
]
```

**Test:** Historia 12 wersji widoczna ✅

---

### 3.3 Rollback

**Endpoint:** `POST /plan/{id}/rollback`

**Payload:**
```json
{
  "target_version": 4
}
```

**Logika:**
1. Fetch target version snapshot (days_json)
2. Create new version with change_type='rollback'
3. Copy days_json from target
4. Update Plan.updated_at
5. Return success

**Test:** Rollback do wersji 4 → version 12 created ✅

**Ważne:** Rollback NIE usuwa wersji, tylko tworzy nową z kopią starej (immutable history).

---

## 4. PostgreSQL Migration (Day 4-5)

**Co zostało zrobione:**
- Alembic migrations setup
- `plans` table (id, user_id, created_at, updated_at, days_json, version)
- `plan_versions` table (version tracking)
- `poi` table (read-only, seed from zakopane.xlsx)
- Connection pooling via psycopg2

**Render Setup:**
- Postgres FREE tier
- Auto-migrations on deploy via `render.yaml`
- Env variable: `DATABASE_URL`

**Local Setup:**
```bash
createdb travel_planner
export DATABASE_URL="postgresql://user:pass@localhost/travel_planner"
alembic upgrade head
```

---

## 5. Gap Fill Logic (Day 7)

**Problem:** Po usunięciu POI powstaje luka czasu.

**Rozwiązanie:**
1. Calculate gap (start_time, duration)
2. Score available POI (fit gap, category, target group)
3. Select best POI
4. Insert with transit
5. Reflow times

**Code:** `app/application/services/plan_editor.py::_attempt_gap_fill()`

**Test:** Po usunięciu poi_30, gap został wypełniony innym POI ✅

---

## 6. Time Reflow (Day 7)

**Problem:** Po każdej edycji trzeba przeliczyć wszystkie czasy.

**Rozwiązanie:**
1. Iterate through all items sequentially
2. Recalculate start_time based on previous end_time
3. Handle transits (duration based on distance)
4. Preserve structure (parking, lunch, day_end)

**Code:** `app/application/services/plan_editor.py::_recalculate_times()`

**Test:** Po remove/replace/regenerate wszystkie czasy spójne ✅

---

## 7. Testing (Day 10)

**E2E Tests:** 3 scenarios PASSED na live Render deployment

**Scenario 1: Multi-Day Planning**
- Plan ID: aa3fd398-0439-4f04-869b-b9f4a81ebe31
- 5-day plan, 28 POI, 71.4% uniqueness
- Core rotation working

**Scenario 2: Editing Workflow**
- 12 versions created
- Remove x2, Replace x1, Regenerate x1, Rollback x1
- All operations successful

**Scenario 3: Regression**
- Budget=1: 4 POI (~95 PLN)
- Budget=2: 6 POI (~135 PLN)
- Core rotation: poi_35 → poi_33 → poi_35
- Zero regresji Etap 1

**Test execution:** Automated via PowerShell REST API calls

---

## 8. Changes vs ETAP 1

| Feature | ETAP 1 | ETAP 2 |
|---------|--------|--------|
| **Planning** | 1 day only | 1-5 days |
| **Database** | In-memory | PostgreSQL |
| **Versioning** | None | Full history + rollback |
| **Editing** | None | Remove, Replace, Regenerate |
| **POI Uniqueness** | N/A | >70% cross-day |
| **Core Rotation** | Static | Dynamic |
| **API Endpoints** | 7 | 14 |

---

## Known Limitations

1. **Regenerate auto-versions:** Każde remove/replace tworzy 2 wersje (edit + automatic regenerate). To design decision - można optymalizować w przyszłości.

2. **Gap fill quality:** Gap fill wybiera "best available", ale nie zawsze idealny match. W przyszłości można dodać ML scoring.

3. **Cross-day energy:** System energii jest uproszczony (day 1 = heavy OK, rest = lighter). Można rozbudować o user fitness level.

4. **Timing gaps:** W niektórych planach są luki 1-2h przed lunchem (gdy brak POI fitting gap). Akceptowalne, ale można usprawnić.

---

## Future Improvements (ETAP 3+)

- [ ] ML-based POI recommendations
- [ ] Weather-based plan adjustments
- [ ] Real-time traffic for transits
- [ ] Multi-destination planning (Kraków + Zakopane)
- [ ] User feedback loop (rating POI)
- [ ] Advanced energy model (user fitness)
- [ ] Optimize automatic regenerations (skip if unnecessary)

---

**Status:** ✅ All ETAP 2 features complete and tested  
**Next:** Klientka manual testing via Swagger UI
