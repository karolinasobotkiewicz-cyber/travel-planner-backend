# ETAP 2 - OFERTA I ANALIZA DLA KLIENTKI

**Data:** 10.02.2026  
**Klient:** Karolina Sobotkiewicz  
**Projekt:** Travel Planner Backend - Multi-day + Monetization  
**Developer:** Mateusz Zurowski (ngencode.dev@gmail.com)

---

## 📋 POTWIERDZENIE FUNDAMENTÓW Z ETAPU 1

Cześć Karolino!

Dziękuję za przesłanie zakresu Etapu 2. Najpierw potwierdzam fundamenty, które mamy gotowe:

### ✅ CO MAMy GOTOWE (Etap 1):

#### 1. **Architecture & Layer Separation** ✅
```
app/
├── domain/           # Business logic (engine, scoring, filters)
├── application/      # Use cases (PlanService, mappers)
├── infrastructure/   # Data access (repositories, loaders)
└── api/             # HTTP layer (routes, dependencies)
```
- **Clean Architecture** z wyraźnymi granicami
- **Dependency Injection** gotowy
- **Testability** - każda warstwa jest testowalna osobno

#### 2. **Repository Pattern** ✅
```python
# Już działające repositories:
- PlanRepository      # In-memory storage dla planów
- POIRepository       # Ładowanie z Excel
- DestinationsRepository  # Metadata destynacji
```
- **GOTOWE** do podmiany na PostgreSQL
- Interface-based, łatwa migracja do DB

#### 3. **Mock Stripe Payment Flow** ✅
```python
# app/api/routes/payment.py
- POST /create-checkout-session  # Generuje fake Stripe URL
- POST /stripe/webhook            # Mock webhook handler
```
- **Szkielet gotowy**, wystarczy wpiąć prawdziwy Stripe SDK
- TODO: Signature validation, event handling, entitlement logic

#### 4. **Planning Engine - Single Day** ✅
```python
# app/domain/planner/engine.py  
def build_day(pois, user, context):
    # ✅ Scoring system (15+ modułów)
    # ✅ Core POI rotation (Phase 2 - 08.02.2026)
    # ✅ Premium experience (KULIGI - 08.02.2026)
    # ✅ Hard filters (seasonality, target_group, intensity)
    # ✅ Soft penalties (budget, crowd, weather)
    # ✅ Gap filling logic
    # ✅ Energy management
    # ✅ Opening hours validation
    # ✅ Time windows & lunch breaks
```
- **1-day planning działa ŚWIETNIE**
- ❌ **Brak multi-day orchestration** (to do zrobienia)

#### 5. **API Contracts & Models** ✅
```python
# Modele Pydantic:
- TripInput (location, group, budget, preferences, travel_style)
- PlanResponse (days[], metadata)
- DayPlan (items[], day_number)
- 7 item types (day_start, parking, transit, attraction, lunch, free_time, day_end)
```
- **API zgodne z klientką** (25.01.2026 feedback)
- **Swagger docs** działają
- **Validation** out-of-the-box

#### 6. **Data Infrastructure** ✅
```
data/zakopane.xlsx
- 70+ POI z pełnymi danymi
- Scoring attributes (must_see, priority, intensity, target_groups)
- Logistics (parking, tickets, opening_hours)
- Premium experience flag (KULIGI - 08.02.2026)
- Core POI rotation (priority_level=12 - 08.02.2026)
```

---

## 🎯 ZAKRES ETAPU 2 - BREAKDOWN

### **1. MULTI-DAY PLANNING** (2-7 dni)

#### Co trzeba zrobić:
```python
# NOWA FUNKCJA w engine.py
def plan_multiple_days(pois, user, context, num_days):
    """
    Orchestrator multi-day z logiką:
    - Day-to-day POI tracking (avoid duplicates)
    - Core rotation across days (1 core/day, no repeats)
    - Day vibe steering (travel_style + group corrections)
    - Progressive energy depletion
    - Daily limits per group type
    """
    all_days = []
    used_poi_ids = set()  # Cross-day tracking
    core_pois_used = []   # Core rotation tracking
    
    for day_num in range(num_days):
        # Per-day context updates
        context_day = {
            **context,
            "day_number": day_num + 1,
            "used_pois": used_poi_ids,
            "core_history": core_pois_used,
            "cumulative_fatigue": calculate_multi_day_fatigue(day_num)
        }
        
        # Generate day with cross-day constraints
        day_plan = build_day_v2(
            pois,
            user,
            context_day,
            enforce_core_rotation=True,
            enforce_variety=True
        )
        
        all_days.append(day_plan)
        
        # Update tracking
        used_poi_ids.update(extract_poi_ids(day_plan))
        core_pois_used.extend(extract_core_pois(day_plan))
    
    return all_days
```

#### Wymagania:
- ✅ **Core rotation** - już mamy logikę (08.02.2026), extend to multi-day
- ✅ **Limity atrakcji** - już mamy (GROUP_ATTRACTION_LIMITS)
- 🆕 **Day vibe** - nowa funkcja `calculate_day_vibe(travel_style, group, day_num)`
- 🆕 **Bazowa dywersyfikacja** - penalty za podobieństwo dni
- 🆕 **Cross-day POI tracking** - set() do śledzenia użytych POI

**Szacunek:** 16-20 godzin

---

### **2. PLAN QUALITY + EXPLAINABILITY**

