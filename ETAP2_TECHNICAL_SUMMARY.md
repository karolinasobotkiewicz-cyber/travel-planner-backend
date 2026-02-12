# ETAP 2 - TECHNICAL SUMMARY

**Date:** 10.02.2026  
**Status:** Offer Ready - Awaiting Client Approval  
**Price:** 9,000 PLN (15% discount from 10,640 PLN)  
**Payment:** 50/50 (4,500 PLN start + 4,500 PLN acceptance)  
**Timeline:** 7 weeks (February → April 2026)  
**Bonus:** 2 weeks support + video docs + guidelines (value: 2,500 PLN)

---

## 📊 CURRENT STATE (ETAP 1)

### Architecture ✅
```
app/
├── api/              # FastAPI routes, dependencies
├── application/      # PlanService, mappers
├── domain/          # Engine, scoring (15+ modules), models
└── infrastructure/  # Repositories (in-memory), data loaders
```

### Features Implemented ✅
- ✅ Single-day planning (`build_day()`)
- ✅ 15+ scoring modules (family, budget, crowd, intensity, preferences, travel_style, etc.)
- ✅ Core POI rotation (08.02.2026)
- ✅ Premium experience penalties (08.02.2026)
- ✅ Hard filters (seasonality, target_group, intensity, opening hours)
- ✅ Gap filling logic
- ✅ Repository pattern (in-memory)
- ✅ Mock Stripe payments
- ✅ API contracts (TripInput → PlanResponse)

### Missing ❌
- ❌ Multi-day orchestration
- ❌ PostgreSQL persistence
- ❌ Real Stripe integration
- ❌ PDF generation
- ❌ Email delivery
- ❌ Plan versioning
- ❌ Plan editing/regeneration
- ❌ Admin panel
- ❌ User authentication

---

## 🎯 ETAP 2 SCOPE

### 1. MULTI-DAY PLANNING (20h) 🔴 CRITICAL

**New Function:**
```python
def plan_multiple_days(pois, user, context, num_days: int):
    """
    Multi-day orchestrator with:
    - Cross-day POI tracking (no duplicates)
    - Core rotation (1 core/day, no repeats)
    - Day vibe steering (travel_style + group corrections)
    - Progressive energy depletion
    - Daily limits per group type
    """
    all_days = []
    used_poi_ids = set()
    core_pois_used = []
    
    for day_num in range(num_days):
        context_day = {
            **context,
            "day_number": day_num + 1,
            "used_pois": used_poi_ids,
            "core_history": core_pois_used,
            "cumulative_fatigue": calculate_multi_day_fatigue(day_num)
        }
        
        day_plan = build_day_v2(pois, user, context_day,
                                enforce_core_rotation=True,
                                enforce_variety=True)
        
        all_days.append(day_plan)
        used_poi_ids.update(extract_poi_ids(day_plan))
        core_pois_used.extend(extract_core_pois(day_plan))
    
    return all_days
```

**Key Features:**
- Core rotation cross-day (already have single-day logic)
- Day vibe calculation (`calculate_day_vibe(travel_style, group, day_num)`)
- Cross-day diversity penalty
- Cumulative fatigue tracking

**Testing:**
- 2, 3, 5, 7 day scenarios
- Verify no POI duplicates
- Verify core rotation (different core each day)
- Verify day diversity

---

### 2. PLAN QUALITY + EXPLAINABILITY (12-16h) 🟠 HIGH

**New Module:** `app/domain/planner/quality/`

```python
class QualityChecker:
    def validate_poi(self, poi, context, user):
        return {
            "valid": bool,
            "hard_excludes": [],    # BLOCKING
            "soft_penalties": [],   # WARNINGS
            "quality_badges": []    # POSITIVE
        }

class ExplainabilityService:
    def explain_selection(self, poi, score_breakdown, user):
        return {
            "why_selected": ["Matches preferences", "Must-see", ...],
            "badges": ["must_see", "core_attraction", "perfect_timing"],
            "score_breakdown": {...}  # Optional debug
        }
```

**Response Extension:**
```python
class AttractionItem(BaseModel):
    # ... existing ...
    why_selected: List[str] = []
    quality_badges: List[str] = []
    score_breakdown: Optional[Dict[str, float]] = None
```

---

### 3. WERSJE I HISTORIA (10-12h) 🟡 MEDIUM

