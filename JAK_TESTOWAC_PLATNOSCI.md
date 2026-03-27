# Jak testować płatności - Przewodnik dla klientki

## ✨ METODA 1: Prosty HTML (NAJŁATWIEJSZA!) ✨

### Krok 1: Otwórz plik testowy
1. Otwórz plik **`test_platnosci.html`** w przeglądarce (dwukrotne kliknięcie)
2. Zobaczysz ładny formularz

### Krok 2: Wklej JWT token
1. Zaloguj się do [Supabase Dashboard](https://supabase.com/dashboard/project/usztzcigcnsyyatguxay)
2. Idź do: **Authentication** → **Users** → kliknij na dowolnego usera
3. Skopiuj **Access Token** (długi tekst zaczynający się od `eyJ...`)
4. Wklej do formularza

### Krok 3: Kliknij przycisk
1. Kliknij **"Rozpocznij Test Płatności"**
2. Poczekaj chwilę (tworzy plan + sesję płatności)
3. Automatycznie przekieruje Cię do Stripe

### Krok 4: Zapłać testową kartą
```
Numer karty: 4242 4242 4242 4242
Data ważności: 12/34
CVC: 123
```

### Krok 5: Gotowe!
Po zapłaceniu wrócisz do formularza i zobaczysz:
- ✅ **PŁATNOŚĆ ZAKOŃCZONA SUKCESEM!**
- Linki do weryfikacji w Stripe i Supabase

**To wszystko! Nie musisz wiedzieć nic o API, curl czy programowaniu.** 😊

---

## 📊 Weryfikacja wyniku

Po udanej płatności sprawdź:

### W Stripe Dashboard:
1. Wejdź: https://dashboard.stripe.com/test/payments
2. Znajdź swoją płatność (najnowsza)
3. Status: **Succeeded** ✅

### W Supabase:
1. Wejdź: https://supabase.com/dashboard/project/usztzcigcnsyyatguxay/editor
2. Tabela: **payment_sessions**
3. Status: **COMPLETE** ✅

---

## 🎯 METODA 2: Szybki test przez API (dla bardziej technicznych)

### Krok 1: Stwórz plan z autoryzacją

```bash
# 1. Zaloguj się w Supabase i skopiuj JWT token
# 2. Wyślij request:

curl -X POST https://travel-planner-backend-xbsp.onrender.com/plan/preview \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TWOJ_JWT_TOKEN" \
  -d '{
    "location": "Kraków",
    "groupType": "couple",
    "daysCount": 2,
    "budget": 2,
    "preferences": {
      "pace": "relaxed",
      "interests": ["culture"]
    }
  }'

# ZAPISZ plan_id z odpowiedzi!
```

---

### Krok 2: Stwórz sesję płatności

```bash
curl -X POST https://travel-planner-backend-xbsp.onrender.com/payment/create-checkout-session \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TWOJ_JWT_TOKEN" \
  -d '{
    "plan_id": "PLAN_ID_Z_KROKU_1"
  }'

# Otrzymasz:
# {
#   "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
#   "session_id": "cs_test_..."
# }
```

---

### Krok 3: Zapłać testową kartą Stripe

**Otwórz `checkout_url` w przeglądarce i użyj testowej karty:**

✅ **SUKCES (płatność przejdzie):**
```
Numer karty: 4242 4242 4242 4242
Data ważności: 12/34 (dowolna przyszła data)
CVC: 123 (dowolne 3 cyfry)
```

❌ **ODRZUCONA (płatność się nie powiedzie):**
```
Numer karty: 4000 0000 0000 0002
Data ważności: 12/34
CVC: 123
```

🔄 **WYMAGA AUTORYZACJI 3D Secure:**
```
Numer karty: 4000 0027 6000 3184
Data ważności: 12/34
CVC: 123
(Stripe pokaże testowy ekran 3D Secure - kliknij "Complete")
```

---

### Krok 4: Sprawdź status płatności

```bash
curl -X GET https://travel-planner-backend-xbsp.onrender.com/payment/session/SESSION_ID_Z_KROKU_2/status \
  -H "Authorization: Bearer TWOJ_JWT_TOKEN"

# Odpowiedź:
# {
#   "payment_status": "paid",      ← Powinna być "paid" po udanej płatności
#   "status": "complete",
#   "amount_total": 1999
# }
```

---

## 🔍 Weryfikacja w Stripe Dashboard

### 1. Sprawdź płatności w Stripe

Wejdź na: https://dashboard.stripe.com/test/payments

- **Payment List** - zobaczysz wszystkie testowe płatności
- Status: **Succeeded** = płatność przeszła ✅
- Status: **Failed** = płatność odrzucona ❌

### 2. Sprawdź webhook events

Wejdź na: https://dashboard.stripe.com/test/webhooks/we_...

- Znajdź swój webhook: `https://travel-planner-backend-xbsp.onrender.com/payment/stripe/webhook`
- Kliknij na event `checkout.session.completed`
- Sprawdź:
  - **Response code:** Powinno być `200 OK` ✅
  - **Response body:** Sprawdź czy backend odpowiedział poprawnie
  - Jeśli widzisz error 401/500 - coś jest nie tak

### 3. Sprawdź checkout sessions

Wejdź na: https://dashboard.stripe.com/test/checkout-sessions

- Znajdź swoją sesję (po session_id)
- Status: **Complete** = płatność zakończona sukcesem
- Status: **Open** = użytkownik jeszcze nie zapłacił
- Status: **Expired** = sesja wygasła (24h timeout)

---

## 📊 Weryfikacja w bazie danych (Supabase)

### Sprawdź tabelę payment_sessions

Wejdź na: https://supabase.com/dashboard/project/usztzcigcnsyyatguxay/editor

```sql
-- Sprawdź ostatnie płatności
SELECT 
  id,
  plan_id,
  user_id,
  stripe_session_id,
  status,
  amount_total,
  created_at
FROM payment_sessions
ORDER BY created_at DESC
LIMIT 10;

-- Status powinien być: COMPLETE (sukces) lub PENDING (czeka)
```

### Sprawdź tabelę transactions

```sql
-- Sprawdź potwierdzone transakcje
SELECT 
  id,
  payment_session_id,
  stripe_payment_intent_id,
  amount,
  currency,
  status,
  created_at
FROM transactions
ORDER BY created_at DESC
LIMIT 10;

-- Status powinien być: succeeded
```

---

## 🛠️ Testowanie bez frontendu (tylko backend)

### Metoda 1: Postman / Insomnia

1. Zaimportuj: `ETAP2_API_SPECIFICATION.json`
2. Ustaw zmienną `{{baseUrl}}`: `https://travel-planner-backend-xbsp.onrender.com`
3. Ustaw zmienną `{{authToken}}`: Twój JWT z Supabase
4. Wykonaj requesty w kolejności:
   - POST /plan/preview
   - POST /payment/create-checkout-session
   - Otwórz checkout_url w przeglądarce
   - GET /payment/session/{id}/status

### Metoda 2: Python script

Stwórz plik `test_payment_manual.py`:

```python
import requests
import time
import webbrowser

BASE_URL = "https://travel-planner-backend-xbsp.onrender.com"
JWT_TOKEN = "TWOJ_JWT_TOKEN"  # Wklej tu token z Supabase

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Stwórz plan
print("1. Tworzę plan...")
plan_response = requests.post(
    f"{BASE_URL}/plan/preview",
    headers=headers,
    json={
        "location": "Kraków",
        "groupType": "couple",
        "daysCount": 2,
        "budget": 2,
        "preferences": {"pace": "relaxed", "interests": ["culture"]}
    }
)
plan_id = plan_response.json()["plan_id"]
print(f"   Plan ID: {plan_id}")

# 2. Stwórz sesję płatności
print("2. Tworzę checkout session...")
checkout_response = requests.post(
    f"{BASE_URL}/payment/create-checkout-session",
    headers=headers,
    json={"plan_id": plan_id}
)
checkout_data = checkout_response.json()
session_id = checkout_data["session_id"]
checkout_url = checkout_data["checkout_url"]
print(f"   Session ID: {session_id}")
print(f"   Checkout URL: {checkout_url}")

# 3. Otwórz checkout w przeglądarce
print("3. Otwieram checkout w przeglądarce...")
webbrowser.open(checkout_url)
print("   ✅ Zapłać testową kartą: 4242 4242 4242 4242")
input("   ⏸️  Naciśnij ENTER po zakończeniu płatności...")

# 4. Sprawdź status
print("4. Sprawdzam status płatności...")
for i in range(10):
    status_response = requests.get(
        f"{BASE_URL}/payment/session/{session_id}/status",
        headers=headers
    )
    status_data = status_response.json()
    payment_status = status_data["payment_status"]
    
    print(f"   Próba {i+1}/10: {payment_status}")
    
    if payment_status == "paid":
        print("   ✅ PŁATNOŚĆ ZAKOŃCZONA SUKCESEM!")
        break
    elif payment_status == "unpaid":
        print("   ❌ PŁATNOŚĆ ODRZUCONA")
        break
    
    time.sleep(3)

print("\n✅ Test zakończony!")
```

Uruchom: `python test_payment_manual.py`

---

## 🚨 Najczęstsze problemy

### Problem 1: "Invalid token" (401)
**Rozwiązanie:**
- Sprawdź czy token nie wygasł
- Zaloguj się ponownie w Supabase i wygeneruj nowy token
- Sprawdź czy token ma poprawny format: `eyJ...`

### Problem 2: Webhook nie działa (nie zmienia statusu na "paid")
**Rozwiązanie:**
- Sprawdź w Stripe Dashboard → Webhooks → Recent events
- Szukaj błędu 401/500 w response
- Sprawdź czy webhook URL jest poprawny: `https://travel-planner-backend-xbsp.onrender.com/payment/stripe/webhook`

### Problem 3: Status zawsze "pending" mimo zapłacenia
**Rozwiązanie:**
- Sprawdź webhook events w Stripe
- Poczekaj 10-20 sekund (webhook może mieć opóźnienie)
- Sprawdź tabelę payment_sessions w Supabase - czy status to COMPLETE?

### Problem 4: "Plan not found" przy create-checkout-session
**Rozwiązanie:**
- Upewnij się że użyłeś tego samego JWT tokenu do:
  1. Utworzenia planu (/plan/preview)
  2. Utworzenia sesji płatności (/payment/create-checkout-session)
- Plan musi należeć do tego samego usera

---

## ✅ Checklist weryfikacji

Po udanym teście powinieneś zobaczyć:

### W API:
- [ ] POST /plan/preview → 200 OK, zwrócił plan_id
- [ ] POST /payment/create-checkout-session → 200 OK, zwrócił checkout_url
- [ ] Checkout page opens in browser
- [ ] Payment with 4242... succeeds
- [ ] GET /payment/session/{id}/status → "payment_status": "paid"

### W Stripe Dashboard:
- [ ] Płatność widoczna w Payments → Status: Succeeded
- [ ] Checkout session → Status: Complete
- [ ] Webhook event `checkout.session.completed` → Response: 200 OK

### W Supabase:
- [ ] payment_sessions → status: COMPLETE
- [ ] transactions → status: succeeded

---

## 📞 Potrzebujesz pomocy?

Jeśli coś nie działa:
1. Sprawdź logi w Stripe Dashboard → Webhooks
2. Sprawdź tabelę payment_sessions w Supabase (czy status się zmienia?)
3. Wyślij mi screenshot błędu + session_id

**Testowe dane Stripe:**
- Dashboard: https://dashboard.stripe.com/test
- Testowe karty: https://stripe.com/docs/testing#cards
- Webhook secret: `whsec_cg57zap8crNr6UUNEQvcdwIrmdUKKrNt`

---

**🎉 Gotowe!** Jeśli wszystkie checkingi przeszły - płatności działają poprawnie!