#### Co trzeba zrobić:
```python
# NOWA WARSTWA: app/domain/planner/quality/

class QualityChecker:
    """Runtime validation POI before selection."""
    
    def validate_poi(self, poi, context, user):
        flags = {
            "valid": True,
            "hard_excludes": [],    # BLOCKING issues
            "soft_penalties": [],   # WARNINGS
            "quality_badges": []    # POSITIVE signals
        }
        
        # Hard excludes (already exists, consolidate)
        if self.check_season_mismatch(poi, context):
            flags["hard_excludes"].append("season_mismatch")
        if self.check_target_group_mismatch(poi, user):
            flags["hard_excludes"].append("target_group_mismatch")
        if self.check_intensity_mismatch(poi, user):
            flags["hard_excludes"].append("intensity_too_high")
        
        # Soft penalties (capture from scoring modules)
        if poi.get("premium_experience") and user["budget"] < 3:
            flags["soft_penalties"].append("budget_penalty")
        if poi.get("crowd_level") > user["crowd_tolerance"]:
            flags["soft_penalties"].append("crowd_sensitive")
        
        # Quality badges (NEW)
        if poi.get("must_see_score", 0) > 80:
            flags["quality_badges"].append("must_see")
        if poi.get("priority_level") == 12:
            flags["quality_badges"].append("core_attraction")
        if self.check_perfect_timing(poi, context):
            flags["quality_badges"].append("perfect_timing")
        
        flags["valid"] = len(flags["hard_excludes"]) == 0
        return flags

class ExplainabilityService:
    """Generate why_selected reasons for attractions."""
    
    def explain_selection(self, poi, score_breakdown, user, context):
        reasons = []
        
        # Top scoring factors
        if score_breakdown["preference_match"] > 50:
            reasons.append("Matches your preferences")
        if score_breakdown["must_see"] > 80:
            reasons.append("Must-see attraction")
        if score_breakdown["travel_style_bonus"] > 20:
            reasons.append(f"Perfect for {user['travel_style']} style")
        if poi.get("target_groups") and user["target_group"] in poi["target_groups"]:
            reasons.append(f"Great for {user['target_group']}")
        
        # Timing/logistics
        if score_breakdown["time_of_day"] > 15:
            reasons.append("Optimal time for this activity")
        if score_breakdown["weather_fit"] > 10:
            reasons.append("Weather-appropriate")
        
        return {
            "why_selected": reasons[:3],  # Top 3 reasons
            "score_breakdown": score_breakdown,
            "badges": self.quality_checker.validate_poi(poi, context, user)["quality_badges"]
        }
```

#### Response model extension:
```python
class AttractionItem(BaseModel):
    # ... existing fields ...
    
    # NEW - Explainability
    why_selected: List[str] = Field(
        default_factory=list,
        description="Top reasons why this attraction was selected"
    )
    quality_badges: List[str] = Field(
        default_factory=list,
        description="Quality signals: must_see, core_attraction, perfect_timing, etc."
    )
    
    # Optional: Score breakdown dla debugging (only if requested)
    score_breakdown: Optional[Dict[str, float]] = None
```

**Szacunek:** 12-16 godzin

---

### **3. WERSJE I HISTORIA**

#### Co trzeba zrobić:
```python
# NOWA TABELA: plan_versions
class PlanVersion(BaseModel):
    version_id: str
    plan_id: str
    version_number: int
    created_at: datetime
    days: List[DayPlan]
    metadata: Dict[str, Any]
    parent_version_id: Optional[str] = None  # dla rollback
    change_type: str  # "initial", "regenerated", "edited", "rollback"

# NOWY REPOSITORY: PlanVersionRepository
class PlanVersionRepository:
    def save_version(self, plan_id, version, change_type):
        """Save plan snapshot as new version."""
        pass
    
    def list_versions(self, plan_id) -> List[PlanVersion]:
        """Get all versions for plan."""
        pass
    
    def get_version(self, plan_id, version_number) -> PlanVersion:
        """Get specific version."""
        pass
    
    def diff_versions(self, version_a, version_b) -> Dict:
        """Compare two versions (MVP diff)."""
        return {
            "added_pois": [...],
            "removed_pois": [...],
            "time_changes": [...]
        }
    
    def rollback_to_version(self, plan_id, version_number):
        """Create NEW version from old snapshot."""
        old_version = self.get_version(plan_id, version_number)
        new_version = PlanVersion(
            version_id=str(uuid.uuid4()),
            plan_id=plan_id,
            version_number=self.get_next_version_number(plan_id),
            days=old_version.days,  # Copy old data
            parent_version_id=old_version.version_id,
            change_type="rollback"
        )
        self.save_version(plan_id, new_version, "rollback")
        return new_version

# API ENDPOINTS:
@router.get("/plans/{plan_id}/versions")
def list_plan_versions(plan_id: str):
    """List all versions of plan."""
    pass

@router.get("/plans/{plan_id}/versions/{version_num}")
def get_plan_version(plan_id: str, version_num: int):
    """Get specific version."""
    pass

@router.post("/plans/{plan_id}/versions/{version_num}/diff")
def diff_versions(plan_id: str, version_num: int, compare_to: int):
    """Compare two versions."""
    pass

@router.post("/plans/{plan_id}/rollback")
def rollback_plan(plan_id: str, to_version: int):
    """Rollback to old version (creates new version)."""
    pass
```

**Uwaga:** Versioning requires **PostgreSQL** - in-memory nie wystarczy!

**Szacunek:** 10-12 godzin

---

### **4. EDYCJA I NAPRAWA PLANU (MVP)**

