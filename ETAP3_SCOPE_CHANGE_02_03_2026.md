# ETAP 3 - ZMIANA SCOPE + WYCENA

**Data:** 02.03.2026  
**Status:** Nowy scope otrzymany, wycena przygotowana  

---

## 🔄 CO SIĘ STAŁO

### **WAŻNA ZMIANA:**

**Poprzedni ETAP 3 (z rana 02.03):**
- Dodanie konkretnych miast: Kraków, Warszawa, Gdańsk, Wrocław
- Rozszerzenie Zakopane
- Wycena: 6000-9000 PLN
- **STATUS: ANULOWANY** ❌

**Nowy ETAP 3 (po południu 02.03):**
- Infrastruktura pod 25-30 miast (bez dodawania konkretnych miast)
- Preview/Paywall (server-side)
- Quality & Safety checks
- Opcjonalnie: Restauracje + Szlaki górskie
- Wycena: 4200-5600 PLN
- **STATUS: AKTUALNY** ✅

---

## 📧 EMAIL OD KLIENTKI

**Kluczowe info:**
> "Poczekałabym teraz aż skończy front, żeby móc wszystko już przetestować."

> "To ma być etap domykający przed udostępnieniem planera użytkownikom (dalej chcę go rozwijać, ale najpierw muszę wyjść do ludzi i zebrać feedback)."

**Meaning:**
- Frontend kończy się niedługo
- ETAP 3 to MVP przed startem publicznym
- Nie dodajemy jeszcze 25-30 miast (tylko infrastruktura)
- Miasta będą dodawane PÓŹNIEJ (po feedback od userów)

---

## 🎯 NOWY SCOPE - SZCZEGÓŁY

### **1. FULL POI READINESS (25-30 MIAST)**

**Co to znaczy:**
- Endpoint `GET /destinations` - lista wszystkich dostępnych miast
- Pola: city/name, slug, country, region_type, icon_key, lat, lng, active, poi_count, image_key
- Przygotowanie systemu żeby ogarniał wiele miast (nie crashował, nie był wolny)
- Stabilne filtrowanie po mieście/regionie
- Fallbacki - jak jest mało POI to system nie wywala błędu tylko robi sensowny plan

**Czas:** 3-4 dni

---

### **2. PREVIEW / PAYWALL (SERVER-SIDE)**

**Co to znaczy:**
- User widzi tylko **połowę pierwszego dnia** przed płatnością
- Pełny plan dostępny dopiero po zapłaceniu
- Backend generuje cały plan, ale API zwraca tylko preview
- Nowe pola: `access_level` (preview/full), `payment_status`, `entitlements`
- Update `GET /plan/{plan_id}/status`

**Czas:** 2-3 dni

---

### **3. QUALITY & SAFETY**

**Co to znaczy:**
- Quality checks:
  - Zbyt dużo free_time? (dziury w planie)
  - Brak core POI? (Morskie Oko w Zakopanem)
  - Brak otwartych atrakcji? (nie dajemy zamkniętych muzeów)
- Edge cases:
  - Co jak miasto ma 5 POI a user chce 3 dni?
  - Co jak wszystkie POI są premium (ponad budget)?
- Statusy generowania:
  - `pending` - plan się generuje
  - `ready` - gotowe do pobrania
  - `failed` - coś poszło nie tak
  - `payment_required` - wygenerowane, trzeba zapłacić
- Pola: `warnings`, `fail_reason`
- Logging - żeby klientka widziała co się psuje

**Czas:** 4-5 dni

---

### **4. OPCJONALNIE**

**Restauracje:**
- Typ POI "restaurant"
- Kolacje/śniadania (obiad już jest 12-13:30)
- Filtrowanie po kuchni, cenie

**Szlaki górskie:**
- Typ POI "hiking_trail"
- Czas trwania (2-6h)
- Trudność (łatwy/średni/trudny)

**Czas:** +3-4 dni (oba razem)

---

## 💰 WYCENA

### **PAKIET KOMPLETNY - MVP READY: 8000 PLN**

**Zakres:**
- Destinations endpoint + infrastruktura pod 25-30 miast
- Preview/Paywall (server-side)
- Quality & Safety (checks + statusy + warnings + logging)
- Restauracje (śniadania, obiady, kolacje)
- Szlaki górskie (czas, trudność, pogoda)
- **BONUS 1:** Rozszerzenie Zakopane (22 → 40 POI)
- **BONUS 2:** Email notifications (plan ready, payment confirmed, errors)

**Czas:** 15-17 dni roboczych

**Co dostajesz:**
- MVP gotowe do startu publicznego
- Wszystko w jednej cenie (no hidden costs)
- 2 bonusy wliczone (normalnie 1600 PLN extra)
- Pakiet "all-inclusive"

---

**Normalnie osobno:**
- Infrastruktura + Paywall + Quality: 4800 PLN
- Restauracje + Szlaki: 1600 PLN
- Zakopane expansion: 800 PLN
- Email notifications: 800 PLN
- **RAZEM: 8000 PLN**

**Płacisz: 8000 PLN** (uczciwa cena za kompletny pakiet)

---

## 📊 PORÓWNANIE - STARY vs NOWY SCOPE

| Aspekt | Stary ETAP 3 (rano) | Nowy ETAP 3 (aktualny) |
|--------|---------------------|------------------------|
| **Miasta** | Dodać Kraków, Warszawa, Gdańsk, Wrocław | Tylko infrastruktura (miasta później) |
| **POI** | 120-140 nowych POI | Rozszerzenie Zakopane (bonus) |
| **Restauracje** | Nie | Tak (w cenie) |
| **Szlaki** | Nie | Tak (w cenie) |
| **Bonusy** | Brak | Zakopane expansion + Email notifications |
| **Focus** | Content (POI research) | Features (paywall, quality) |
| **Czas** | 12-21 dni | 15-17 dni |
| **Kwota** | 6000-9000 PLN | 8000 PLN (all-inclusive) |
| **Cel** | Rozbudowa bazy POI | MVP gotowe do startu |

