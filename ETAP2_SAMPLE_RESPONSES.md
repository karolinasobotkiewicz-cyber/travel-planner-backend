# ETAP 2 - Sample Responses dla Frontend

## 🌐 Staging URL

**Base URL:** `https://travel-planner-backend-xbsp.onrender.com`
**Swagger UI:** https://travel-planner-backend-xbsp.onrender.com/docs
**OpenAPI JSON:** https://travel-planner-backend-xbsp.onrender.com/openapi.json

**Status:** ✅ Live (auto-deploy z main branch)
**Version:** 2.0.0

---

## 📋 Sample Responses - ETAP 2 Endpoints

### 1. Generate Plan (Multi-day)

**Endpoint:** `POST /plan/preview`
**Auth:** Optional (Bearer token)

**Request:**
```json
{
  "location": "Zakopane",
  "groupType": "couple",
  "daysCount": 3,
  "budget": 2,
  "preferences": {
    "pace": "relaxed",
    "interests": ["nature", "wellness"],
    "activityLevel": "moderate"
  }
}
```

**Response (200 OK):**
```json
{
  "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7",
  "version": 1,
  "days": [
    {
      "day_number": 1,
      "date": "2026-03-01",
      "theme": "Mountain Views & Thermal Relaxation",
      "activities": [
        {
          "time": "09:00",
          "name": "Gubałówka Cable Car",
          "type": "attraction",
          "duration": 120,
          "description": "Scenic cable car ride to mountain viewpoint with panoramic Tatra views",
          "location": {
            "lat": 49.296,
            "lng": 19.952,
            "address": "Droga Stanisława Zubka, 34-500 Zakopane"
          },
          "category": "nature",
          "poi_id": "22",
          "cost": 45.0,
          "booking_required": false,
          "opening_hours": "09:00-17:00"
        },
        {
          "time": "11:30",
          "name": "Góralska Tradycja",
          "type": "restaurant",
          "duration": 60,
          "description": "Traditional highlander restaurant with authentic regional cuisine",
          "location": {
            "lat": 49.295,
            "lng": 19.953,
            "address": "Krupówki 12, 34-500 Zakopane"
          },
          "category": "food",
          "poi_id": "45",
          "cost": 50.0,
          "cuisine": "Polish"
        },
        {
          "time": "13:00",
          "name": "Krupówki Promenade",
          "type": "activity",
          "duration": 90,
          "description": "Stroll along the main street with local shops and highland atmosphere",
          "location": {
            "lat": 49.295,
            "lng": 19.951,
            "address": "Krupówki, 34-500 Zakopane"
          },
          "category": "culture",
          "poi_id": "67",
          "cost": 0.0
        },
        {
          "time": "15:00",
          "name": "Termy Zakoplanskie",
          "type": "wellness",
          "duration": 180,
          "description": "Modern thermal spa complex with indoor and outdoor pools, mountain views",
          "location": {
            "lat": 49.278,
            "lng": 19.964,
            "address": "Jagiellońska 31B, 34-500 Zakopane"
          },
          "category": "wellness",
          "poi_id": "2",
          "cost": 119.0,
          "booking_required": true,
          "opening_hours": "10:00-22:00"
        },
        {
          "time": "18:30",
          "name": "Karczma Sabała",
          "type": "restaurant",
          "duration": 90,
          "description": "Historic highlander inn with traditional Polish mountain cuisine",
          "location": {
            "lat": 49.296,
            "lng": 19.950,
            "address": "Krupówki 11, 34-500 Zakopane"
          },
          "category": "food",
          "poi_id": "89",
          "cost": 85.0,
          "cuisine": "Polish"
        }
      ]
    },
    {
      "day_number": 2,
      "date": "2026-03-02",
      "theme": "Mountain Hiking & Nature",
      "activities": [
        {
          "time": "08:00",
          "name": "Morskie Oko",
          "type": "attraction",
          "duration": 180,
          "description": "Iconic mountain lake, most popular Tatra hiking destination",
          "location": {
            "lat": 49.201,
            "lng": 20.071,
            "address": "Droga do Morskiego Oka, 34-500 Zakopane"
          },
          "category": "nature",
          "poi_id": "35",
          "cost": 44.0,
          "booking_required": false,
          "opening_hours": "06:00-19:00"
        },
        {
          "time": "12:00",
          "name": "Schronisko PTTK Palenica Białczańska",
          "type": "restaurant",
          "duration": 60,
          "description": "Mountain lodge with traditional meals and stunning views",
          "location": {
            "lat": 49.237,
            "lng": 20.061,
            "address": "Palenica Białczańska, 34-500 Zakopane"
          },
          "category": "food",
          "poi_id": "112",
          "cost": 40.0,
          "cuisine": "Polish"
        },
        {
          "time": "14:00",
          "name": "Dolina Kościeliska",
          "type": "activity",
          "duration": 120,
          "description": "Scenic valley trail with caves and mountain streams",
          "location": {
            "lat": 49.260,
            "lng": 19.871,
            "address": "Kościeliska Valley, 34-500 Zakopane"
          },
          "category": "nature",
          "poi_id": "28",
          "cost": 6.0,
          "booking_required": false
        },
        {
          "time": "17:00",
          "name": "Cafe Tygodnik Podhalański",
          "type": "restaurant",
          "duration": 60,
          "description": "Cozy highland café with regional pastries and coffee",
          "location": {
            "lat": 49.294,
            "lng": 19.949,
            "address": "Krupówki 20, 34-500 Zakopane"
          },
          "category": "food",
          "poi_id": "134",
          "cost": 25.0,
          "cuisine": "Polish"
        },
        {
          "time": "19:00",
          "name": "Restauracja Owczarnia",
          "type": "restaurant",
          "duration": 90,
          "description": "Traditional shepherd's hut style restaurant with live folk music",
          "location": {
            "lat": 49.297,
            "lng": 19.948,
            "address": "Zamoyskiego 2, 34-500 Zakopane"
          },
          "category": "food",
          "poi_id": "156",
          "cost": 95.0,
          "cuisine": "Polish"
        }
      ]
    },
    {
      "day_number": 3,
      "date": "2026-03-03",
      "theme": "Culture & Gentle Nature",
      "activities": [
        {
          "time": "10:00",
          "name": "Muzeum Tatrzańskie",
          "type": "attraction",
          "duration": 90,
          "description": "Museum showcasing Tatra mountain history and highland culture",
          "location": {
            "lat": 49.295,
            "lng": 19.954,
            "address": "Krupówki 10, 34-500 Zakopane"
          },
          "category": "culture",
          "poi_id": "178",
          "cost": 18.0,
          "booking_required": false,
          "opening_hours": "09:00-17:00"
        },
        {
          "time": "12:00",
          "name": "Piekarnia Klimek",
          "type": "restaurant",
          "duration": 45,
          "description": "Local bakery famous for traditional oscypek cheese and zapiekanka",
          "location": {
            "lat": 49.296,
            "lng": 19.951,
            "address": "Krupówki 8, 34-500 Zakopane"
          },
          "category": "food",
          "poi_id": "190",
          "cost": 20.0,
          "cuisine": "Polish"
        },
        {
          "time": "13:30",
          "name": "Rusinowa Polana",
          "type": "activity",
          "duration": 120,
          "description": "Gentle forest trail with meadows and mountain views, perfect for relaxed walk",
          "location": {
            "lat": 49.249,
            "lng": 19.911,
            "address": "Rusinowa Polana trail, 34-500 Zakopane"
          },
          "category": "nature",
          "poi_id": "41",
          "cost": 0.0
        },
        {
          "time": "16:00",
          "name": "Wielka Krokiew Ski Jump",
          "type": "attraction",
          "duration": 60,
          "description": "Visit the famous Olympic ski jump complex with observation deck",
          "location": {
            "lat": 49.280,
            "lng": 19.954,
            "address": "Bronisława Czecha 1, 34-500 Zakopane"
          },
          "category": "sport",
          "poi_id": "25",
          "cost": 15.0
        },
        {
          "time": "18:30",
          "name": "RestauracjaCzarny Potok",
          "type": "restaurant",
          "duration": 120,
          "description": "Upscale highlander restaurant with modern take on traditional cuisine",
          "location": {
            "lat": 49.293,
            "lng": 19.956,
            "address": "Tetmajera 18, 34-500 Zakopane"
          },
          "category": "food",
          "poi_id": "201",
          "cost": 120.0,
          "cuisine": "Polish"
        }
      ]
    }
  ]
}
```