#### Co trzeba zrobić:
```python
# NOWY MODUŁ: app/domain/planner/edit_engine.py

class PlanEditor:
    """Handle plan modifications with smart reflow."""
    
    def reorder_items(self, day_plan, item_id, new_position):
        """Reorder attraction with time reflow."""
        # 1. Extract item
        # 2. Recalculate transit times
        # 3. Shift all subsequent items
        pass
    
    def remove_item(self, day_plan, item_id, avoid_cooldown_hours=24):
        """Remove attraction and add to avoid list."""
        # 1. Remove item
        # 2. Add to user's avoid_pois with cooldown
        # 3. Reflow remaining items
        # 4. Optional: FILL_GAP with new POI
        pass
    
    def replace_item(self, day_plan, item_id, strategy="SMART_REPLACE"):
        """Replace attraction with similar alternative."""
        if strategy == "SMART_REPLACE":
            # Find POI with similar attributes
            # - Same categories/tags
            # - Similar duration
            # - Same time window compatibility
            # - NOT in avoid list
            pass
        elif strategy == "FILL_GAP":
            # Remove item, fill gap with best available
            pass
    
    def regenerate_day_fragment(self, day_plan, start_item, end_item):
        """Regenerate part of day between two items."""
        # 1. Keep start_item and end_item fixed
        # 2. Remove items between
        # 3. Run mini engine.build_day() for gap
        # 4. Stitch back together
        pass
    
    def reflow_day(self, day_plan):
        """Recalculate all times after edits."""
        # Update transit times, check opening hours, fix gaps
        pass

# API ENDPOINTS:
@router.post("/plans/{plan_id}/days/{day_num}/reorder")
def reorder_day_items(plan_id, day_num, item_id, new_position):
    pass

@router.delete("/plans/{plan_id}/days/{day_num}/items/{item_id}")
def remove_day_item(plan_id, day_num, item_id):
    pass

@router.post("/plans/{plan_id}/days/{day_num}/items/{item_id}/replace")
def replace_day_item(plan_id, day_num, item_id, strategy: str):
    pass

@router.post("/plans/{plan_id}/days/{day_num}/regenerate-fragment")
def regenerate_day_fragment(plan_id, day_num, start_item, end_item):
    pass
```

**Szacunek:** 16-20 godzin

---

### **5. MONETYZACJA I DOSTAWA**

#### 5.1 User Authentication (Login + Claim Guest)
```python
# NOWY MODUŁ: app/api/routes/auth.py

@router.post("/auth/login")
def login(email: str, password: str):
    """Login with email/password or social."""
    # TODO: JWT token generation
    pass

@router.post("/auth/register")
def register(email: str, password: str):
    """Register new user."""
    pass

@router.post("/auth/claim-guest-plan")
def claim_guest_plan(user_id: str, guest_plan_id: str):
    """Associate guest plan with logged-in user."""
    # Transfer ownership: guest -> user_id
    pass
```

**Szacunek:** 6-8 godzin

#### 5.2 Real Stripe Integration
```python
# UPDATE: app/api/routes/payment.py

import stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
def create_checkout_session(request: CreateCheckoutRequest):
    """Create REAL Stripe Checkout Session."""
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'pln',
                'product_data': {'name': 'Travel Plan'},
                'unit_amount': 4900,  # 49 PLN
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        metadata={'plan_id': request.plan_id}
    )
    return CheckoutSessionResponse(
        session_id=session.id,
        checkout_url=session.url
    )

@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks with signature validation."""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError as e:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(400, "Invalid signature")
    
    # Handle events
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        plan_id = session['metadata']['plan_id']
        
        # GRANT ACCESS
        entitlement_service.grant_access(plan_id, session['customer'])
        
        # TRIGGER PDF + EMAIL
        pdf_service.generate_async(plan_id)
        email_service.send_purchase_confirmation(plan_id)
    
    return {"received": True}

# NOWY MODUŁ: app/application/services/entitlement_service.py
class EntitlementService:
    def grant_access(self, plan_id, customer_id):
        """Mark plan as paid and accessible."""
        # Update plan metadata: {"paid": true, "customer_id": ...}
        pass
    
    def check_access(self, plan_id, user_id):
        """Verify if user can access plan."""
        # Check if plan.customer_id == user_id OR plan.paid == true
        pass
```

**Szacunek:** 8-10 godzin

#### 5.3 PDF Generation (Async)
```python
# NOWY MODUŁ: app/application/services/pdf_service.py

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import boto3  # dla S3 storage

class PDFService:
    def __init__(self, storage_service):
        self.storage = storage_service
    
    def generate_async(self, plan_id):
        """Queue PDF generation job."""
        # Use Celery or Railway cron job
        job_id = self.queue_job(plan_id)
        return job_id
    
    def generate_pdf(self, plan: PlanResponse) -> bytes:
        """Generate PDF from plan."""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # Render plan
        c.drawString(100, 800, f"Your Travel Plan - {plan.plan_id}")
        
        for day in plan.days:
            c.drawString(100, 750, f"Day {day.day_number}")
            y = 720
            for item in day.items:
                if item.type == "attraction":
                    c.drawString(120, y, f"{item.start_time} - {item.name}")
                    y -= 20
        
        c.save()
        return buffer.getvalue()
    
    def upload_to_storage(self, plan_id, pdf_bytes):
        """Upload PDF to S3 or Railway volume."""
        filename = f"plans/{plan_id}.pdf"
        self.storage.upload(filename, pdf_bytes)
        return self.storage.get_url(filename)

# API:
@router.get("/plans/{plan_id}/pdf")
def get_plan_pdf(plan_id: str, user_id: str):
    """Download PDF (auth required)."""
    if not entitlement_service.check_access(plan_id, user_id):
        raise HTTPException(403, "Access denied")
    
    pdf_url = pdf_service.get_or_generate(plan_id)
    return {"pdf_url": pdf_url}
```

**Szacunek:** 12-14 godzin