**New Table:** `plan_versions`
```python
class PlanVersion(BaseModel):
    version_id: str
    plan_id: str
    version_number: int
    created_at: datetime
    days: List[DayPlan]
    parent_version_id: Optional[str]
    change_type: str  # initial, regenerated, edited, rollback
```

**New Repository:** `PlanVersionRepository`
- `save_version(plan_id, version, change_type)`
- `list_versions(plan_id)`
- `get_version(plan_id, version_num)`
- `diff_versions(version_a, version_b)` - MVP diff
- `rollback_to_version(plan_id, version_num)` - creates new version

**API Endpoints:**
- `GET /plans/{plan_id}/versions`
- `GET /plans/{plan_id}/versions/{num}`
- `POST /plans/{plan_id}/versions/{num}/diff`
- `POST /plans/{plan_id}/rollback`

**Note:** Requires PostgreSQL!

---

### 4. EDYCJA I NAPRAWA (16-20h) 🔴 HIGH

**New Module:** `app/domain/planner/edit_engine.py`

```python
class PlanEditor:
    def remove_item(self, day_plan, item_id, avoid_cooldown_hours=24):
        """Remove + add to avoid list + reflow."""
        pass
    
    def replace_item(self, day_plan, item_id, strategy="SMART_REPLACE"):
        """Replace with similar alternative."""
        # Strategy: same categories, similar duration, time compatible
        pass
    
    def reorder_items(self, day_plan, item_id, new_position):
        """Reorder + recalc transit times."""
        pass
    
    def regenerate_fragment(self, day_plan, start_item, end_item):
        """Regenerate items between two fixed points."""
        pass
    
    def reflow_day(self, day_plan):
        """Recalc all times after edits."""
        pass
```

**API Endpoints:**
- `POST /plans/{plan_id}/days/{day}/reorder`
- `DELETE /plans/{plan_id}/days/{day}/items/{id}`
- `POST /plans/{plan_id}/days/{day}/items/{id}/replace`
- `POST /plans/{plan_id}/days/{day}/regenerate-fragment`

**MVP Scope:** Remove + Replace only (defer Reorder)

---

### 5. MONETYZACJA (32-42h total) 🔴 CRITICAL

#### 5.1 User Auth (6-8h)
```python
# app/api/routes/auth.py
@router.post("/auth/login")
@router.post("/auth/register")
@router.post("/auth/claim-guest-plan")  # Associate guest plan with user
```

#### 5.2 Real Stripe (8-10h)
```python
import stripe

@router.post("/create-checkout-session")
def create_checkout_session(request):
    session = stripe.checkout.Session.create(
        line_items=[{...}],
        metadata={'plan_id': request.plan_id}
    )
    return CheckoutSessionResponse(
        session_id=session.id,
        checkout_url=session.url
    )

@router.post("/stripe/webhook")
async def stripe_webhook(request):
    # Signature validation
    event = stripe.Webhook.construct_event(payload, sig, secret)
    
    if event['type'] == 'checkout.session.completed':
        plan_id = event['data']['object']['metadata']['plan_id']
        entitlement_service.grant_access(plan_id, customer_id)
        pdf_service.generate_async(plan_id)
        email_service.send_confirmation(plan_id)
```

**New Service:** `EntitlementService`
- `grant_access(plan_id, customer_id)`
- `check_access(plan_id, user_id)`

#### 5.3 PDF Generation (12-14h)
```python
# app/application/services/pdf_service.py
from reportlab.pdfgen import canvas

class PDFService:
    def generate_async(self, plan_id):
        """Queue job (Railway cron or Celery)."""
        pass
    
    def generate_pdf(self, plan: PlanResponse) -> bytes:
        """Render plan to PDF."""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        # ... render plan ...
        return buffer.getvalue()
    
    def upload_to_storage(self, plan_id, pdf_bytes):
        """Upload to S3 or Railway volume."""
        pass

# API:
@router.get("/plans/{plan_id}/pdf")
def get_plan_pdf(plan_id, user_id):
    if not entitlement_service.check_access(plan_id, user_id):
        raise HTTPException(403)
    return {"pdf_url": pdf_service.get_or_generate(plan_id)}
```