---

### 2. Get Plan

**Endpoint:** `GET /plan/{plan_id}`
**Auth:** Optional

**Response (200 OK):**
```json
{
  "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7",
  "version": 2,
  "days": [
    {
      "day_number": 1,
      "date": "2026-03-01",
      "theme": "Mountain Views & Thermal Relaxation",
      "activities": [
        {
          "time": "09:00",
          "name": "Gubałówka Cable Car",
          "type": "attraction",
          "duration": 120,
          "description": "Scenic cable car ride to mountain viewpoint with panoramic Tatra views",
          "location": {
            "lat": 49.296,
            "lng": 19.952,
            "address": "Droga Stanisława Zubka, 34-500 Zakopane"
          },
          "category": "nature",
          "poi_id": "22",
          "cost": 45.0
        }
      ]
    }
  ]
}
```

---

### 3. Get Plan Versions

**Endpoint:** `GET /plan/{plan_id}/versions`
**Auth:** Optional

**Response (200 OK):**
```json
{
  "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7",
  "current_version": 3,
  "versions": [
    {
      "version_number": 1,
      "created_at": "2026-02-25T10:30:00Z",
      "change_type": "initial",
      "change_summary": "Initial plan created (version 1)",
      "parent_version_id": null
    },
    {
      "version_number": 2,
      "created_at": "2026-02-25T11:15:00Z",
      "change_type": "remove_activity",
      "change_summary": "Removed activity at index 2 from day 1",
      "parent_version_id": "v1-uuid"
    },
    {
      "version_number": 3,
      "created_at": "2026-02-25T12:00:00Z",
      "change_type": "replace_activity",
      "change_summary": "Replaced activity at index 1 on day 2 with 'New Restaurant'",
      "parent_version_id": "v2-uuid"
    }
  ]
}
```