#### 5.4 Email Delivery (Outbox + Retry)
```python
# NOWY MODUŁ: app/infrastructure/email/

class EmailService:
    def __init__(self, smtp_config, outbox_repo):
        self.smtp = smtp_config
        self.outbox = outbox_repo
    
    def send_purchase_confirmation(self, plan_id):
        """Queue email for sending."""
        email = EmailMessage(
            to="user@example.com",
            subject="Your Travel Plan is Ready!",
            body=f"Your plan {plan_id} is ready. Download PDF: ...",
            attachments=["plan.pdf"]
        )
        self.outbox.queue(email)
    
    def send_queued_emails(self):
        """Worker function - sends pending emails."""
        pending = self.outbox.get_pending()
        for email in pending:
            try:
                self.smtp.send(email)
                self.outbox.mark_sent(email.id)
            except Exception as e:
                self.outbox.increment_retry(email.id)
                if email.retry_count > 3:
                    self.outbox.mark_failed(email.id)

# OUTBOX TABLE:
class EmailOutbox(BaseModel):
    id: str
    to: str
    subject: str
    body: str
    status: str  # pending, sent, failed
    retry_count: int
    created_at: datetime
    sent_at: Optional[datetime]
```

**Szacunek:** 8-10 godzin

---

### **6. ADMIN PANEL (Minimum)**

```python
# NOWY MODUŁ: app/api/routes/admin.py

@router.get("/admin/plans")
def list_all_plans(skip: int = 0, limit: int = 50):
    """List all generated plans."""
    pass

@router.get("/admin/plans/{plan_id}")
def get_plan_details(plan_id: str):
    """View plan details + metadata."""
    pass

@router.get("/admin/jobs")
def list_background_jobs():
    """List PDF generation jobs, email jobs."""
    pass

@router.get("/admin/exports")
def list_exports():
    """List generated PDFs."""
    pass

@router.get("/admin/emails")
def list_emails(status: str = "all"):
    """View email outbox."""
    pass

@router.get("/admin/errors")
def list_errors():
    """View error logs."""
    pass

@router.get("/admin/poi-quality")
def check_poi_quality():
    """POI quality dashboard:
    - Missing data (no prices, no coords, no hours)
    - Low must_see scores
    - Never selected POI
    """
    pass

# SIMPLE FRONTEND:
# - FastAPI Admin or minimal React dashboard
# - Read-only views
# - Basic filtering/sorting
```

**Szacunek:** 10-12 godzin

---

## 💰 WYCENA I PROPOZYCJA

### BREAKDOWN GODZINOWY (realistyczny szacunek):

| Moduł | Szacunek (h) | Kompleksowość |
|-------|--------------|---------------|
| **1. Multi-day Planning** | 18h | ⭐⭐⭐ High |
| **2. Quality + Explainability** | 14h | ⭐⭐ Medium |
| **3. Wersje i Historia (MVP)** | 10h | ⭐⭐ Medium |
| **4. Edycja i Naprawa (MVP)** | 16h | ⭐⭐⭐ High |
| **5.1 Auth (Login + Claim)** | 7h | ⭐ Low-Medium |
| **5.2 Stripe Integration** | 9h | ⭐⭐ Medium |
| **5.3 PDF Generation** | 12h | ⭐⭐ Medium |
| **5.4 Email + Outbox** | 9h | ⭐⭐ Medium |
| **6. Admin Panel (Basic)** | 10h | ⭐ Low |
| **PostgreSQL Migration** | 10h | ⭐⭐ Medium |
| **Testing + QA** | 22h | ⭐⭐⭐ High |
| **Deployment + DevOps** | 7h | ⭐ Low-Medium |
| **Dokumentacja + Handoff** | 8h | ⭐ Low |

**TOTAL:** **~152 godziny**

### MOJA PROPOZYCJA: 9,000 PLN

**Dlaczego ta cena jest uczciwa:**

#### 1. **Świadoma rezygnacja z zysku** 💡
- Standardowa stawka: 70 PLN/h × 152h = **10,640 PLN**
- Proponuję: **9,000 PLN** 
- **Oszczędzasz: 1,640 PLN** (~15% rabatu)
- **Mój zysk netto:** faktycznie ~59 PLN/h po uwzględnieniu podatków i kosztów

#### 2. **Kontynuacja współpracy** 🤝
Pracujemy już razem od Etapu 1, znam projekt od środka:
- Nie trzeba wdrażać nowego developera (koszt onboardingu: 20-30h)
- Kod jest dla mnie naturalny środowiskiem (zero friction)
- Mamy wypracowany workflow i komunikację
- **To przekłada się na jakość i szybkość**

#### 3. **Jakość zamiast ilości** ⚡
Nie szukam "najtańszej" stawki - szukam **długoterminowej wartości**:
- Clean code, który będzie łatwo rozwijać w Etapie 3
- Comprehensive tests (żeby nie wrócić za miesiąc "bo coś nie działa")
- Dokumentacja techniczna (żeby zespół mógł przejąć projekt)
- Architecture decisions udokumentowane

#### 4. **Ryzyko jest po mojej stronie** ⚠️
- Jeśli multi-day zajmie 25h zamiast 18h → **ja ponoszę koszt**
- Jeśli PostgreSQL migration będzie problematyczna → **mój czas**
- Jeśli Stripe wymaga więcej iteracji → **nie doliczam**
- **Fixed price = Twoje bezpieczeństwo**

#### 5. **To nie tylko kod** 📦
Dostarczam kompletny produkt:
- Działający backend (wszystkie endpointy)
- Migracje DB (Alembic)
- Testy (unit + integration)
- Deployment na Railway
- Dokumentacja API (Swagger)
- Technical handoff (sesja z zespołem)

---

