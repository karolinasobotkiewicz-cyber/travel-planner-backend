# 📦 ETAP 2 - Pakiet dla Frontendu

## 🎯 Co dostajecie

Kompletny pakiet dokumentacji i narzędzi do rozpoczęcia implementacji frontendu bez rozjazdów z backendem.

---

## 🌐 Środowisko Staging

**Base URL:** https://travel-planner-backend-xbsp.onrender.com

**Swagger UI:** https://travel-planner-backend-xbsp.onrender.com/docs

**OpenAPI JSON:** https://travel-planner-backend-xbsp.onrender.com/openapi.json

**Status:** ✅ Live (19 endpointów)

**Wersja:** 2.0.0

---

## 📋 Pliki w pakiecie

### 1️⃣ **Travel_Planner_ETAP2.postman_collection.json**
**Kolekcja Postman - gotowa do importu i testowania**

**Jak użyć:**
1. Otwórz Postman
2. File → Import → wybierz plik
3. Ustaw zmienne w Collection variables:
   - `baseUrl`: `https://travel-planner-backend-xbsp.onrender.com`
   - `authToken`: Twój JWT token z Supabase (opcjonalnie)
4. Uruchom requesty!

**Co zawiera:**
- ✅ 17 gotowych requestów pogrupowanych w 6 folderów
- ✅ Automatyczne zapisywanie `planId` i `sessionId` do zmiennych
- ✅ Pre-configured auth headers
- ✅ Przykładowe requesty z realnymi danymi
- ✅ Opisy każdego endpointa

**Foldery:**
1. **Plan Management** (5 requestów) - tworzenie, pobieranie, wersjonowanie
2. **Plan Editing** (4 requesty) - usuwanie, zastępowanie, regeneracja
3. **Payment (ETAP 2)** (2 requesty) - checkout session, status
4. **User Management (ETAP 2)** (2 requesty) - moje plany, claim guest plans
5. **Content & POI** (2 requesty) - home content, POI details
6. **System** (2 requesty) - health check, root

**Zmienne automatyczne:**
- Po "Generate Plan" → zapisuje `{{planId}}`
- Po "Create Checkout Session" → zapisuje `{{sessionId}}`
- Możesz od razu używać ich w kolejnych requestach!

---

### 2️⃣ **ETAP2_SAMPLE_RESPONSES.md**
**Realne przykłady JSON z backendu**

**Jak użyć:**
- Otwórz w edytorze markdown
- Kopiuj JSON do mocków frontendowych
- Używaj jako reference podczas implementacji typów TypeScript

**Co zawiera:**
- ✅ 10 kluczowych endpointów ETAPU 2
- ✅ Pełny przykład 3-dniowego planu dla Zakopanego (15 aktywności)
- ✅ Wszystkie scenariusze payment status (pending, paid, unpaid, expired)
- ✅ Nowe endpointy: `/claim-guest-plans`, `/my-plans`
- ✅ Przykłady wersjonowania i edycji planu
- ✅ Model Status & Entitlements z kodem JavaScript
- ✅ Strategia pollowania (jak długo, jak często)
- ✅ Wszystkie error responses (401, 404, 500)

**Przykładowe endpointy:**
1. Generate Plan (multi-day) - pełny 3-dniowy plan
2. Get Plan - aktualny plan z wszystkimi szczegółami
3. Get Plan Versions - historia zmian
4. Get Specific Version - konkretna wersja
5. Remove Activity - usunięcie aktywności (before/after)
6. Replace Activity - zastąpienie aktywności (before/after)
7. Create Checkout Session - inicjacja płatności
8. Get Payment Status - 3 warianty (pending, paid, expired)
9. Claim Guest Plans - transfer guest → user
10. Get My Plans - lista planów użytkownika

---

### 3️⃣ **ETAP2_API_SPECIFICATION.json**
**Kompletna specyfikacja OpenAPI 3.x**

**Jak użyć:**
- Import do Postman (alternatywa dla collection)
- Import do swagger-codegen / openapi-generator
- Generuj TypeScript types: `npx openapi-typescript ETAP2_API_SPECIFICATION.json -o types.ts`
- Reference podczas tworzenia API client

**Co zawiera:**
- ✅ Wszystkie 19 endpointów z pełnymi definicjami
- ✅ Request/Response schemas
- ✅ Authentication requirements (Bearer token)
- ✅ Error responses
- ✅ Zgodność z OpenAPI 3.0.2

---

### 4️⃣ **ETAP2_FRONTEND_INTEGRATION_GUIDE.md**
**Kompletny przewodnik integracji z kodem**