---

### 4. Get Specific Version

**Endpoint:** `GET /plan/{plan_id}/versions/{version_number}`
**Auth:** Optional

**Response (200 OK):**
```json
{
  "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7",
  "version": 1,
  "days": [
    {
      "day_number": 1,
      "date": "2026-03-01",
      "activities": [
        {
          "time": "09:00",
          "name": "Original Activity",
          "type": "attraction"
        }
      ]
    }
  ]
}
```

---

### 5. Remove Activity

**Endpoint:** `POST /plan/{plan_id}/days/{day_number}/remove`
**Auth:** Optional

**Request:**
```json
{
  "activity_indices": [2]
}
```

**Response (200 OK):**
```json
{
  "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7",
  "version": 4,
  "days": [
    {
      "day_number": 1,
      "date": "2026-03-01",
      "activities": [
        {
          "time": "09:00",
          "name": "Activity 1"
        },
        {
          "time": "11:00",
          "name": "Activity 2"
        }
      ]
    }
  ]
}
```

---

### 6. Replace Activity

**Endpoint:** `POST /plan/{plan_id}/days/{day_number}/replace`
**Auth:** Optional

**Request:**
```json
{
  "activity_index": 1,
  "new_activity": "Sukiennice",
  "replace_mode": "similar"
}
```

**Response (200 OK):**
```json
{
  "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7",
  "version": 5,
  "days": [
    {
      "day_number": 1,
      "date": "2026-03-01",
      "activities": [
        {
          "time": "09:00",
          "name": "Wawel Castle"
        },
        {
          "time": "11:00",
          "name": "Sukiennice",
          "type": "attraction",
          "description": "Historic trading hall in the Main Square",
          "location": {
            "lat": 50.062,
            "lng": 19.937
          },
          "category": "culture",
          "cost": 0.0
        },
        {
          "time": "13:00",
          "name": "Restaurant"
        }
      ]
    }
  ]
}
```

---

### 7. Create Payment Checkout Session

**Endpoint:** `POST /payment/create-checkout-session`
**Auth:** ✅ Required (Bearer token)

**Request:**
```json
{
  "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7"
}
```