#### 5.4 Email Delivery (8-10h)
```python
# app/infrastructure/email/

class EmailService:
    def send_purchase_confirmation(self, plan_id):
        """Queue email."""
        email = EmailMessage(
            to="...",
            subject="Your Plan is Ready",
            body="...",
            attachments=["plan.pdf"]
        )
        self.outbox.queue(email)
    
    def send_queued_emails(self):
        """Worker - sends pending emails."""
        pending = self.outbox.get_pending()
        for email in pending:
            try:
                self.smtp.send(email)
                self.outbox.mark_sent(email.id)
            except:
                self.outbox.increment_retry(email.id)

# Outbox table:
class EmailOutbox:
    id, to, subject, body, status, retry_count, created_at, sent_at
```

---

### 6. ADMIN PANEL (10-12h) 🟢 LOW

**New Routes:** `app/api/routes/admin.py`

```python
@router.get("/admin/plans")          # List all plans
@router.get("/admin/plans/{id}")     # View plan details
@router.get("/admin/jobs")           # Background jobs
@router.get("/admin/exports")        # PDF list
@router.get("/admin/emails")         # Email outbox
@router.get("/admin/errors")         # Error logs
@router.get("/admin/poi-quality")    # POI quality check
```

**Frontend:** FastAPI Admin or minimal React dashboard

---

### 7. POSTGRESQL MIGRATION (8-10h) 🔴 CRITICAL

**Schema Design:**
```sql
-- plans
CREATE TABLE plans (
    plan_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    version INT,
    days JSONB,
    metadata JSONB,
    paid BOOLEAN DEFAULT FALSE,
    customer_id VARCHAR,
    created_at TIMESTAMP
);

-- plan_versions
CREATE TABLE plan_versions (
    version_id UUID PRIMARY KEY,
    plan_id UUID REFERENCES plans(plan_id),
    version_number INT,
    days JSONB,
    parent_version_id UUID,
    change_type VARCHAR,
    created_at TIMESTAMP
);

-- users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE,
    password_hash VARCHAR,
    created_at TIMESTAMP
);

-- entitlements
CREATE TABLE entitlements (
    id UUID PRIMARY KEY,
    plan_id UUID REFERENCES plans(plan_id),
    user_id UUID REFERENCES users(id),
    granted_at TIMESTAMP,
    payment_intent_id VARCHAR
);

-- email_outbox
CREATE TABLE email_outbox (
    id UUID PRIMARY KEY,
    to_email VARCHAR,
    subject VARCHAR,
    body TEXT,
    status VARCHAR,  -- pending, sent, failed
    retry_count INT DEFAULT 0,
    created_at TIMESTAMP,
    sent_at TIMESTAMP
);
```

**Implementation:**
- SQLAlchemy models
- Alembic migrations
- Update Repository implementations (keep interfaces!)
- Railway PostgreSQL addon

---

## 💰 PRICING

### BREAKDOWN:

| Module | Hours | Complexity |
|--------|-------|------------|
| Multi-day Planning | 18h | ⭐⭐⭐ High |
| Quality + Explainability | 14h | ⭐⭐ Medium |
| Versioning (MVP) | 10h | ⭐⭐ Medium |
| Plan Editing (MVP) | 16h | ⭐⭐⭐ High |
| Auth (Login + Claim) | 7h | ⭐ Low-Medium |
| Stripe Integration | 9h | ⭐⭐ Medium |
| PDF Generation | 12h | ⭐⭐ Medium |
| Email + Outbox | 9h | ⭐⭐ Medium |
| Admin Panel (Basic) | 10h | ⭐ Low |
| PostgreSQL Migration | 10h | ⭐⭐ Medium |
| Testing + QA | 22h | ⭐⭐⭐ High |
| Deployment + DevOps | 7h | ⭐ Low-Medium |
| Documentation + Handoff | 8h | ⭐ Low |

**Total:** ~152 hours

### PRICING:

**Standard Rate:** 70 PLN/h × 152h = 10,640 PLN  
**Proposed:** **9,000 PLN** (15% discount)  
**Savings:** 1,640 PLN

### PAYMENT TERMS (50/50):

**Payment #1: 4,500 PLN** 💰
- When: After contract signing, before implementation start
- Form: VAT invoice
- Terms: 7 days

**Payment #2: 4,500 PLN** 💰
- When: After delivery and client acceptance
- Form: VAT invoice
- Terms: 7 days

**Milestone for Payment #2:**
```
✅ Multi-day planning works (tested: 2, 3, 5, 7 days)
✅ Stripe accepts payments (test + live mode)
✅ PostgreSQL deployed and working
✅ PDF generates correctly
✅ Email confirmation works
✅ Plan editing (remove + replace) works
✅ Basic admin panel views
✅ All tests PASS (>80% coverage)
✅ Swagger docs updated
✅ Deployed on Railway
```

