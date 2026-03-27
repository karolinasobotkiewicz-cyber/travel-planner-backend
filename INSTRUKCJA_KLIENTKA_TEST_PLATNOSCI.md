# 💳 INSTRUKCJA: Jak przetestować płatności (dla Klientki)

## 🎯 Co będziesz testować?

Pełny flow płatności:
1. ✅ Utworzenie planu podróży (Zakopane, 2 dni)
2. ✅ Przekierowanie do Stripe (prawdziwy system płatności)
3. ✅ Płatność kartą testową
4. ✅ Powrót do aplikacji

---

## 📋 KROK PO KROKU (5 minut)

### **KROK 1: Uruchom serwer lokalny**

1. Otwórz folder projektu
2. **Uruchom plik: `START_SERWER_TEST.bat`** (kliknij 2x)
3. Zobaczysz czarne okno z tekstem:
   ```
   Uruchamiam serwer na porcie 3000...
   ```
4. **NIE ZAMYKAJ tego okna!** (musi być otwarte podczas testów)

---

### **KROK 2: Wygeneruj token JWT**

> ⚠️ **Token to "klucz" do backendu** - musisz go wygenerować przed testem

1. W tym samym folderze uruchom: **`WYGENERUJ_TOKEN_24H.py`** (kliknij 2x)
2. Zobaczysz okno z długim tekstem:
   ```
   ============================================================
   TOKEN (skopiuj poniższy tekst):
   ============================================================
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoZ...
   ============================================================
   ```
3. **Zaznacz i skopiuj** cały token (Ctrl+A, Ctrl+C)
4. Token jest ważny **24 godziny** - możesz go używać wielokrotnie

---

### **KROK 3: Otwórz narzędzie testowe**

1. Otwórz przeglądarkę (Chrome/Firefox/Edge)
2. Wejdź na: **http://localhost:3000/test_platnosci.html**
3. Zobaczysz formularz z polem "JWT Token"

---

### **KROK 4: Uruchom test płatności**

1. **Wklej token** (Ctrl+V) w pole "JWT Token"
2. Kliknij **"Rozpocznij Test Płatności"**
3. Poczekaj ~5 sekund - zobaczysz:
   ```
   ✅ Plan utworzony!
   ✅ Sesja płatności: cs_test_...
   Za 3 sekundy zostaniesz przekierowana do Stripe Checkout.
   ```
4. **Automatyczne przekierowanie** do strony Stripe

---

### **KROK 5: Zapłać na Stripe (test mode)**

Na stronie Stripe wpisz:

| Pole | Wartość |
|------|---------|
| **Email** | Twój email (dowolny) |
| **Numer karty** | `4242 4242 4242 4242` |
| **Data ważności** | `12/30` (dowolna przyszła data) |
| **CVC** | `123` (dowolne 3 cyfry) |

Kliknij **"Pay"** (lub "Zapłać")

---

### **KROK 6: Sprawdź wynik**

#### ✅ **W Stripe Dashboard:**

1. Otwórz: https://dashboard.stripe.com/test/payments
2. **WAŻNE:** W prawym górnym rogu **MUSI być "Viewing test data"** ✅
3. Zobaczysz płatność **19,99 PLN** z statusem "Succeeded"

#### ✅ **W Stripe Checkout Sessions:**

1. Otwórz: https://dashboard.stripe.com/test/checkout/sessions
2. Znajdź najnowszą sesję (status: **"complete"**)
3. Kliknij na nią → zobaczysz szczegóły płatności

#### ✅ **W bazie danych (Supabase):**

1. Otwórz: https://supabase.com/dashboard/project/usztzcigcnsyyatguxay/editor/29565
2. Tabela: **payment_sessions**
3. Zobaczysz wpis z:
   - `status = "completed"`
   - `amount = 19.99`
   - `stripe_session_id = cs_test_...`

---

## 🆘 Co zrobić jeśli coś nie działa?

### ❌ **"Token expired" (401 błąd)**
- **Rozwiązanie:** Wygeneruj nowy token (uruchom `WYGENERUJ_TOKEN_24H.py`)
- Token ważny tylko 24h!

### ❌ **"CORS error" / "nie kieruje do Stripe"**
- **Rozwiązanie:** Sprawdź czy `START_SERWER_TEST.bat` jest uruchomiony
- Serwer **MUSI** działać na porcie 3000

### ❌ **"Plan not found" / "błąd 404"**
- **Rozwiązanie:** Backend może być wyłączony
- Sprawdź: https://travel-planner-backend-xbsp.onrender.com/health
- Jeśli błąd → poczekaj 2 minuty (Render budzi się ze snu)

### ❌ **"Nie widzę płatności w Stripe"**
- **Sprawdź:** Czy jesteś w **"Test mode"** (prawy górny róg)
- **Sprawdź:** https://dashboard.stripe.com/test/checkout/sessions
- Jeśli sesja jest "open" (nie "complete") → nie dokończyłaś płatności na Stripe

---

## 📞 Pomoc

Jeśli coś nie działa:
1. Zrób screenshot błędu (F12 → Console)
2. Wyślij do mnie
3. Naprawię w <1 godzinę! 🚀

---

## ✅ Co testujemy?

Ten test sprawdza:
- ✅ Tworzenie planu przez API
- ✅ Integrację z prawdziwym Stripe (test mode)
- ✅ Przekierowanie płatności
- ✅ Zapisywanie sesji płatności w bazie
- ✅ Webhook (automatyczna aktualizacja po płatności)

**To jest TEN SAM flow** który będzie używany w produkcji! 🎉

Tylko różnica:
- **Test mode:** Karta `4242 4242...` 
- **Produkcja:** Prawdziwe karty klientów

---

**Powodzenia!** 🙌

Jeśli wszystko zadziała → ETAP 2 w 100% gotowy! ✅
