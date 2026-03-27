# EMAIL KLIENTKA - ETAP 3 NOWY SCOPE

**Data:** 02.03.2026  
**Od:** Karolina (klientka)  
**Temat:** ETAP 3 - przed wypuszczeniem do userow

---

## 📧 TREŚĆ EMAILA

> Poczekałabym teraz aż skończy front, żeby móc wszystko już przetestować.
> W międzyczasie mógłbyś przygotować wstępną wycenę ETAPU 3? To ma być etap domykający przed udostępnieniem planera użytkownikom (dalej chcę go rozwijać, ale najpierw muszę wyjść do ludzi i zebrać feedback).

### **ETAP 3**

#### **1) Full POI readiness (25-30 miast)**
- przygotowanie silnika pod pełną bazę POI (na start 25-30 miast)
- stabilne filtrowanie po mieście/regionie
- wydajność i stabilność generowania (multi-day)
- sensowne fallbacki, gdy jest mało pasujących POI

**Nowy endpoint:**
- `GET /destinations` (lub podobnie)
- Pola minimum: `city/name`, `slug`, `country`, `region_type`, `icon_key`, `lat`, `lng`, `active`
- Opcjonalnie: `poi_count`, `image_key`

#### **2) Preview / Paywall (server-side)**
Cel: Przed zakupem użytkownik widzi tylko połowę 1 dnia, full plan po płatności.

**Wymagania:**
- Backend generuje plan i zapisuje całość
- Server-side zwraca tylko preview, jeśli brak uprawnień
- Po płatności zwraca full

**Nowe pola w API:**
- W `PlanResponse`: `access_level` (preview/full), `payment_status`, `entitlements`
- Doprecyzowanie `GET /plan/{plan_id}/status`

#### **3) Quality & safety**
- Minimal quality checks:
  - Zbyt dużo free_time
  - Brak core POI
  - Brak otwartych atrakcji
- Obsługa edge-case przy małej liczbie POI
- Statusy generowania w status endpoint: `pending/ready/failed/payment_required`
- Pola: `warnings`, `fail_reason`
- Podstawowe logowanie błędów/generacji (dla klientki - żeby widziała co się psuje)

#### **4) Opcjonalnie (zależnie od budżetu)**
- Restauracje
- Szlaki górskie

---

## 🔍 ANALIZA

**Kontekst:**
- To **etap domykający przed startem publicznym**
- Klientka chce wypuścić MVP do użytkowników
- Dalszy rozwój będzie po zebraniu feedback
- Front kończy się niedługo → wtedy pełne testy

**WAŻNE:**
- To **NIE jest** rozszerzenie o miasta (Kraków, Warszawa, etc.)
- To jest **przygotowanie infrastruktury** pod 25-30 miast
- Miasta będą dodawane stopniowo PÓŹNIEJ (po starcie)

**Zmiana scope:**
- Poprzedni ETAP 3: Dodanie konkretnych miast (Kraków, Warszawa, Gdańsk, Wrocław)
- Nowy ETAP 3: Infrastruktura + preview/paywall + quality checks

---

## 📋 CO TRZEBA ZROBIĆ

### **1. Full POI readiness**
- [ ] Endpoint `GET /destinations` (lista wszystkich miast)
- [ ] Filtrowanie po mieście/regionie (if needed)
- [ ] Optymalizacja multi-day dla wielu miast
- [ ] Fallbacki gdy mało POI (graceful degradation)

### **2. Preview/Paywall**
- [ ] Logic: pełny plan generowany, ale API zwraca tylko preview przed płatnością
- [ ] Pola: `access_level`, `payment_status`, `entitlements`
- [ ] Update `GET /plan/{plan_id}/status`

### **3. Quality & safety**
- [ ] Quality checks (free_time, core POI, open hours)
- [ ] Edge cases handling
- [ ] Statusy: pending/ready/failed/payment_required
- [ ] Warnings + fail_reason
- [ ] Logging (dla klientki)

### **4. Opcjonalnie**
- [ ] Restauracje (jako POI type)
- [ ] Szlaki górskie (jako POI type)

---

## ⏳ NEXT STEPS

1. Przygotować wycenę (za chwilę)
2. Czekać na feedback od klientki
3. Po akceptacji: Start ETAP 3
4. W międzyczasie: Klientka kończy frontend + testy

---

**Saved:** 02.03.2026  
**Status:** Nowy scope otrzymany, wycena w przygotowaniu