**Response (200 OK):**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
  "session_id": "cs_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated"
}
```

---

### 8. Get Payment Session Status

**Endpoint:** `GET /payment/session/{session_id}/status`
**Auth:** ✅ Required (Bearer token)

**Response (200 OK - Pending):**
```json
{
  "session_id": "cs_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "payment_status": "pending",
  "status": "open",
  "amount_total": 1999,
  "currency": "pln",
  "created_at": "2026-02-25T14:30:00Z",
  "expires_at": "2026-02-26T14:30:00Z"
}
```

**Response (200 OK - Completed):**
```json
{
  "session_id": "cs_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "payment_status": "paid",
  "status": "complete",
  "amount_total": 1999,
  "currency": "pln",
  "created_at": "2026-02-25T14:30:00Z",
  "completed_at": "2026-02-25T14:35:00Z"
}
```

**Response (200 OK - Expired):**
```json
{
  "session_id": "cs_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "payment_status": "unpaid",
  "status": "expired",
  "amount_total": 1999,
  "currency": "pln",
  "created_at": "2026-02-25T14:30:00Z",
  "expires_at": "2026-02-26T14:30:00Z"
}
```

---

### 9. Claim Guest Plans (NEW in ETAP 2!)

**Endpoint:** `POST /plan/claim-guest-plans`
**Auth:** ✅ Required (Bearer token)

**Request:**
```json
{
  "guest_id": "b8e4d930-5e23-4f9b-8c4d-g2f3e9b6d8c8"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "transferred_plans": 3,
  "user_id": "776fcb06-c71a-4595-88b1-d18d21fd6a24"
}
```

**Response (200 OK - No plans):**
```json
{
  "success": true,
  "transferred_plans": 0,
  "user_id": "776fcb06-c71a-4595-88b1-d18d21fd6a24"
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated"
}
```

---

### 10. Get My Plans (NEW in ETAP 2!)

**Endpoint:** `GET /plan/my-plans`
**Auth:** ✅ Required (Bearer token)

**Response (200 OK):**
```json
{
  "plans": [
    {
      "plan_id": "a7f3c829-4d12-4e8a-9b3c-f1e2d8a5c6b7",
      "location": "Zakopane",
      "days_count": 3,
      "created_at": "2026-02-25T10:30:00Z",
      "updated_at": "2026-02-25T12:00:00Z",
      "version": 3
    },
    {
      "plan_id": "c9f5e831-6f34-5g0c-9d5e-h3g4f0c7e9d9",
      "location": "Warszawa",
      "days_count": 2,
      "created_at": "2026-02-24T15:20:00Z",
      "updated_at": "2026-02-24T15:20:00Z",
      "version": 1
    },
    {
      "plan_id": "e1g7f043-8h56-6h2e-0f7g-j5h6g2e9f1e1",
      "location": "Gdańsk",
      "days_count": 4,
      "created_at": "2026-02-23T09:15:00Z",
      "updated_at": "2026-02-23T11:45:00Z",
      "version": 2
    }
  ],
  "total_count": 3
}
```

**Response (200 OK - Empty):**
```json
{
  "plans": [],
  "total_count": 0
}
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated"
}
```

---

## 🔐 Authentication Headers

All protected endpoints require JWT token:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**How to get token:**
1. User logs in via Supabase Auth
2. Supabase returns `access_token`
3. Frontend includes token in API requests

---

## 🌐 CORS Configuration

**Allowed Origins:**
- `http://localhost:3000` (development)
- `https://lets-travel.pl` (production)

**Allowed Methods:** GET, POST, PUT, DELETE, OPTIONS

**Allowed Headers:** Content-Type, Authorization

---

## 📊 Status & Entitlements Model

### Payment Status Values:
- `pending` - Payment session created, awaiting completion
- `paid` - Payment successful (confirmed by webhook)
- `unpaid` - Payment failed or cancelled
- `expired` - Checkout session expired (24h timeout)

### Plan Access Logic (for frontend):
```javascript
function canUserAccessPlan(plan, paymentStatus) {
  // Free preview (1 day plans)
  if (plan.days_count === 1) {
    return true;
  }
  
  // Paid plans
  if (paymentStatus === 'paid') {
    return true;
  }
  
  // Pending payment - show prompt
  if (paymentStatus === 'pending') {
    return false; // Show "Complete payment" button
  }
  
  // Unpaid - show paywall
  return false; // Show "Purchase plan" button
}
```

### Polling Strategy:
```javascript
// Poll payment status every 3-5 seconds after Stripe redirect
async function pollPaymentStatus(sessionId, maxAttempts = 20) {
  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`/payment/session/${sessionId}/status`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    
    if (data.payment_status === 'paid') {
      return 'success';
    } else if (data.payment_status === 'unpaid' || data.payment_status === 'expired') {
      return 'failed';
    }
    
    // Still pending, wait 3 seconds
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  
  return 'timeout'; // Stop after 60 seconds
}
```

---

## 🧪 Testing Credentials

### Supabase
- **URL:** https://supabase.com/dashboard/project/usztzcigcnsyyatguxay
- **JWT Secret:** `pvaAG1JoRNPiJf7y2Y0XcCPscCnzKr6OFKfTSB+qlpJNFewjVrJWcPOpBTNJ28jF43xPjZj1dxscXoLtQqgm1A==`

### Stripe Test Mode
- **Publishable Key:** `pk_test_51T3z24HKwaztaoKBqd8ewYPw`
- **Test Card (Success):** `4242 4242 4242 4242`
- **Test Card (Declined):** `4000 0000 0000 0002`
- **Date:** 12/34 | **CVC:** 123

---

## 📝 Notes for Frontend

1. **Guest → Auth Flow:**
   - Guest creates plans (no auth) → `user_id = NULL` in DB
   - User signs up/logs in
   - Frontend calls `/claim-guest-plans` with `guest_id` from localStorage
   - Backend transfers ownership

2. **Payment Flow:**
   - User clicks "Buy Plan"
   - Frontend calls `/create-checkout-session`
   - Redirect to `checkout_url`
   - User pays on Stripe
   - Stripe redirects back with `?session_id=xxx`
   - Frontend polls `/session/{id}/status` until `paid`

3. **Error Handling:**
   - 401: Redirect to login
   - 404: Plan not found
   - 500: Show generic error message

4. **Backward Compatibility:**
   - `/preview` endpoint works with AND without auth
   - Legacy behavior preserved
