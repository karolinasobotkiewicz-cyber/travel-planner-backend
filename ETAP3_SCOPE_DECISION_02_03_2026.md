# 🎯 ETAP 3 - DECYZJA O ZAKRESIE

**Data:** 02.03.2026 (rano)  
**Status:** ❌ **NIEAKTUALNY - ZMIENIONY SCOPE**  
**Context:** Feedback po testach ETAP 2

---

## ⚠️ UWAGA: TEN DOKUMENT JEST NIEAKTUALNY

**Nowy scope ETAP 3:** Zobacz [ETAP3_SCOPE_CHANGE_02_03_2026.md](ETAP3_SCOPE_CHANGE_02_03_2026.md)

**Co się zmieniło:**
- Poprzedni scope (ten dokument): Dodanie konkretnych miast (Kraków, Warszawa, Gdańsk, Wrocław)
- Nowy scope: Infrastruktura + Preview/Paywall + Quality checks (bez dodawania miast)

Ten dokument zachowany dla historii.

---

---

## 🔍 PROBLEM DO ROZWIĄZANIA

**Zgłoszony przez klientkę:**
> "Testy stanęły ze względu na małą ilość POI"

**Szczegóły:**
- Zakopane ma obecnie **22 POI**
- Dla planów 4-5 dniowych to **za mało**
- Algorytm potrzebuje większej bazy dla variety (cross-day uniqueness >70%)

**Diagnoza techniczna:**
```
1-2 dni: 22 POI = ✅ OK
3 dni:   22 POI = ⚠️ Działa, ale mało variety
4-5 dni: 22 POI = ❌ Za mało (problem z uniqueness)
```

**Wymagane minimum dla 5 dni:**
- **35-40 POI** (z czego 15-20 core + 20-25 optional)

---

## ❓ PYTANIE KLIENTKI

**Pytanie 1:** Czy Małopolskę włączać do ETAP 3?

**Kontekst:**
- Małopolska = cały region (Zakopane, Kraków, Nowy Targ, Wieliczka, itd.)
- Pytanie: Czy robić jako jeden duży region, czy osobne miasta?

**Pytanie 2:** Czy odłożyć testy i skupić się na ETAP 3?

**Kontekst:**
- Testy ETAP 2 wykazały brak POI
- Czy naprawiać teraz, czy odłożyć do ETAP 3?

---

## 💡 DECYZJA KLIENTKI

### **✅ STRATEGIA: MIASTA > REGIONY**

**Decyzja:**
> "Myślę że najpierw skupimy się na tym żeby do planera wrzucić **topowe miasta turystyczne i okoliczne atrakcje** a nie całe regiony. Wydaje mi się, że w ten sposób zrobimy to solidniej. Ewentualnie w dalszym rozwoju jak zobaczymy że warto to zrobić to wtedy zrobimy całe regiony."

**Implikacje:**
- ❌ **NIE:** Małopolska jako jeden region
- ✅ **TAK:** Każde miasto jako osobna destinacja
- ✅ **TAK:** Topowe miasta turystyczne (Kraków, Warszawa, Gdańsk, Wrocław)
- ✅ **TAK:** Rozszerzenie Zakopane (22 → 35-40 POI)
- 🔮 **MOŻE PÓŹNIEJ:** Regiony (jeśli będzie demand)

### **✅ TESTY: ODŁOŻONE DO ROZSZERZENIA BAZY**

**Decyzja:**
> "Tak, bo wszystko nam działało z tego co pamiętam tylko był problem z tym, że baza POI była zbyt mała na Zakopane, prawda?"

**Implikacje:**
- ✅ ETAP 2 funkcjonalnie działa
- ⏸️ Testy 4-5 dni odłożone do momentu rozszerzenia bazy POI
- 🚀 Start ETAP 3: Rozszerzenie POI

---

## 🎯 ETAP 3 - WSTĘPNY ZAKRES

### **1. ROZSZERZENIE ZAKOPANE** (Priority: HIGH)

**Current state:** 22 POI  
**Target:** 35-40 POI  
**Dodatkowe POI (+15-18):**

**Categories:**
- Mountain trails (dodatkowe szlaki)
- Thermal pools/spas (dodatkowe termy)
- Museums (muzea lokalne)
- Restaurants (dodatkowe restauracje)
- Winter sports (ośrodki narciarskie)
- Viewpoints (dodatkowe punkty widokowe)
- Cultural venues (miejsca kulturalne)

**Format:** Konsultacja z klientką - które POI dodać

---

### **2. NOWE MIASTA** (Priority: HIGH)

**Lista miast (do dyskusji):**

#### **Kraków** 🏰
- **Typ:** city
- **Target POI:** 30-35
- **Categories:** Museums, Old Town, Kazimierz, Wawel, Restaurants, Bars, Parks
- **Estimate:** ~2-3 dni robocze research + implementation