**Jak użyć:**
- Przeczytaj sekcję "Quick Start" - 5 min overview
- Zaimplementuj flows wg przykładów (Guest Flow, Auth Flow, Payment Flow)
- Skopiuj funkcje pomocnicze (polling, error handling)
- Użyj checklist na końcu jako TODO list

**Co zawiera:**
- ✅ 5 głównych flows z kodem JavaScript:
  1. **Guest Flow** - użytkownik bez konta
  2. **Auth Flow** - użytkownik z kontem
  3. **Migration Flow** - guest → auth (claim plans)
  4. **Payment Flow** - checkout + polling status
  5. **My Plans Flow** - lista planów użytkownika
- ✅ Strategia pollowania (kod gotowy do skopiowania)
- ✅ Error handling patterns
- ✅ CORS configuration (co jest dozwolone)
- ✅ Complete endpoint reference (curl examples)
- ✅ Testing examples
- ✅ Integration checklist

**Przykładowy kod:**
```javascript
// Payment Flow - gotowy do użycia!
async function createPayment(planId, token) {
  const response = await fetch(`${API_URL}/payment/create-checkout-session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ plan_id: planId })
  });
  const data = await response.json();
  window.location.href = data.checkout_url; // Redirect to Stripe
}
```

---

### 5️⃣ **get_supabase_token.html** ⭐
**Prosty sposób na pobranie JWT tokenu (dla Karoliny)**

**Jak użyć:**
1. Stwórz testowego użytkownika w Supabase Dashboard
2. Otwórz plik w przeglądarce (double-click)
3. Wpisz email i hasło
4. Kliknij "Zaloguj i pobierz token"
5. Skopiuj token (przycisk "Skopiuj token")

**Co robi:**
- ✅ Loguje się do Supabase przez API
- ✅ Pobiera JWT Access Token
- ✅ Wyświetla go w czytelny sposób
- ✅ Przycisk kopiowania do schowka
- ✅ Instrukcje jak użyć tokenu

**Kiedy użyć:**
- Potrzebujesz tokenu do test_platnosci.html
- Potrzebujesz tokenu do Postman
- Token wygasł (ważny ~1h) i potrzebujesz nowego

**Bez technicznej wiedzy - tylko 3 kliki!**

---

### 6️⃣ **test_platnosci.html**
**Narzędzie do testowania płatności (dla Karoliny)**

**Jak użyć:**
1. Otwórz plik w przeglądarce (double-click)
2. (Opcjonalnie) Wklej JWT token z Supabase (użyj get_supabase_token.html!)
3. Kliknij "Start Payment Test"
4. Zapłać kartą testową: `4242 4242 4242 4242`
5. Po powrocie ze Stripe - poczekaj na automatyczne sprawdzenie statusu

**Co robi:**
- ✅ Tworzy testowy plan
- ✅ Tworzy sesję płatności
- ✅ Przekierowuje do Stripe
- ✅ Po powrocie automatycznie polluje status
- ✅ Pokazuje sukces/error z linkami do weryfikacji

**Bez instalacji, bez kodu, bez technicznej wiedzy!**

---

### 7️⃣ **JAK_TESTOWAC_PLATNOSCI.md**
**Instrukcje testowania płatności**

**Dla kogo:** Karolina / testerzy nietechiniczni

**Co zawiera:**
- ✅ Metoda 1: HTML (najłatwiejsza) - opis tool powyżej
- ✅ Metoda 2: API testing (curl/Python) - dla devs
- ✅ Weryfikacja w Stripe Dashboard
- ✅ Weryfikacja w Supabase (SQL queries)
- ✅ Testowe karty Stripe (sukces, failure, 3D Secure)
- ✅ Troubleshooting

---

### 8️⃣ **ETAP2_COMPLETION_REPORT.md**
**Raport implementacji - co zostało zrobione**

**Dla kogo:** Dokumentacja / onboarding / historia projektu

**Co zawiera:**
- ✅ Executive summary
- ✅ Wszystkie 7 faz ETAPU 2 (status każdej)
- ✅ Nowe endpointy - opis i użycie
- ✅ Production verification (7 testów)
- ✅ Metryki (221 linii kodu, 19 endpointów)
- ✅ Deployment details
- ✅ Final checklist

---

## 🔐 Credentials Testowe

### Supabase (Authentication)
- **Dashboard:** https://supabase.com/dashboard
- **Project:** [Twój projekt]
- **JWT Secret:** `pvaAG1JoRNPiJf7y2Y0XcCPscCnzKr6OFKfTSB+qlpJNFewjVrJWcPOpBTNJ28jF43xPjZj1dxscXoLtQqgm1A==`

**Jak dostać JWT token:**

**Metoda 1: Prosty HTML tool (NAJŁATWIEJSZA!)** ⭐
1. Stwórz użytkownika w Supabase Dashboard (Authentication → Users → Add user)
2. Otwórz **get_supabase_token.html** w przeglądarce
3. Wpisz email i hasło
4. Kliknij "Zaloguj i pobierz token"
5. Skopiuj token (przycisk "Skopiuj token")
6. Użyj w Postman lub test_platnosci.html

**Metoda 2: Dashboard (NIE DZIAŁA - token nie jest widoczny)**
- ~~Supabase Dashboard nie pokazuje bezpośrednio Access Token~~
- ❌ Użyj Metody 1 zamiast tego!

**Format tokenu w API:**
- Header: `Authorization: Bearer <token>`
- Token ważny przez: ~1 godzinę (potem pobierz nowy przez get_supabase_token.html)

### Stripe (Payments)
- **Dashboard:** https://dashboard.stripe.com/test
- **Mode:** Test Mode
- **Price:** 19.99 PLN (1999 cents)

**Testowe karty:**
- ✅ Sukces: `4242 4242 4242 4242`
- ❌ Declined: `4000 0000 0000 0002`
- 🔒 3D Secure: `4000 0027 6000 3184`
- **Expiry:** Dowolna przyszła data (np. 12/34)
- **CVC:** Dowolne 3 cyfry (np. 123)

---

## 🚀 Quick Start dla Frontendu

### Krok 1: Import Postman Collection
```bash
# Otwórz Postman
# File → Import → Travel_Planner_ETAP2.postman_collection.json
# Ustaw zmienne:
#   - baseUrl: https://travel-planner-backend-xbsp.onrender.com
#   - authToken: (opcjonalnie - dla endpointów z auth)
```

### Krok 2: Wygeneruj TypeScript Types (opcjonalnie)
```bash
npm install -g openapi-typescript
openapi-typescript ETAP2_API_SPECIFICATION.json -o src/types/api.ts
```

### Krok 3: Stwórz API Client
```typescript
// src/api/client.ts
const API_URL = 'https://travel-planner-backend-xbsp.onrender.com';

