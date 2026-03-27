# ✅ CHECKLIST: Test Płatności (5 minut)

## Przed testem:

- [ ] Mam folder `travel-planner-backend` otwarty
- [ ] Mam przeglądarkę (Chrome/Firefox/Edge) gotową
- [ ] Mam dostęp do Stripe Dashboard (https://dashboard.stripe.com)

---

## KROK 1: Start serwera

- [ ] Znalazłam plik: `START_SERWER_TEST.bat`
- [ ] Kliknęłam 2x na ten plik
- [ ] Widzę czarne okno z tekstem "Uruchamiam serwer..."
- [ ] **NIE ZAMYKAM** tego okna!

**✅ Serwer działa!**

---

## KROK 2: Token JWT

- [ ] Otworzyłam email: "ETAP 2 - Gotowe do testowania płatności"
- [ ] Znalazłam sekcję: "TWÓJ TOKEN JWT"
- [ ] Skopiowałam cały długi token (Ctrl+A, Ctrl+C)

**Token w schowku!** 📋

**ALTERNATYWNIE:** Jeśli token wygasł:
- [ ] Uruchom `WYGENERUJ_TOKEN_24H.py` (kliknij 2x)
- [ ] Skopiuj nowy token z czarnego okna

---

## KROK 3: Otwórz narzędzie testowe

- [ ] Otworzyłam przeglądarkę
- [ ] Weszłam na: http://localhost:3000/test_platnosci.html
- [ ] Widzę formularz z polem "JWT Token"

**Strona załadowana!** 🌐

---

## KROK 4: Uruchom test

- [ ] Wkleiłam token w pole "JWT Token" (Ctrl+V)
- [ ] Kliknęłam przycisk: **"Rozpocznij Test Płatności"**
- [ ] Widzę komunikat: "Step 1: Creating plan..."
- [ ] Widzę komunikat: "Step 2: Creating checkout session..."
- [ ] Widzę zielony komunikat: "✅ Plan utworzony!"
- [ ] Poczekałam 3 sekundy
- [ ] **Zostałam przekierowana do Stripe Checkout**

**Przekierowanie działa!** 🎉

---

## KROK 5: Płatność na Stripe

Na stronie Stripe wypełniłam:

- [ ] **Email:** Wpisałam dowolny email (np. test@test.pl)
- [ ] **Karta:** `4242 4242 4242 4242`
- [ ] **Data ważności:** `12/30`
- [ ] **CVC:** `123`
- [ ] Kliknęłam: **"Pay"** (lub "Zapłać")
- [ ] Widziałam komunikat o sukcesie
- [ ] Wróciłam do aplikacji (przekierowanie automatyczne)

**Płatność przeszła!** 💳 ✅

---

## KROK 6: Weryfikacja w Stripe Dashboard

### 6A: Sprawdź Payments

- [ ] Otworzyłam: https://dashboard.stripe.com/test/payments
- [ ] **Sprawdziłam:** Prawy górny róg = **"Viewing test data"** ✅
  - Jeśli jest "Viewing live data" → kliknij i zmień!
- [ ] Widzę płatność **19.99 PLN** / **PLN 19.99**
- [ ] Status: **"Succeeded"** (zielony)
- [ ] Czas: Dzisiejsza data, ostatnie minuty

**Płatność widoczna w Stripe!** ✅

### 6B: Sprawdź Checkout Sessions

- [ ] Otworzyłam: https://dashboard.stripe.com/test/checkout/sessions
- [ ] Widzę najnowszą sesję (pierwsza na liście)
- [ ] Status: **"complete"** (niebieski)
- [ ] Amount: **PLN 19.99**
- [ ] Kliknęłam na sesję → widzę szczegóły

**Sesja kompletna!** ✅

---

## KROK 7: Weryfikacja w bazie danych (Supabase)

- [ ] Otworzyłam: https://supabase.com/dashboard/project/usztzcigcnsyyatguxay/editor/29565
- [ ] Tabela: **payment_sessions**
- [ ] Widzę nowy wpis z:
  - `status` = **"completed"**
  - `amount` = **19.99**
  - `stripe_session_id` = **cs_test_...**
  - `created_at` = dzisiejsza data
- [ ] Kliknęłam na wiersz → widzę pełne dane

**Baza danych zaktualizowana!** ✅

---

## ✅ SUKCES! Pełny flow działa!

Jeśli zaznaczyłaś wszystkie checkboxy:
- ✅ Backend API działa
- ✅ Stripe integracja działa
- ✅ Webhook aktualizuje bazę
- ✅ ETAP 2 w 100% gotowy! 🎉

---

## ❌ Co zrobić jeśli coś nie działa?

### Problem: "Token expired" (błąd 401)
**Rozwiązanie:**
1. Uruchom: `WYGENERUJ_TOKEN_24H.py`
2. Skopiuj nowy token
3. Odśwież stronę (F5)
4. Wklej nowy token

### Problem: "CORS error" / "nie kieruje do Stripe"
**Rozwiązanie:**
1. Sprawdź czy `START_SERWER_TEST.bat` jest uruchomiony
2. Jeśli nie → uruchom ponownie
3. Odśwież stronę (F5)

### Problem: "Nie widzę płatności w Stripe"
**Rozwiązanie:**
1. Sprawdź czy jesteś w **"Test mode"** (prawy górny róg)
2. Sprawdź: https://dashboard.stripe.com/test/checkout/sessions
3. Jeśli sesja jest "open" (nie "complete"):
   - Nie dokończyłaś płatności na stronie Stripe
   - Uruchom test ponownie od KROKU 4

### Problem: "Backend error 500"
**Rozwiązanie:**
1. Backend może być "śpiący" (Render free tier)
2. Sprawdź: https://travel-planner-backend-xbsp.onrender.com/health
3. Poczekaj 2 minuty aż się obudzi
4. Spróbuj ponownie

---

## 📞 Pomoc

Jeśli dalej nie działa:
1. Zrób screenshot błędu
2. Naciśnij F12 → Console → skopiuj błędy
3. Wyślij do mnie
4. Naprawię w <1 godzinę! 🚀

---

**Powodzenia!** 🙌

Po udanym teście → możesz dokonać płatności za ETAP 2! 💰
