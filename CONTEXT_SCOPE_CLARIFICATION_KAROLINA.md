# 📝 CONTEXT MEMORY - SCOPE CLARIFICATION Z KAROLINĄ

**Data:** 10.02.2026  
**Status:** Waiting for client decision on options  
**Następny krok:** Karolina wybiera opcję (1-4) lub negocjuje

---

## 🎯 KLUCZOWE USTALENIA

### 1. **Co JEST w ofercie 9k PLN:**
✅ Multi-day planning (2-7 dni) z cross-day POI tracking  
✅ Core POI rotation across days  
✅ Quality scoring + Explainability (why_selected, badges)  
✅ **Versioning:** snapshot + rollback + list versions  
✅ **Editing:** remove_item + replace_item + full reflow  
✅ **Regeneration:** FILL_GAP (już działa Etap 1) + SMART_REPLACE + regenerate_time_range z pinned items  
✅ PostgreSQL migration (Alembic + schemas)  
✅ Stripe integration (real, nie mock)  
✅ PDF generation (async, reportlab)  
✅ Email delivery (outbox pattern + retry)  
✅ Basic auth (register/login, guest→user transfer)  
✅ Admin endpoints (basic)  
✅ Testing + Deployment + Docs  

### 2. **Czego NIE MA w 9k PLN:**
❌ **Reorder (drag & drop)** - zmiana kolejności POI  
❌ **Lunch flexibility** - move/remove przerwy obiadowej  
❌ **Visual diff** - porównanie wersji "co się zmieniło"  

---

## 💰 OPCJE CENOWE DLA KLIENTKI

### **OPCJA 1: MVP** (9k PLN) ← REKOMENDOWANA
- Zakres: jak w oryginalnej ofercie
- Timeline: 7 tygodni
- Bonusy: support + video + docs (~2,5k PLN wartości)

### **OPCJA 2: MVP + Reorder** (10,200 PLN)
- +1,200 PLN za drag & drop editing
- +12-15h pracy
- Timeline: 8 tygodni

### **OPCJA 3: Full Editing** (10,800 PLN)
- +1,800 PLN za reorder + lunch flexibility
- +18-22h pracy
- Timeline: 8-9 tygodni

### **OPCJA 4: MVP + Diff** (9,600 PLN)
- +600 PLN za backend diff (JSON)
- +8-10h pracy
- Timeline: 7 tygodni
- ⚠️ Wizualizacja diff = frontend work

---

## 🔍 PYTANIA KAROLINY - DIAGNOZA

### **Q1: "Czy reorder + lunch w cenie?"**
- **Odpowiedź:** NIE - to było niejednoznaczne w specyfikacji
- **Rozwiązanie:** Opcja 2 (+1,2k) lub Opcja 3 (+1,8k)
- **Rekomendacja:** MVP najpierw, reorder w Phase 3 (post-launch)

### **Q2: "Czy FILL_GAP / SMART_REPLACE / regeneracja z pinned?"**
- **Odpowiedź:** TAK - wszystko w cenie 9k
- **FILL_GAP:** już działa (Etap 1 - gap filling logic w engine.py)
- **SMART_REPLACE:** dodam (kategoria + vibes + avoid_cooldown)
- **Regenerate range:** dodam (endpoint + pinned logic)

### **Q3: "Czy diff + rollback, czy tylko snapshots?"**
- **Odpowiedź:** Rollback TAK, visual diff NIE
- **W ofercie:** snapshot history + rollback to old version
- **Nie ma:** comparison logic "co się zmieniło między v2 a v4"
- **Rozwiązanie:** Opcja 4 (+600 PLN) dla backend JSON diff

### **Q4: "Timeline: 7 tyg czy 3 tyg?"**
- **Odpowiedź:** 7 tygodni (mid-Feb → early April)
- **Confusion:** "3-4 msc" było w porównaniu z software house, nie nasza oferta
- **Realny:** 7 tyg @ 20h/tydzień
- **Fast-track:** 5 tyg @ 30h/tydzień (+2k PLN) = 11k total

---

## 🚨 IMPORTANT CLARIFICATIONS