### 🎁 BONUS: Co dostaniesz GRATIS (wartość ~2,500 PLN)

#### 1. **2 tygodnie wsparcia post-launch** (wartość: ~1,400 PLN)
- Hotfixy critical bugs (jeśli wystąpią)
- Odpowiedzi na pytania techniczne
- Pomoc przy pierwszych deploymentach
- **Availability: 24h response time**

#### 2. **Video dokumentacja techniczna** (wartość: ~700 PLN)
- 30-45 min nagranie screen capture
- Walkthrough przez architekturę Etapu 2
- Jak edytować plan, jak działa multi-day, jak testować Stripe
- **Dla Twojego zespołu / przyszłego developera**

#### 3. **Code review guidelines** (wartość: ~400 PLN)
- Dokument: "Jak rozwijać projekt dalej"
- Best practices dla tego codebase
- Common pitfalls i jak ich unikać
- **Future-proofing**

**Łącznie bonus: ~2,500 PLN wartości za 0 PLN extra!**

---

### 💳 MODEL PŁATNOŚCI (50/50)

**Bezpieczny dla obu stron:**

#### **Płatność 1: 4,500 PLN** (start prac)
- Po podpisaniu umowy
- Przed rozpoczęciem implementacji
- **Zabezpiecza:** Mój czas i commitment

#### **Płatność 2: 4,500 PLN** (akceptacja Etapu 2)
- Po dostarczeniu funkcjonalności
- Po Twoich testach i akceptacji
- Przed ostatecznymi poprawkami kosmetycznymi
- **Zabezpiecza:** Twoją satysfakcję z produktu

**Milestone dla płatności 2:**
- ✅ Multi-day planning działa (2-7 dni)
- ✅ Stripe przyjmuje płatności
- ✅ PDF generuje się poprawnie
- ✅ Email confirmation wysłany
- ✅ PostgreSQL deployed
- ✅ Wszystkie testy PASS
- ✅ Swagger docs updated

---

### 🎯 DLACZEGO TA OFERTA?

Mogę zrobić taniej? **Tak.**  
Będzie wtedy lepiej? **Nie.**

**Za 9,000 PLN dostajesz:**
- ✅ Profesjonalny, maintainable code
- ✅ Comprehensive testing
- ✅ Zero technical debt
- ✅ Dokumentację na przyszłość
- ✅ Wsparcie post-launch (2 tyg)
- ✅ Pewność, że wszystko działa

**Za 6,000-7,000 PLN dostaniesz:**
- ⚠️ "Działa, ale..."
- ⚠️ Minimalne testy
- ⚠️ Brak dokumentacji
- ⚠️ Problemy za 3 miesiące
- ⚠️ Koszt refactoringu: kolejne 5-8k PLN

**Wybór jest prosty:** Zainwestuj raz dobrze, albo płać dwa razy.

---

### 📊 COMPARISON: Co dostajesz vs Market

| Feature | Freelancer Budget | Freelancer Mid | **Moja oferta** | Software House |
|---------|-------------------|----------------|-----------------|----------------|
| **Cena** | 5-6k PLN | 12-15k PLN | **9,000 PLN** | 25-35k PLN |
| **Jakość kodu** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Testy** | ❌ Basic | ✅ Unit | ✅ Unit + Integration | ✅ Full QA team |
| **Dokumentacja** | ❌ Brak | ⚠️ README | ✅ Full + Video | ✅ Full |
| **Support post-launch** | ❌ Brak | ⚠️ 1 tydzień | ✅ **2 tygodnie** | ✅ 1 miesiąc |
| **Code ownership** | ✅ Twój | ✅ Twój | ✅ **Twój** | ⚠️ License |
| **Timeline** | ⚠️ 10-12 tyg | 8-10 tyg | ✅ **7 tygodni** | 12-16 tyg |
| **Komunikacja** | ⚠️ Wolna | ✅ Dobra | ✅ **Natychmiastowa** | ⚠️ PM layer |

**Sweet spot:** Jakość Software House, cena Freelancera Mid, timeline zoptymalizowany.

---

### ✅ PODSUMOWANIE OFERTY

**Zakres:** Pełny Etap 2 (wszystkie must-have + nice-to-have)  
**Cena:** 9,000 PLN (zamiast 10,640 PLN)  
**Płatność:** 50% start (4,500 PLN) + 50% akceptacja (4,500 PLN)  
**Timeline:** 7 tygodni (mid-Feb → early April)  
**Bonus:** 2 tyg support + video docs + guidelines (wartość: 2,500 PLN)  
**Gwarancja:** Fixed price (ryzyko po mojej stronie)  

**ROI dla Ciebie:**
- Gotowy produkt na launch wiosną
- Zero technical debt
- Kod gotowy na Etap 3
- Dokumentacja dla zespołu
- Peace of mind

---

## ⚠️ RYZYKA I WĄSKIE GARDŁA

### 1. **Multi-day Planning Complexity** 🔴 HIGH RISK
**Problem:**
- Engine obecnie planuje 1 dzień independent
- Multi-day wymaga cross-day state tracking (used POIs, core rotation, fatigue)
- Ryzyko: Dni mogą być zbyt podobne lub zbyt różne

**Mitigation:**
- Zaczynamy od prostej implementacji (loop przez dni + avoid lista)
- Iteracyjnie dodajemy "day vibe" i dywersyfikację
- Testy z prawdziwymi scenariuszami (2, 3, 5, 7 dni)

### 2. **Plan Editing - Reflow Logic** 🟡 MEDIUM RISK
**Problem:**
- Usuwanie/przestawianie POI wymaga przeliczeń transit times
- Opening hours mogą się zmienić po reflow
- Gap filling musi działać inteligentnie