#### **Warszawa** 🏙️
- **Typ:** city
- **Target POI:** 30-35
- **Categories:** Museums, Old Town, Modern, Restaurants, Parks, Nightlife
- **Estimate:** ~2-3 dni robocze

#### **Gdańsk** 🌊
- **Typ:** sea
- **Target POI:** 30-35
- **Categories:** Old Town, Beaches, Maritime, Restaurants, Sopot, Gdynia
- **Estimate:** ~2-3 dni robocze

#### **Wrocław** 🎭
- **Typ:** city
- **Target POI:** 30-35
- **Categories:** Old Town, Ostrów Tumski, Restaurants, Parks, Culture
- **Estimate:** ~2-3 dni robocze

**Total POI to add:** ~135-155 POI (4 miasta + Zakopane expansion)

---

### **3. MULTI-LANGUAGE** (Priority: MEDIUM - Optional)

**Scope:**
- English (EN) translations
- German (DE) translations

**What to translate:**
- POI names (jeśli potrzebne)
- POI descriptions
- Categories
- UI labels (if backend provides)
- Error messages

**Estimate:** ~2-3 dni per language

---

### **4. AI/ML PERSONALIZATION** (Priority: LOW - Optional)

**Scope:**
- Machine learning recommendations
- User preference learning
- Advanced analytics (Google Analytics, Mixpanel)

**Estimate:** ~3-5 dni

---

## 📊 ETAP 3 - WYCENA WSTĘPNA

### **Opcja 1: MINIMUM (Cities Only)**
**Scope:**
- Rozszerzenie Zakopane (22 → 40 POI)
- 4 nowe miasta (Kraków, Warszawa, Gdańsk, Wrocław)
- Każde miasto: 30 POI
- Total: 138 POI to add/create

**Estimate:**
- Research per miasto: 1-1.5 dni
- Implementation per miasto: 1.5-2 dni
- Testing: 1-2 dni
- **Total:** 12-15 dni roboczych

**Budget:** **6000-7000 PLN**

---

### **Opcja 2: CITIES + MULTI-LANGUAGE**
**Scope:**
- Opcja 1 (Cities)
- English translations
- German translations

**Estimate:**
- Opcja 1: 12-15 dni
- Translations: +4-6 dni
- **Total:** 16-21 dni roboczych

**Budget:** **8000-9000 PLN**

---

### **Opcja 3: FULL (Cities + Lang + AI)**
**Scope:**
- Opcja 2 (Cities + Languages)
- AI/ML personalization
- Advanced analytics

**Estimate:**
- Opcja 2: 16-21 dni
- AI/ML: +3-5 dni
- **Total:** 20-26 dni roboczych

**Budget:** **10000-12000 PLN**

---

## 🤔 PYTANIE TECHNICZNE OD KLIENTKI

**Pytanie:**
> "Jeśli się mylę i Twoim zdaniem z punktu widzenia technicznego powinniśmy najpierw całą Małopolskę opracować to daj proszę znać."

**Odpowiedź:** Zobacz dokument **ODPOWIEDZ_KLIENTKA_MALOPOLSKA_MIASTA.md**

**TL;DR:** Z technicznego punktu widzenia **NIE trzeba** opracowywać całej Małopolski. Miasta > Regiony! ✅

---

## 📋 NASTĘPNE KROKI - PLANOWANIE

### **IMMEDIATE:**
1. ✅ Decyzja strategiczna: Miasta > Regiony
2. ⏳ **Do ustalenia z klientką:**
   - Które miasta priorytetowe? (Kraków, Warszawa, Gdańsk, Wrocław - wszystkie czy wybrane?)
   - Zakres: Cities only vs Cities + Languages vs Full?
   - Budget: 6000-9000 PLN?
   - Źródła POI: Klientka dostarcza listę czy backend dev researcha?
   - Timeline: Start kiedy? (zaraz po ETAP 2 transfer czy później?)

### **BEFORE START:**
1. Transfer projektu ETAP 2 (Render + Supabase)
2. Precyzyjny zakres ETAP 3
3. Finalna wycena
4. Podpisanie umowy / potwierdzenie zakresu

---

## 📄 DOKUMENTY POWIĄZANE

- **ETAP2_PAYMENT_CONFIRMED_02_03_2026.md** - Potwierdzenie zakończenia ETAP 2
- **ODPOWIEDZ_KLIENTKA_MALOPOLSKA_MIASTA.md** - Odpowiedź techniczna na pytanie
- **ETAP2_FINAL_STATUS_02_03_2026.md** - Status ETAP 2

---

**Status:** 📋 SCOPE DEFINED - WAITING FOR CLIENT CONFIRMATION  
**Next:** Finalna wycena + timeline po ustaleniach z klientką  
**Created:** 02.03.2026