### **Gap Filling już istnieje (Etap 1):**
- Plik: `app/domain/planner/engine.py` linie 1154, 1194, 1246-1247
- Funkcjonalność: automatyczne wypełnianie luk >40 min soft attractions
- Status: ✅ Działa, testowane

### **Editing MVP - co to znaczy:**
- **Remove:** usuń POI → gap fill → reflow
- **Replace:** zamień POI na podobny (strategy: SMART_REPLACE / RANDOM / MANUAL)
- **Reflow:** przelicz czasy po każdej zmianie
- **NIE MA:** drag & drop UI (to wymaga frontend + złożona logika)

### **Versioning MVP - co to znaczy:**
- **Snapshot:** każda zmiana = nowy rekord w `plan_versions` table
- **List:** `GET /plans/{id}/versions` → array of versions
- **Get:** `GET /plans/{id}/versions/{num}` → full snapshot
- **Rollback:** `POST /plans/{id}/rollback` → copy old version as new
- **NIE MA:** diff view ("wersja 2 dodała Gubałówkę, usunęła Morskie Oko, +20 min")

### **Timeline confusion:**
- **Dokument miał 2 timeline references:**
  1. "7 tygodni (mid-Feb → early April)" ← **NASZ TARGET**
  2. "Software house = 3-4 msc" ← reference konkurencji
- **Fix:** W odpowiedzi jasno: **7 tygodni = 49 dni roboczych @ 20h/tydzień**

---

## 📋 NASTĘPNE KROKI

### **Czekam na:**
1. Karolina wybiera opcję (1/2/3/4) lub proponuje hybrydy
2. Karolina odpowiada na pytania:
   - Timeline 7 tyg OK? Czy potrzeba fast-track (5 tyg)?
   - Co jest must-have, a co nice-to-have?
   - Chce live call (30 min doprecyzowanie)?

### **Po decyzji:**
1. Update umowy (zakres + cena + timeline)
2. Faktura #1 (50% = 4,500 PLN lub więcej jeśli wybrała opcję 2/3/4)
3. Kickoff call (30-45 min)
4. **START ETAP 2**

---

## 🧠 LESSONS LEARNED

### **Co poszło nie tak w oryginalnej ofercie:**
1. **Editing scope był niejasny** - "remove + replace" vs "reorder + lunch"
   - **Fix:** Teraz 4 opcje z jasnym pricing
2. **Versioning miał diff w code examples** ale "Phase 3" w timeline
   - **Fix:** Wyjaśnione: snapshot TAK, visual diff NIE (chyba że opcja 4)
3. **Timeline miał 2 wartości** (7 tyg vs 3-4 msc)
   - **Fix:** Jasno: 7 tyg = nasz target, 3-4 msc = konkurencja reference
4. **Regeneration nie była explicit** - FILL_GAP był w Etapie 1, nie wymieniony w 2
   - **Fix:** Potwierdzam: FILL_GAP działa, SMART_REPLACE dodam, regenerate_range dodam

### **Co działało dobrze:**
- Natural tone ✅
- Bonusy jako incentive ✅
- 50/50 payment protection ✅
- Market comparison ✅
- Fixed price clarity ✅

### **Improvement for future:**
- **Feature checklist** na początku dokumentu (✅/❌/Phase 3)
- **Explicit MVP definition** - "MVP = co dostaniesz w cenie X"
- **Roadmap table** - Phase 2 (now) vs Phase 3 (post-launch)

---

## 🔗 DOCUMENTATION LINKS

- **Oryginalna oferta:** `ETAP2_OFERTA_DLA_KLIENTKI.md`
- **Email version:** `EMAIL_DLA_KAROLINY_ETAP2.md`
- **Technical breakdown:** `ETAP2_TECHNICAL_SUMMARY.md`
- **Executive summary:** `ETAP2_OFERTA_FINALNA.md`
- **Odpowiedź na pytania:** `ODPOWIEDZ_DLA_KAROLINY_SCOPE_CLARIFICATION.md`

---

## ⏳ STATUS: WAITING FOR CLIENT DECISION

**Last update:** 10.02.2026  
**Waiting on:** Karolina's choice of option (1/2/3/4)  
**Next action:** Update contract + invoice based on her decision