**Mitigation:**
- Najpierw zaimplementuj remove + replace (łatwiejsze)
- Reorder jako ostatnie (najtrudniejsze)
- Unit tests dla każdego edit operation

### 3. **PostgreSQL Migration** 🟡 MEDIUM RISK
**Problem:**
- Obecnie in-memory repository
- Trzeba zaprojektować schema (plans, versions, users, entitlements)
- Railway + PostgreSQL addon

**Mitigation:**
- Repository interfaces już są - wystarczy podmienić implementację
- SQLAlchemy + Alembic migrations
- Schema review przed implementacją

### 4. **PDF Generation Performance** 🟡 MEDIUM RISK
**Problem:**
- PDF może być slow (reportlab rendering)
- Blocking generation = bad UX

**Mitigation:**
- Async generation (Celery + Redis lub Railway cron)
- Generate on payment, not on request
- Cache PDFs in S3/Railway volume

### 5. **Stripe Webhook Reliability** 🟢 LOW RISK
**Problem:**
- Webhooks mogą fail (network, server restart)
- Must be idempotent

**Mitigation:**
- Signature validation (prevent fake webhooks)
- Idempotency keys
- Retry logic w Stripe dashboard
- Test with Stripe CLI

### 6. **Email Delivery** 🟢 LOW RISK
**Problem:**
- SMTP może failować
- Spam filters

**Mitigation:**
- Outbox pattern (retry queue)
- Use SendGrid/Mailgun (nie raw SMTP)
- Email verification flow

---

## 🚀 CO ZROBIĆ KONIECZNIE TERAZ (POD LAUNCH WIOSNA)

### **MUST-HAVE (Minimum Viable Product):**

#### 1. **Multi-day Planning** 🔴 CRITICAL
**Dlaczego:** To core feature Etapu 2, bez tego nie ma produktu
**Priorytet:** #1
**Czas:** 20h

#### 2. **Stripe Integration + Entitlement** 🔴 CRITICAL
**Dlaczego:** Bez płatności nie ma monetyzacji
**Priorytet:** #2
**Czas:** 10h

#### 3. **PostgreSQL Migration** 🟠 HIGH
**Dlaczego:** In-memory nie wystarczy w production
- Plans persistence
- User accounts
- Payment records
**Priorytet:** #3
**Czas:** 10h

#### 4. **PDF Generation (Basic)** 🟠 HIGH
**Dlaczego:** User musi dostać deliverable po płatności
**Priorytet:** #4
**Czas:** 10h (uproszczony - bez fancy styling)

#### 5. **Email Confirmation** 🟠 HIGH
**Dlaczego:** Potwierdzenie zakupu + link do PDF
**Priorytet:** #5
**Czas:** 8h

#### 6. **Basic Plan Editing** 🟡 MEDIUM
**Dlaczego:** User chce móc usunąć/zamienić POI
**Priorytet:** #6
**Czas:** 12h (tylko remove + replace, bez reorder)

---

### **GOOD-TO-HAVE (Post-Launch):**

#### 7. **Plan Explainability** (why_selected)
- Można dodać post-launch
- Nice UX improvement, but not blocking

#### 8. **Admin Panel**
- Zrobimy prostą wersję (FastAPI Admin)
- Można rozbudować po launch

#### 9. **Plan Versioning (Full)**
- MVP: Save versions only
- Diff + rollback: Phase 3

#### 10. **Advanced Editing (Reorder + Regenerate Fragment)**
- MVP: Remove + Replace wystarczy
- Reorder: post-launch

---

## 📅 TIMELINE (REALISTYCZNY)

### **FAZA 1: CORE FUNCTIONALITY** (4 tygodnie)
**Tydzień 1-2:** Multi-day planning + PostgreSQL migration
**Tydzień 3:** Stripe integration + Entitlement logic
**Tydzień 4:** PDF + Email basic

### **FAZA 2: PRODUCT POLISH** (2 tygodnie)
**Tydzień 5:** Plan editing (remove + replace)
**Tydzień 6:** Testing + bug fixes

### **FAZA 3: LAUNCH PREP** (1 tydzień)
**Tydzień 7:** Deployment, monitoring, final QA

**TOTAL:** **7 tygodni** (mid-February → early April)

---

## 🎯 MOJA REKOMENDACJA: FULL SCOPE ZA 9,000 PLN

### Dlaczego warto?

**1. Wszystko, czego potrzebujesz na launch** ✅
Nie będziesz musiała prosić o "jeszcze jedną rzecz" za miesiąc:
- Multi-day planning (2-7 dni) ✅
- Stripe payments (real integration) ✅
- PostgreSQL (scalable storage) ✅
- PDF generation (deliverable) ✅
- Email confirmations ✅
- Plan editing (remove + replace) ✅
- Basic admin (monitoring) ✅
- Plan versioning (history tracking) ✅
- Quality checks + explainability ✅

**2. Produkt gotowy na growth** 🚀
Nie będziesz musiała "refactor" za pół roku:
- Clean Architecture (łatwa rozbudowa)
- Comprehensive tests (pewność przy zmianach)
- Dokumentacja (onboarding nowych ludzi)
- Scalable infrastructure (PostgreSQL + Railway)

**3. Zero technical debt** 💎
Nie będziesz płacić dwa razy:
- Kod pisany "na raz dobrze", nie "na szybko"
- Edge cases handled (nie tylko happy path)
- Error handling (graceful failures)
- Monitoring hooks (wiesz co się dzieje)

**4. Peace of mind** 😌
- Fixed price → **wiesz ile płacisz**
- 50/50 payment → **bezpieczeństwo dla obu stron**
- 2 tyg support → **spokój post-launch**
- Video docs → **zespół może przejąć**