### BONUS INCLUDED (value ~2,500 PLN - FREE!):

1. **2 weeks post-launch support** (~1,400 PLN value)
   - Critical bug hotfixes
   - Technical questions
   - Deployment assistance
   - 24h response time

2. **Video technical documentation** (~700 PLN value)
   - 30-45 min screen recording
   - Architecture walkthrough
   - How to edit plans, multi-day logic, Stripe testing
   - For your team / future developers

3. **Code review guidelines** (~400 PLN value)
   - "How to develop project further" document
   - Best practices for this codebase
   - Common pitfalls
   - Future-proofing

**Total bonus value: ~2,500 PLN for 0 PLN extra!**

---

## ⚠️ RISKS & MITIGATION

| Risk | Severity | Mitigation |
|------|----------|------------|
| Multi-day complexity | 🔴 HIGH | Start simple, iterate, test 2/3/5/7 day scenarios |
| Edit reflow logic | 🟡 MEDIUM | Do remove+replace first, defer reorder |
| PostgreSQL migration | 🟡 MEDIUM | Interfaces ready, use SQLAlchemy + Alembic |
| PDF performance | 🟡 MEDIUM | Async generation (Railway cron) |
| Stripe webhooks | 🟢 LOW | Signature validation, idempotency, test with CLI |
| Email delivery | 🟢 LOW | Outbox pattern, use SendGrid |

---

## 📅 TIMELINE (Option B)

**Week 1-2:** Multi-day planning + PostgreSQL migration  
**Week 3:** Stripe integration + Entitlement  
**Week 4:** PDF + Email  
**Week 5:** Plan editing (remove + replace)  
**Week 6:** Testing + bug fixes  
**Week 7:** Deployment + final QA  

**Total:** 7 weeks (mid-Feb → early April 2026)

---

## 🚀 MUST-HAVE FOR LAUNCH

1. 🔴 Multi-day planning
2. 🔴 Stripe + Entitlement
3. 🟠 PostgreSQL
4. 🟠 PDF generation
5. 🟠 Email confirmation
6. 🟡 Basic editing (remove + replace)

**Post-launch:**
- Explainability (why_selected)
- Admin panel (full)
- Version diff + rollback
- Advanced editing (reorder)

---

## ✅ RECOMMENDATION: FULL SCOPE FOR 9,000 PLN

**Why this is the right choice:**

### 1. **Everything needed for launch** ✅
You won't need to ask for "one more thing" next month:
- Multi-day planning (2-7 days) ✅
- Stripe payments (real integration) ✅
- PostgreSQL (scalable storage) ✅
- PDF generation (deliverable) ✅
- Email confirmations ✅
- Plan editing (remove + replace) ✅
- Basic admin (monitoring) ✅
- Plan versioning (history) ✅
- Quality checks + explainability ✅

### 2. **Product ready for growth** 🚀
You won't need to "refactor" in 6 months:
- Clean Architecture (easy to extend)
- Comprehensive tests (confidence in changes)
- Documentation (onboarding new people)
- Scalable infrastructure (PostgreSQL + Railway)

### 3. **Zero technical debt** 💎
You won't pay twice:
- Code written "right once", not "quick and dirty"
- Edge cases handled (not just happy path)
- Error handling (graceful failures)
- Monitoring hooks (know what's happening)

### 4. **Peace of mind** 😌
- Fixed price → **you know what you pay**
- 50/50 payment → **safe for both sides**
- 2 weeks support → **calm post-launch**
- Video docs → **team can take over**

### 5. **Best value for money** 💰
**Cheaper (6-7k PLN):**
- ⚠️ Only must-haves
- ⚠️ Minimal tests
- ⚠️ No documentation
- ⚠️ Problems after 2-3 months
- ⚠️ **Refactoring cost: +5-8k PLN later**

**More expensive (15-20k PLN):**
- ✅ Software house quality
- ⚠️ Slower timeline (3-4 months)
- ⚠️ More bureaucracy
- ⚠️ Less flexible
- ⚠️ **40% goes to PM + overhead**

**This offer (9k PLN):**
- ✅ Software house quality
- ✅ Freelancer flexibility
- ✅ Optimal timeline
- ✅ Direct communication
- ✅ Long-term success focus

---

**Status:** Awaiting client approval  
**Next:** Review full spec → Contract → Kickoff → Start work