export async function generatePlan(params: GeneratePlanParams) {
  const response = await fetch(`${API_URL}/plan/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  return response.json();
}

// Więcej w ETAP2_FRONTEND_INTEGRATION_GUIDE.md
```

### Krok 4: Użyj Sample Responses do Mocków
```typescript
// src/mocks/plans.ts
export const mockPlan = {
  // Skopiuj z ETAP2_SAMPLE_RESPONSES.md
  "plan_id": "a3f4e2d1-8b7c-4e9f-a2b3-c4d5e6f7g8h9",
  "location": "Zakopane",
  "days_count": 3,
  "days": [ /* ... */ ]
};
```

### Krok 5: Zaimplementuj Payment Flow
```typescript
// Wzorowany na ETAP2_FRONTEND_INTEGRATION_GUIDE.md
async function handlePayment(planId: string, token: string) {
  // 1. Create checkout session
  const session = await createCheckoutSession(planId, token);
  
  // 2. Redirect to Stripe
  window.location.href = session.checkout_url;
  
  // 3. Po powrocie: poll status
  const status = await pollPaymentStatus(session.session_id, token);
  
  // 4. Show result
  if (status.payment_status === 'paid') {
    showSuccess();
  }
}
```

---

## 📊 Status & Entitlements Model

### Payment Status Values
- `pending` - Czeka na płatność
- `paid` - Opłacony (pełny dostęp)
- `unpaid` - Nieudana płatność
- `expired` - Sesja wygasła (24h)

### Access Control (JavaScript)
```javascript
function canAccessPlan(plan) {
  if (!plan.has_paid) return false; // nieoptacony = brak dostępu
  if (plan.payment_status !== 'paid') return false; // tylko 'paid'
  return true; // wszystko OK
}

function showPlanUI(plan) {
  if (canAccessPlan(plan)) {
    // Pokaż pełny plan
    renderFullPlan(plan);
  } else {
    // Pokaż paywall
    renderPaywall(plan);
  }
}
```

**Pełny przykład w:** `ETAP2_SAMPLE_RESPONSES.md` (sekcja "Status & Entitlements Model")

---

## 🔄 Polling Strategy

**Kiedy pollować:**
- Po powrocie ze Stripe Checkout (payment redirect)
- Po kliknięciu "Check Payment" (user action)

**Jak długo:**
- Interwał: **3-5 sekund**
- Max czas: **60 sekund** (12-20 prób)
- Po timeout: Pokaż "Sprawdź później" + link do ręcznej weryfikacji

**Kod gotowy do użycia:**
```javascript
async function pollPaymentStatus(sessionId, token, maxAttempts = 20) {
  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(
      `${API_URL}/payment/session/${sessionId}/status`,
      { headers: { 'Authorization': `Bearer ${token}` } }
    );
    const data = await response.json();
    
    if (data.payment_status === 'paid') {
      return { success: true, data };
    }
    if (data.payment_status === 'unpaid' || data.payment_status === 'expired') {
      return { success: false, data };
    }
    
    await new Promise(resolve => setTimeout(resolve, 3000)); // 3s
  }
  
  return { timeout: true }; // Po 60s bez rezultatu
}
```

**Pełny przykład:** `ETAP2_FRONTEND_INTEGRATION_GUIDE.md` (sekcja "Payment Polling Strategy")

---

## 🛡️ CORS Configuration

**Dozwolone originy:**
- `http://localhost:3000` (development)
- `https://lets-travel.pl` (production)

**Dozwolone metody:**
- GET, POST, PUT, DELETE, OPTIONS

**Dozwolone headers:**
- Content-Type, Authorization

**Credentials:** Allowed

**Test CORS z konsoli przeglądarki:**
```javascript
fetch('https://travel-planner-backend-xbsp.onrender.com/health')
  .then(r => r.json())
  .then(console.log); // Powinno zadziałać!
```

---

## ✅ Integration Checklist

### Frontend TODO:
- [ ] Zaimportować Postman collection i przetestować requesty
- [ ] Przeczytać `ETAP2_FRONTEND_INTEGRATION_GUIDE.md`
- [ ] Wygenerować TypeScript types z OpenAPI spec
- [ ] Stworzyć API client z funkcjami z Integration Guide
- [ ] Zaimplementować 5 głównych flows (Guest, Auth, Migration, Payment, My Plans)
- [ ] Użyć sample responses jako mocki podczas developmentu
- [ ] Zaimplementować payment polling (3s interval, 60s max)
- [ ] Dodać error handling (401, 404, 500)
- [ ] Przetestować guest → auth migration flow
- [ ] Przetestować payment flow z kartą testową

### Design/UX TODO:
- [ ] Paywall UI (gdy `has_paid = false`)
- [ ] Payment success page
- [ ] Payment error/expired handling
- [ ] "My Plans" dashboard page
- [ ] Guest → Auth migration prompt ("Zaloguj się aby zachować plany")

### Testing TODO:
- [ ] Happy path: Guest tworzy plan → płaci → widzi pełen plan
- [ ] Edge case: Guest tworzy plan → loguje się → claim plans → płaci
- [ ] Error case: Płatność nieudana (karta odrzucona)
- [ ] Timeout case: Polling > 60s bez rezultatu
- [ ] Auth case: Token expired (401) → redirect to login

---

## 🆘 Pomoc i Wsparcie

### Problemy z API:
1. Sprawdź Swagger UI: https://travel-planner-backend-xbsp.onrender.com/docs
2. Użyj Postman collection do debugowania
3. Sprawdź sample responses - czy odpowiedź się zgadza?

### Problemy z Auth:
1. Sprawdź czy token jest poprawny (nie wygasł)
2. Sprawdź format header: `Authorization: Bearer <token>`
3. Endpointy payment/my-plans/claim-guest-plans WYMAGAJĄ auth!

### Problemy z Payment:
1. Sprawdź czy używasz test mode w Stripe
2. Użyj karty `4242 4242 4242 4242`
3. Użyj `test_platnosci.html` do szybkiego testu
4. Sprawdź czy pollingujesz status po redirect

### Inne pytania:
- Napisz do zespołu backend :)

---

## 📞 Kontakt

**Backend:** Dostępny na staging 24/7 (Render auto-healing)

**Swagger:** https://travel-planner-backend-xbsp.onrender.com/docs

**Health Check:** https://travel-planner-backend-xbsp.onrender.com/health

---

## 🎉 Gotowe do integracji!

Wszystko przetestowane, udokumentowane i gotowe do użycia. Frontend może startować bez rozjazdów! 🚀

**Happy coding!** 💻✨