---

### Co dostajesz za te 9,000 PLN?

#### **PRODUKT:**
- ✅ Pełny backend Etapu 2 (wszystkie moduły)
- ✅ PostgreSQL deployed na Railway
- ✅ Stripe live mode ready
- ✅ PDF generation working
- ✅ Email delivery configured
- ✅ Admin panel basic views

#### **JAKOŚĆ:**
- ✅ Unit tests (>80% coverage)
- ✅ Integration tests (API endpoints)
- ✅ Code documentation (docstrings)
- ✅ API docs (Swagger updated)
- ✅ Architecture docs (dla zespołu)

#### **WSPARCIE:**
- ✅ 2 tygodnie post-launch support
- ✅ Video walkthrough (30-45 min)
- ✅ Code review guidelines
- ✅ Handoff session z zespołem

#### **TIMELINE:**
- ✅ 7 tygodni (ready for April launch)
- ✅ Weekly progress updates
- ✅ Deployment na bieżąco (możesz testować)

---

### Alternatywy (dla porównania)

#### **Taniej (6-7k PLN):**
**Dostaniesz:**
- ⚠️ Tylko must-have features
- ⚠️ Minimalne testy
- ⚠️ Brak dokumentacji
- ⚠️ Brak supportu post-launch
- ⚠️ Problemy po 2-3 miesiącach

**Musisz dofinansować za 3 msc:**
- Refactoring: 3-5k PLN
- Bug fixes: 2-3k PLN
- Dokumentacja: 1-2k PLN
- **Total: 6k + 6k = 12k PLN**

#### **Drożej (15-20k PLN):**
**Dostaniesz:**
- ✅ Software house quality
- ✅ Full QA team
- ✅ Project manager layer
- ⚠️ Wolniejszy timeline (3-4 msc)
- ⚠️ Więcej biurokracji
- ⚠️ Mniej flexible na zmiany

**Za co płacisz:**
- 40% = developer (6-8k PLN)
- 30% = PM + meetings (4.5-6k PLN)
- 30% = overhead + marża (4.5-6k PLN)

#### **Moja oferta (9k PLN):**
**Sweet spot:**
- ✅ Jakość software house
- ✅ Flexible jak freelancer
- ✅ Timeline optymalny
- ✅ Direct communication (zero PM layer)
- ✅ Care about long-term success

---

## 📝 NASTĘPNE KROKI

Jeśli oferta Ci pasuje, oto jak to wygląda dalej:

### **KROK 1: Pełna specyfikacja techniczna** (Twoja strona)
- Doślij mi pełny dokument specyfikacji Etapu 2
- Przejrzę szczegóły i zaznaczę ewentualne pytania
- Upewnimy się, że jesteśmy na tej samej stronie
- **Czas:** 1-2 dni

### **KROK 2: Umowa + Faktura 1** (moja strona)
- Przygotuję umowę o dzieło / zlecenie (jak wolisz)
- Wystawię fakturę #1: **4,500 PLN** (50% zaliczki)
- Określimy milestones dla płatności #2
- **Czas:** 1 dzień

### **KROK 3: Kickoff Call** (razem)
- 30-45 min call (Google Meet / Zoom)
- Przegląd techniczny specyfikacji
- Ustalenie priorytetów (co first, co can wait)
- Q&A - wszystkie pytania które masz
- **Czas:** 1h (z przygotowaniem)

### **KROK 4: Start Implementation** (moja strona)
- Zaczynam od Multi-day planning (najbardziej krytyczne)
- Setup PostgreSQL + migrations
- Weekly updates (email / Slack)
- Deployment na bieżąco (możesz testować live)
- **Czas:** Tygodnie 1-4

### **KROK 5: Mid-point Review** (razem)
- Po 3-4 tygodniach: demo call
- Pokazuję co już działa (multi-day, DB, Stripe)
- Twój feedback + ewentualne adjustments
- Potwierdzamy scope dla drugiej połowy
- **Czas:** 30 min call

### **KROK 6: Finalizacja + Testing** (moja strona)
- Dokańczam pozostałe moduły (PDF, email, editing)
- Comprehensive testing (unit + integration)
- Bug fixing + polish
- Dokumentacja + video walkthrough
- **Czas:** Tygodnie 5-7

### **KROK 7: Akceptacja + Płatność 2** (Twoja strona)
- Daję Ci dostęp do testów
- Sprawdzasz wszystkie funkcjonalności
- Lista must-fix (jeśli są)
- Po akceptacji → Faktura #2: **4,500 PLN**
- **Czas:** 3-5 dni na Twoje testy

### **KROK 8: Handoff + Support** (razem)
- Session z Twoim zespołem (1-2h)
- Przekazanie dokumentacji
- Setup monitoring i alertów
- Start 2-tyg support period
- **Czas:** 1 dzień

---

## 💳 HARMONOGRAM PŁATNOŚCI

### **Płatność #1: 4,500 PLN** 💰
**Kiedy:** Po podpisaniu umowy, przed startem prac  
**Forma:** Faktura VAT / faktura pro forma  
**Termin:** 7 dni  
**Za co płacisz:** Commitment, rezerwacja mojego czasu, start implementation

### **Płatność #2: 4,500 PLN** 💰
**Kiedy:** Po dostarczeniu funkcjonalności i Twojej akceptacji  
**Forma:** Faktura VAT  
**Termin:** 7 dni  
**Za co płacisz:** Ukończony Etap 2, wszystkie moduły działają

