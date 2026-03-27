# ETAP 2: Frontend Integration Guide

## 📋 Overview

This document provides complete integration instructions for the Travel Planner API (ETAP 2).

**API Base URL:** `https://travel-planner-backend-xbsp.onrender.com`
**API Version:** 2.0.0
**Total Endpoints:** 19

---

## 🔐 Authentication

### Supabase JWT Authentication

The API uses **Supabase JWT tokens** for authentication.

**Backend Configuration:**
- JWT Secret: `pvaAG1JoRNPiJf7y2Y0XcCPscCnzKr6OFKfTSB+qlpJNFewjVrJWcPOpBTNJ28jF43xPjZj1dxscXoLtQqgm1A==`
- Algorithm: HS256
- Token header: `Authorization: Bearer <token>`

**Frontend Flow:**
1. User signs up/logs in via Supabase
2. Supabase returns JWT token
3. Frontend stores token (localStorage/sessionStorage)
4. Frontend includes token in API requests: `Authorization: Bearer <token>`

**Token Structure:**
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "iat": 1234567890,
  "exp": 1234571490
}
```

**Protected Endpoints:**
- ✅ `/payment/*` - All payment endpoints require auth
- ✅ `/plan/claim-guest-plans` - Requires auth
- ✅ `/plan/my-plans` - Requires auth
- ❌ `/plan/preview` - Optional auth (backward compatibility)

---

## 🎯 Core Flows

### 1️⃣ Guest User Flow (No Auth)

**Scenario:** User wants to try the app without signing up.

```javascript
// Step 1: Generate plan as guest
const tripInput = {
  location: "Kraków",
  groupType: "couple",
  daysCount: 3,
  budget: 2,
  preferences: {
    pace: "relaxed",
    interests: ["culture", "food"]
  }
};

const response = await fetch('https://travel-planner-backend-xbsp.onrender.com/plan/preview', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
    // NO Authorization header
  },
  body: JSON.stringify(tripInput)
});

const plan = await response.json();
console.log('Plan ID:', plan.plan_id);

// Step 2: Store plan_id in localStorage (no user_id linked in backend)
localStorage.setItem('guest_plans', JSON.stringify([plan.plan_id]));
```

**Backend Behavior:**
- Plan saved with `user_id = NULL` (guest plan)
- Plan accessible via `/plan/{plan_id}` endpoint
- No authentication required

---

### 2️⃣ Authenticated User Flow

**Scenario:** User signs up/logs in before creating plans.

```javascript
// Step 1: User logs in via Supabase
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'password123'
});

const jwtToken = data.session.access_token;
localStorage.setItem('auth_token', jwtToken);

// Step 2: Generate plan with authentication
const response = await fetch('https://travel-planner-backend-xbsp.onrender.com/plan/preview', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${jwtToken}`
  },
  body: JSON.stringify(tripInput)
});

const plan = await response.json();
console.log('Plan ID:', plan.plan_id);
```

**Backend Behavior:**
- JWT decoded, user_id extracted
- Plan saved with `user_id = <authenticated-user-id>`
- Plan linked to user account
- Accessible via `/plan/my-plans` endpoint

---

### 3️⃣ Guest → Authenticated Migration Flow

**Scenario:** Guest creates plans, then signs up/logs in. Need to claim guest plans.

```javascript
// Step 1: Guest creates plans (before auth)
const guestId = generateUUID(); // Frontend generates guest_id
localStorage.setItem('guest_id', guestId);

// Create plan as guest (no auth token)
const planResponse = await createPlanAsGuest(tripInput);
// Plan saved with user_id = NULL

// Step 2: User decides to sign up/login
const { data } = await supabase.auth.signUp({
  email: 'newuser@example.com',
  password: 'password123'
});

const jwtToken = data.session.access_token;

// Step 3: Claim guest plans (transfer ownership)
const claimResponse = await fetch('https://travel-planner-backend-xbsp.onrender.com/plan/claim-guest-plans', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${jwtToken}` // REQUIRED
  },
  body: JSON.stringify({
    guest_id: localStorage.getItem('guest_id')
  })
});

const result = await claimResponse.json();
console.log('Transferred plans:', result.transferred_plans);
// { "success": true, "transferred_plans": 3, "user_id": "uuid" }

// Step 4: Clean up localStorage
localStorage.removeItem('guest_id');
localStorage.removeItem('guest_plans');
```

**Backend Behavior:**
- Finds all plans with `user_id = NULL` (guest plans)
- Updates `user_id` to authenticated user's ID
- Returns count of transferred plans

**⚠️ Important Notes:**
- Guest plans have `user_id = NULL` (not linked to any user)
- `/claim-guest-plans` requires authentication (401 if no token)
- Backend transfers ALL guest plans (assumes single-device session)
- Frontend should call this endpoint **immediately after signup/login**

---

### 4️⃣ View User's Plans

**Scenario:** Display "My Plans" page for authenticated user.

```javascript
// Fetch all plans for logged-in user
const response = await fetch('https://travel-planner-backend-xbsp.onrender.com/plan/my-plans', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${jwtToken}` // REQUIRED
  }
});

const data = await response.json();
console.log('Total plans:', data.total_count);

// Example response:
// {
//   "plans": [
//     {
//       "plan_id": "uuid-1",
//       "location": "Kraków",
//       "days_count": 3,
//       "created_at": "2025-01-30T12:00:00",
//       "updated_at": "2025-01-30T14:30:00",
//       "version": 2
//     },
//     {
//       "plan_id": "uuid-2",
//       "location": "Gdańsk",
//       "days_count": 2,
//       "created_at": "2025-01-29T10:00:00",
//       "updated_at": "2025-01-29T10:00:00",
//       "version": 1
//     }
//   ],
//   "total_count": 2
// }

// Render plans in UI
data.plans.forEach(plan => {
  renderPlanCard(plan);
});
```

**Backend Behavior:**
- Requires authentication (401 if no token)
- Fetches all plans where `user_id = <authenticated-user-id>`
- Returns metadata for each plan (no full day details)
- Ordered by `created_at DESC` (newest first)

---

## 💳 Payment Flow

### Complete Payment Integration

**Scenario:** User wants to purchase a plan.

```javascript
// Step 1: Create Stripe Checkout Session
const checkoutResponse = await fetch('https://travel-planner-backend-xbsp.onrender.com/payment/create-checkout-session', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${jwtToken}` // REQUIRED
  },
  body: JSON.stringify({
    plan_id: 'uuid-of-plan'
  })
});

const checkoutData = await checkoutResponse.json();
console.log('Checkout URL:', checkoutData.checkout_url);
console.log('Session ID:', checkoutData.session_id);

// Step 2: Redirect user to Stripe Checkout
window.location.href = checkoutData.checkout_url;

// Step 3: User completes payment on Stripe
// Stripe redirects back to success_url or cancel_url

// Step 4: Poll payment status (on return from Stripe)
const sessionId = new URLSearchParams(window.location.search).get('session_id');

async function pollPaymentStatus(sessionId) {
  const response = await fetch(`https://travel-planner-backend-xbsp.onrender.com/payment/session/${sessionId}/status`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${jwtToken}` // REQUIRED
    }
  });
  
  const status = await response.json();
  console.log('Payment status:', status.payment_status);
  
  // Example response:
  // {
  //   "payment_status": "paid", // or "pending", "unpaid", "expired"
  //   "status": "complete",
  //   "amount_total": 1999
  // }
  
  if (status.payment_status === 'paid') {
    // Payment successful! Show confirmation
    showSuccessMessage();
  } else if (status.payment_status === 'pending') {
    // Still processing, poll again in 3 seconds
    setTimeout(() => pollPaymentStatus(sessionId), 3000);
  } else {
    // Payment failed or expired
    showErrorMessage();
  }
}

// Start polling after redirect from Stripe
if (sessionId) {
  pollPaymentStatus(sessionId);
}
```

**Backend Behavior:**
1. `/create-checkout-session`:
   - Creates Stripe Checkout Session
   - Saves PaymentSession to database (status: `PENDING`)
   - Returns `checkout_url` and `session_id`
2. User completes payment on Stripe
3. Stripe webhook calls `/payment/stripe/webhook`:
   - Updates PaymentSession status to `COMPLETE`
   - Creates Transaction record
4. `/session/{id}/status`:
   - Returns current payment status for frontend polling

**Payment Statuses:**
- `pending` - Payment session created, awaiting completion
- `paid` - Payment successful, confirmed by webhook
- `unpaid` - Payment session expired or cancelled
- `expired` - Checkout session expired (24h timeout)

**Frontend Polling Strategy:**
- Poll every 3-5 seconds after redirect from Stripe
- Max 10-20 polls (stop after 30-60 seconds)
- If still pending after 60s, show "Check back later" message
- Webhook updates database in real-time (polling catches updates)

---

## 📊 Plan Status & Entitlements Model

### Understanding Plan Access

**Plan Statuses (stored in `trip_metadata.status`):**
- `ready` - Plan generated successfully, ready to use
- `pending` - Plan generation in progress
- `failed` - Plan generation failed

**Payment Statuses (from PaymentSession table):**
- `PENDING` - Checkout session created, payment not completed
- `COMPLETE` - Payment successful
- `EXPIRED` - Checkout session expired (user didn't pay within 24h)

**Frontend Decision Logic:**

```javascript
// Pseudo-code for frontend access control
function canAccessPlan(plan, paymentStatus) {
  // Free preview: Always accessible
  if (plan.days_count <= 1) {
    return true;
  }
  
  // Paid plans: Check payment status
  if (paymentStatus === 'COMPLETE') {
    return true;
  }
  
  // Pending payment: Show "Complete payment" prompt
  if (paymentStatus === 'PENDING') {
    showPaymentPendingPrompt(plan.checkout_url);
    return false;
  }
  
  // Unpaid: Show paywall
  showPaywallPrompt(plan.plan_id);
  return false;
}
```

**When to Poll Payment Status:**
1. After redirect from Stripe Checkout (query param: `?session_id=xxx`)
2. When user opens a plan that has `payment_status !== 'paid'`
3. When user navigates to "My Plans" page (check all plans)

**Stop Polling When:**
1. `payment_status === 'paid'` (success)
2. `payment_status === 'unpaid'` or `'expired'` (failure)
3. After 10-20 polls (timeout)

---

## 🌐 CORS Configuration

**Allowed Origins:**
- `http://localhost:3000` (development)
- `https://lets-travel.pl` (production)

**Allowed Methods:**
- GET, POST, PUT, DELETE, OPTIONS

**Allowed Headers:**
- Content-Type, Authorization

**⚠️ Important:** If frontend uses different domain, ask backend team to add to CORS_ORIGINS.

---

## 📚 Complete Endpoint Reference

### Plan Endpoints

#### 1. `POST /plan/preview`
Generate new travel plan (optional auth).

**Request:**
```json
{
  "location": "Kraków",
  "groupType": "couple",
  "daysCount": 3,
  "budget": 2,
  "preferences": {
    "pace": "relaxed",
    "interests": ["culture", "food"],
    "activityLevel": "moderate"
  }
}
```

**Response:**
```json
{
  "plan_id": "uuid",
  "version": 1,
  "days": [
    {
      "day_number": 1,
      "date": "2025-02-01",
      "activities": [
        {
          "time": "09:00",
          "name": "Wawel Castle",
          "category": "attraction",
          "location": { "lat": 50.054, "lng": 19.935 }
        }
      ]
    }
  ]
}
```

**Headers:**
- `Authorization: Bearer <token>` - Optional (plan linked to user if provided)

---

#### 2. `POST /plan/claim-guest-plans` ✨ NEW
Transfer guest plans to authenticated user.

**Request:**
```json
{
  "guest_id": "uuid-from-localstorage"
}
```

**Response:**
```json
{
  "success": true,
  "transferred_plans": 3,
  "user_id": "authenticated-user-uuid"
}
```

**Headers:**
- `Authorization: Bearer <token>` - **REQUIRED** (401 if missing)

**Use Case:** Call immediately after user signs up/logs in.

---

#### 3. `GET /plan/my-plans` ✨ NEW
Get all plans for authenticated user.

**Response:**
```json
{
  "plans": [
    {
      "plan_id": "uuid-1",
      "location": "Kraków",
      "days_count": 3,
      "created_at": "2025-01-30T12:00:00",
      "updated_at": "2025-01-30T14:30:00",
      "version": 2
    }
  ],
  "total_count": 1
}
```

**Headers:**
- `Authorization: Bearer <token>` - **REQUIRED**

---

#### 4. `GET /plan/{plan_id}`
Get full plan details.

**Response:** Same as `/preview` response.

**Headers:**
- `Authorization: Bearer <token>` - Optional

---

#### 5. `GET /plan/{plan_id}/status`
Get plan generation status.

**Response:**
```json
{
  "plan_id": "uuid",
  "status": "ready",
  "progress": 100
}
```

---

#### 6. `GET /plan/{plan_id}/versions`
Get all version history.

**Response:**
```json
{
  "versions": [
    {
      "version_number": 1,
      "created_at": "2025-01-30T12:00:00",
      "change_type": "initial"
    },
    {
      "version_number": 2,
      "created_at": "2025-01-30T14:30:00",
      "change_type": "regenerated"
    }
  ]
}
```

---

#### 7. `GET /plan/{plan_id}/versions/{version_number}`
Get specific version.

**Response:** Full plan data for that version.

---

#### 8. `POST /plan/{plan_id}/rollback`
Rollback to previous version.

**Request:**
```json
{
  "target_version": 1
}
```

**Response:** Full plan data after rollback.

---

#### 9. `POST /plan/{plan_id}/days/{day_number}/remove`
Remove specific activity from day.

**Request:**
```json
{
  "activity_indices": [0, 2]
}
```

**Response:** Updated plan.

---

#### 10. `POST /plan/{plan_id}/days/{day_number}/replace`
Replace activity with new one.

**Request:**
```json
{
  "activity_index": 1,
  "new_activity": "Kazimierz District",
  "replace_mode": "similar"
}
```

**Response:** Updated plan.

---

#### 11. `POST /plan/{plan_id}/days/{day_number}/regenerate`
Regenerate specific time range in a day.

**Request:**
```json
{
  "from_time": "14:00",
  "to_time": "18:00",
  "pinned_items": ["Wawel Castle"]
}
```

**Response:** Updated plan.

---

### Payment Endpoints

#### 12. `POST /payment/create-checkout-session` 🔐
Create Stripe Checkout session.

**Request:**
```json
{
  "plan_id": "uuid"
}
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_test_..."
}
```

**Headers:**
- `Authorization: Bearer <token>` - **REQUIRED**

---

#### 13. `GET /payment/session/{session_id}/status` 🔐
Get payment session status (for polling).

**Response:**
```json
{
  "payment_status": "paid",
  "status": "complete",
  "amount_total": 1999
}
```

**Headers:**
- `Authorization: Bearer <token>` - **REQUIRED**

---

#### 14. `POST /payment/stripe/webhook`
Stripe webhook handler (backend only).

**⚠️ Do NOT call from frontend.** Stripe calls this directly.

---

### Content Endpoints

#### 15. `GET /content/home`
Get homepage content (hero, features, testimonials).

**Response:**
```json
{
  "hero": {
    "title": "Plan Your Perfect Trip",
    "subtitle": "AI-powered travel planning"
  },
  "features": [...],
  "testimonials": [...]
}
```

---

### POI Endpoints

#### 16. `GET /poi/{poi_id}`
Get POI details.

**Response:**
```json
{
  "poi_id": "123",
  "name": "Wawel Castle",
  "category": "attraction",
  "location": { "lat": 50.054, "lng": 19.935 },
  "opening_hours": "09:00-18:00"
}
```

---

### Admin Endpoints

#### 17. `POST /admin/reload-poi`
Reload POI database (admin only).

**Response:**
```json
{
  "success": true,
  "message": "POI database reloaded"
}
```

---

### Health Check

#### 18. `GET /health`
Check API health.

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "database": "connected"
}
```

---

#### 19. `GET /`
Root endpoint.

**Response:**
```json
{
  "message": "Travel Planner API",
  "version": "2.0.0"
}
```

---

## 🧪 Testing Examples

### Example 1: Generate Plan as Guest

```bash
curl -X POST https://travel-planner-backend-xbsp.onrender.com/plan/preview \
  -H "Content-Type: application/json" \
  -d '{
    "location": "Kraków",
    "groupType": "couple",
    "daysCount": 2,
    "budget": 2,
    "preferences": {
      "pace": "relaxed",
      "interests": ["culture", "food"]
    }
  }'
```

---

### Example 2: Claim Guest Plans

```bash
curl -X POST https://travel-planner-backend-xbsp.onrender.com/plan/claim-guest-plans \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "guest_id": "uuid-from-localstorage"
  }'
```

---

### Example 3: Get My Plans

```bash
curl -X GET https://travel-planner-backend-xbsp.onrender.com/plan/my-plans \
  -H "Authorization: Bearer <your-jwt-token>"
```

---

### Example 4: Create Payment

```bash
curl -X POST https://travel-planner-backend-xbsp.onrender.com/payment/create-checkout-session \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "plan_id": "uuid-of-plan"
  }'
```

---

### Example 5: Check Payment Status

```bash
curl -X GET https://travel-planner-backend-xbsp.onrender.com/payment/session/cs_test_abc123/status \
  -H "Authorization: Bearer <your-jwt-token>"
```

---

## ⚠️ Error Handling

### Common HTTP Status Codes

- **200 OK** - Success
- **400 Bad Request** - Invalid request body/parameters
- **401 Unauthorized** - Missing or invalid JWT token
- **404 Not Found** - Plan/resource not found
- **500 Internal Server Error** - Backend error

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Frontend Error Handling Strategy

```javascript
async function apiCall(endpoint, options) {
  try {
    const response = await fetch(endpoint, options);
    
    if (response.status === 401) {
      // Token expired or invalid
      handleAuthError();
      return null;
    }
    
    if (response.status === 404) {
      // Resource not found
      showNotFoundMessage();
      return null;
    }
    
    if (!response.ok) {
      const error = await response.json();
      showErrorMessage(error.detail);
      return null;
    }
    
    return await response.json();
    
  } catch (error) {
    console.error('API call failed:', error);
    showNetworkErrorMessage();
    return null;
  }
}
```

---

## 📞 Support

**Backend Repository:** https://github.com/karolinasobotkiewicz-cyber/travel-planner-backend

**API Documentation (Swagger UI):** https://travel-planner-backend-xbsp.onrender.com/docs

**Contact:** For questions or issues, contact backend team.

---

## ✅ Integration Checklist

- [ ] Supabase authentication configured
- [ ] JWT token stored in localStorage/sessionStorage
- [ ] Authorization header included in protected endpoints
- [ ] Guest→Auth migration flow implemented (/claim-guest-plans)
- [ ] Payment flow implemented (create checkout → redirect → poll status)
- [ ] Error handling for 401, 404, 500
- [ ] CORS allowed origin configured (ask if needed)
- [ ] Polling strategy implemented (3-5 seconds, max 60s)
- [ ] "My Plans" page implemented (/my-plans endpoint)
- [ ] OpenAPI spec imported (ETAP2_API_SPECIFICATION.json)

---

**🎉 ETAP 2 Complete!** All endpoints documented, tested, and ready for frontend integration.