---

## ⏰ TIMELINE
 ~15-17 dni roboczych (2.5-3 tygodnie)
**Delivery:**
- Opcja A: ~10-11 dni roboczych
- Opcja B: ~14 dni roboczych

**W międzyczasie:**
- Klientka kończy frontend
- Pełne testy ETAP 2 (multi-day, payment, editing)

---

## 📝 CO NIE JEST WLICZONE

**Dodawanie konkretnych miast:**
- To będzie PÓŹNIEJ (po starcie MVP i zebraniu feedback)
- Wycena: ~800 PLN/miasto (research + implementacja + testy)
- Przykład: 5 miast = ~4000 PLN

**Kiedy dodamy miasta:**
- Po starcie publicznym
- Jak klientka zbierze feedback
- Jak będzie wiadomo które miasta priorytetowe

---

## 📄 DOKUMENTY PRZYGOTOWANE

### **1. EMAIL_KLIENTKA_ETAP3_NOWY_SCOPE_02_03_2026.md**
- Pełna treść emaila od klientki
- Analiza scope
- Checklist co trzeba zrobić

### **2. WYCENA_ETAP3_02_03_2026.md**
- Szczegółowa wycena każdego punktu
- Uzasadnienie czasu (dlaczego 3-4 dni na X)
- Uzasadnienie kwoty (dlaczego tyle)
- 2 opcje: Podstawowa vs Full
- Porady: co wybrać i dlaczego

### **3. ETAP3_SCOPE_CHANGE_02_03_2026.md** (ten dokument)
- Podsumowanie zmian
- Porównanie stary vs nowy scope
- Pełne info dla developerów

---

## 🚀 NASTĘPNE KROKI

### **DLA CIEBIE:**
1. Przeczytaj wycenę: [WYCENA_ETAP3_02_03_2026.md](WYCENA_ETAP3_02_03_2026.md)
2. Wyślij klientce (gotowe do wysłania)
3. Czekaj na decision

**DLA KLIENTKI:**
1. Kończy frontend
2. Dostaje wycenę: 8000 PLN za pakiet kompletny (MVP ready)
3. Decyduje: Akceptacja?
4. Decyduje: Kiedy start?

### **PO AKCEPTACJI:**
1. Klientka akceptuje wycenę
2. Start ETAP 3 (gdy frontend ready)
3. ~10-14 dni development
4. Testing + deployment
5. Start publiczny MVP 🚀

---

## 🔍 KLUCZOWE RÓŻNICE SCOPE

**To co myśleliśmy rano (NIEAKTUALNE):**
> "Dodamy Kraków, Warszawę, Gdańsk, Wrocław z pełną bazą POI"

**To co klientka chce (AKTUALNE):**
> "Przygotuj system pod 25-30 miast (infrastruktura), dodamy konkretne miasta później po feedback"

**Dlaczego zmiana:**
- Klientka chce najpierw wypuścić MVP
- Zbierać feedback od userów
- Potem rozbudowywać (miasta, features) na podstawie tego co ludzie chcą
- To sensowne podejście (lean startup)

---

## 💡 MOJA OPINIA (jako developer)

**Nowy scope jest lepszy:**

1. **Skupiamy się na features + bonusy, nie tylko na infrastrukturze**
   - Preview/Paywall to krytyczne (kasa się kręci)
   - Quality checks to krytyczne (user experience)
   - Restauracje + Szlaki = lepsze UX od razu
   - Zakopane expansion + Emails = duża wartość dodana
   - Miasta możemy dodawać stopniowo później

2. **Pakiet "all-inclusive"**
   - Jedna cena: 8000 PLN
   - Wszystko wliczone (no hidden costs)
   - Wiesz od razu ile wydasz

3. **Szybszy time-to-market**
   - 15-17 dni to rozsądny czas
   - Klientka szybciej wypuści produkt
   - MVP kompletne

4. **Mniejsze ryzyko**
   - Nie robimy researchu 100+ POI na ślepo
   - Najpierw feedback, potem rozbudowa
   - Ale mamy restauracje i szlaki od razu (ludzie pytają)

5. **Dobra wartość**
   - Za 8000 PLN: infrastruktura + restauracje + szlaki + 2 bonusy
   - Normalnie osobno: 8000 PLN
   - Uczciwa cena za kompletny pakiet

**Plus:**
- Zakopane 40 POI = można testować 5 dni
- Email notifications = lepszy UX (user nie musi odświeżać)
- Restauracje = must-have (ludzie pytają gdzie zjeść)
- Szlaki = must-have dla Zakopane

---

## ✅ PODSUMOWANIE

**Status:** Wycena gotowa (8000 PLN, pakiet all-inclusive), czeka na klientkę

**Co masz:**
- Email od klientki (zapisany)
- Wycena (w "ludzkim" stylu, nie AI) - 8000 PLN za wszystko
- Zakres: infrastruktura + restauracje + szlaki + 2 bonusy
- Porównanie scope (stary vs nowy)
- Uzasadnienie ceny (normalnie osobno = 8000 PLN)

**Co dalej:**
1. Wyślij wycenę klientce
2. Czekaj na decision
3. Jak frontend ready + wycena zaakceptowana → Start ETAP 3

---

**Saved:** 02.03.2026  
**Next:** Waiting for client decision