**Milestone dla płatności #2:**
```
✅ Multi-day planning działa (tested: 2, 3, 5, 7 dni)
✅ Stripe przyjmuje płatności (test + live mode)
✅ PostgreSQL deployed i działa
✅ PDF generuje się poprawnie
✅ Email confirmation działa
✅ Plan editing (remove + replace) działa
✅ Admin panel podstawowy widok
✅ Wszystkie testy PASS (>80% coverage)
✅ Swagger docs updated
✅ Deployed na Railway
```

**Jeśli coś nie działa:**
- Naprawiam za darmo (w ramach umowy)
- Płatność #2 dopiero po Twojej akceptacji
- **Zero ryzyka dla Ciebie**

---

## ✅ CO GWARANTUJĘ

### **Commitment:**
- Pracuję full-time na Twoim projekcie (gdy już zacznę)
- Nie biorę innych projektów w tym czasie
- Dostępność: email < 24h, Slack < 4h (w weekendy < 48h)

### **Jakość:**
- Kod przejdzie moje internal code review
- Testy muszą być green przed delivery
- Dokumentacja musi być complete
- Zero known bugs w moment delivery

### **Timeline:**
- 7 tygodni to realistic estimate
- Jeśli skończę wcześniej → dostajesz wcześniej
- Jeśli zajmie dłużej (moja wina) → **nie doliczam**

### **Support post-launch:**
- 2 tygodnie wsparcia gratis
- Hotfixy critical bugs (jeśli wystąpią)
- Odpowiedzi na pytania techniczne
- Pomoc przy deploymentach

---

## ❓ FAQ

**Q: Co jeśli nie będę zadowolona z efektu?**  
A: Płatność #2 dopiero po Twojej akceptacji. Masz pełną kontrolę.

**Q: Co jeśli znajdę bug po 2 tygodniach supportu?**  
A: Critical bugs (app crashes, data loss) naprawiam zawsze. Minor bugs możemy ugadać (albo Etap 3).

**Q: Mogę zmienić zakres w trakcie?**  
A: Tak, ale jeśli zwiększa to scope → trzeba renegocjować cenę. Jeśli zmniejsza → zwracam proporcjonalnie.

**Q: Co jeśli projekt się opóźni z Twojej winy?**  
A: Nie doliczam za dodatkowy czas. Fixed price = fixed price.

**Q: Co jeśli projekt się opóźni z mojej winy (long review)?**  
A: Nic się nie zmienia, ale może to wpłynąć na April launch date.

**Q: Czy kod będzie mój?**  
A: Tak, 100%. Full ownership, no strings attached.

**Q: Co jeśli przestaniemy współpracować mid-project?**  
A: Umowa określa zasady rozwiązania. Dostajesz kod w obecnym stanie + dokumentację.

---

## ❓ PYTANIA DO CIEBIE

Zanim ruszymy dalej, potrzebuję od Ciebie feedback:

### **1. Wycena**
**Czy 9,000 PLN (płatność 50/50) jest OK?**
- [ ] Tak, akceptuję
- [ ] Chcę negocjować (co możemy zmienić?)
- [ ] Za drogo (jaki masz budżet?)

### **2. Zakres**
**Czy pełny scope Etapu 2 jest OK?**
- [ ] Tak, wszystko potrzebne
- [ ] Coś można wyciąć (co?)
- [ ] Coś brakuje (co dodać?)

### **3. Priorytet**
**Lista must-have OK?**
1. Multi-day planning
2. Stripe + Entitlement
3. PostgreSQL
4. PDF generation
5. Email confirmation
6. Basic editing

- [ ] Tak, dogadane
- [ ] Zmienić kolejność (jak?)
- [ ] Dodać coś (co?)

### **4. Timeline**
**Czy launch w April 2026 jest realistyczny?**
- [ ] Tak, mam tyle czasu
- [ ] Nie, muszę wcześniej (kiedy?)
- [ ] Mogę później (więcej czasu na testy)

### **5. Infrastruktura**
**Railway + PostgreSQL + SendGrid OK?**
- [ ] Tak, w porządku
- [ ] Wolę AWS / Heroku / inne (co?)
- [ ] Mam swoje konta (podać dane)

### **6. Komunikacja**
**Jak chcesz dostawać updates?**
- [ ] Email weekly (detailed)
- [ ] Slack daily (short)
- [ ] Google Meet co 2 tyg (demo)
- [ ] Mix (jaki?)

### **7. Dokumentacja**
**Co jest dla Ciebie ważne?**
- [ ] Technical docs (dla devów)
- [ ] API docs (Swagger)
- [ ] Video walkthroughs (dla zespołu)
- [ ] User guides (dla end users)
- [ ] Wszystko powyższe

---

## 📧 KONTAKT

**Email:** ngencode.dev@gmail.com  
**Preferowane:** Email (odpowiadam < 24h)  
**Dostępność:** Pn-Pt 9-18, weekendy < 48h  

**Jak odpowiedzieć:**
Możesz po prostu reply na ten email z odpowiedziami na pytania powyżej, albo:
- [ ] Chcę kickoff call najpierw (umów termin)
- [ ] Mam więcej pytań (napisz jakie)
- [ ] Potrzebuję czasu na przemyślenie (ile?)

---

**Pozdrawiam,**  
Mateusz Zurowski  
ngencode.dev@gmail.com

---

**P.S.** Masz rację co do fundamentów - niczego nie pomyliłaś! 🎉
- ✅ Mock Stripe - jest
- ✅ Repository Pattern - jest
- ✅ Clean Architecture - jest
- ✅ Planning Engine - działa świetnie (1 day)
- ✅ Scoring modułowy - 15+ modules
- ✅ API contracts - zgodne z feedbackiem

Mamy solidne fundamenty, Etap 2 to przede wszystkim orchestration i infrastructure! 🚀
