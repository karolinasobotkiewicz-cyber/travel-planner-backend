# ODPOWIEDŹ DLA KAROLINY - CLARIFICATION ZAKRESU

**Data:** 10.02.2026  
**RE:** Pytania do zakresu Etapu 2

---

Cześć Karolino!

Super, że przeanalizowałaś dokument tak dokładnie! 🙂 Odpowiadam punkt po punkcie:

---

## 1. ✏️ EDYCJA PLANU (Reorder + Lunch)

### Co jest w ofercie (9k PLN):
✅ **Remove POI** - usunięcie atrakcji z dnia  
✅ **Replace POI** - zamiana atrakcji (z gap fill / smart replace)  
✅ **Full reflow** - przeliczenie czasów po każdej zmianie  

### Czego NIE MA w ofercie:
❌ **Reorder (drag & drop)** - zmiana kolejności atrakcji  
❌ **Move/remove lunch** - elastyczna edycja przerwy lunchowej  

### 💡 Dlaczego?
Reorder jest **technicznie najciekawszy**, ale też **najmniej krytyczny** dla MVP:
- Remove + Replace rozwiązuje 90% case'ów ("nie chcę tego POI", "wolę coś innego")
- Reorder wymaga **frontend integrations** (drag & drop UI) + skomplikowana logika time-reflow
- Lunch jako fixed slot (12-14h) ma sens dla większości userów

### 🎯 Twoja opcja:
Mam 3 propozycje:

**A) MVP jak w ofercie** (9k PLN)
- Remove + Replace + Reflow
- **Reorder odkładamy na Phase 3** (post-launch ≈ 800-1000 PLN / 12-15h)
- **Lunch fixed** (12-14h, można remove/replace całość)

**B) Dodajemy Reorder** (+1,200 PLN)
- Pełna funkcjonalność drag & drop
- Time-reflow z pinned items
- **Total: 10,200 PLN**

**C) Full Editing (Reorder + Lunch flexibility)** (+1,800 PLN)
- Reorder z zachowaniem constraints
- Move lunch (shift window 11-15h)
- Remove lunch (zamiast tego soft attraction)
- **Total: 10,800 PLN**

**Moja rekomendacja:**  
Opcja **A (9k PLN)** → shipped fast, testujemy z użytkownikami → Phase 3 z reorder, jeśli okaże się must-have.

---

## 2. 🔄 REGENERACJA FRAGMENTÓW (FILL_GAP / SMART_REPLACE)

### Co MAMy już w Etapie 1:
✅ **Gap filling** - silnik automatycznie wypełnia luki między POI  
✅ **Soft attractions** - wstawia filery (muzea, kawiarnie) gdy są dziury >40 min

### Co DODAJĘ w Etapie 2:
✅ **SMART_REPLACE** - przy `replace_item()` silnik:
  - Szuka podobnego POI (same category, similar vibes)
  - Zachowuje time budget ±15 min
  - Respect avoid_cooldown (nie wstawi właśnie usuniętego)

✅ **Regenerate time range** - endpoint:
```python
POST /plans/{plan_id}/days/{day}/regenerate
{
  "from_time": "14:00",
  "to_time": "17:00",
  "pinned_items": ["item_123"]  # Te zostają nienaruszone
}
```
- Silnik **replanuje tylko fragment dnia**
- Pinned items = "chcę te POI na pewno"
- Reszta jest regenerowana

### ✅ Odpowiedź:
**TAK, wszystkie 3 funkcje są w cenie 9k PLN:**
- **FILL_GAP** - już działa (Etap 1)
- **SMART_REPLACE** - dodam w Etapie 2 (logika kategorii + vibes)
- **Regenerate range** - dodam w Etapie 2 (endpoint + pinned logic)

---

## 3. 📦 WERSJONOWANIE (Diff + Rollback)

### Co jest w ofercie (9k PLN):
✅ **Snapshot history** - każda zmiana = nowa wersja w bazie  
✅ **List versions** - `GET /plans/{id}/versions` (timestamps + change_type)  
✅ **Get version** - `GET /plans/{id}/versions/{num}` (pełny snapshot)  
✅ **Rollback** - `POST /plans/{id}/rollback` (restore old version as new)  

### Czego NIE MA w ofercie:
❌ **Visual diff** - kolorowy widok "co się zmieniło" (added/removed/modified POI)  
❌ **Smart diff** - "Day 2: changed 3 attractions, +45 min total time"  

### 💡 Dlaczego?
Masz **podstawową historię** (snapshot + rollback), co wystarcza do:
- "Cofnij mnie do wersji #3"
- "Pokaż mi wszystkie wersje, które generowałem"

**Ale** nie masz diff UI ("Wersja 2 vs 4"):
- To wymaga **complex comparison logic** (match POI by ID, detect time shifts, show inserts/deletes)
- **Bardziej frontend problem** niż backend (backend da JSONy, front musi pokazać)

### 🎯 Twoja opcja:

**A) MVP jak w ofercie** (9k PLN)
- Snapshot + rollback działa
- Diff odkładamy na Phase 3

**B) Dodajemy backend dla diff** (+600 PLN)
```python
GET /plans/{id}/versions/{v1}/diff/{v2}
{
  "added_pois": [...],
  "removed_pois": [...],
  "time_changes": [...]
}
```
- **Total: 9,600 PLN**
- **Uwaga:** to tylko JSON, front musi zrobić wizualizację

**Moja rekomendacja:**  
Opcja **A (9k PLN)** → użytkownicy rzadko porównują wersje, częściej robią "cofnij ostatnią zmianę" (rollback). Diff może poczekać.

---

## 4. ⏱️ TIMELINE - WyJAŚNIENIE

### Skąd confusion?
W dokumencie mam **dwa timelines**:
1. **Etap 2:** **7 tygodni** (mid-Feb → early April) ← **TO JEST NASZ TARGET**
2. **Porównanie z konkurencją:** "Software house = 3-4 msc" ← to reference, nie nasza oferta

### ✅ Realny timeline:
**7 tygodni (49 dni roboczych):**

| Tydzień | Zadania | Deliverable |
|---------|---------|-------------|
| **1-2** | Multi-day + PostgreSQL migration | Multi-day planning działa |
| **3** | Stripe + Entitlements | Payment flow gotowy |
| **4** | PDF + Email | Async generation |
| **5** | Editing MVP + Versioning | Remove/Replace + Rollback |
| **6** | Testing + QA + Bugfixes | Stabilny build |
| **7** | Deployment + Docs + Handoff | **LIVE na producji** |

**Założenia:**
- Pracuję **20h/tydzień** (part-time, bo masz ograniczony budżet)
- Jeśli chcesz **szybciej** → mogę dać 30h/tydz → **5 tygodni** (+2k PLN bo więcej godzin/tydz)

### 🎯 Twoja opcja:

**A) 7 tygodni @ 20h/tydz** (9k PLN)
- **Standard delivery:** early April 2026

**B) 5 tygodni @ 30h/tydz** (11k PLN)
- **Fast-track:** mid-March 2026
- Więcej godzin tygodniowo

**Moja rekomendacja:**  
Opcja **A (7 tygodni)** → realistic, no rush, quality > speed.

---

## 📊 PODSUMOWANIE OPCJI

### 🎯 **OPCJA 1: MVP zgodnie z ofertą** ← REKOMENDOWANA
**Cena:** 9,000 PLN  
**Timeline:** 7 tygodni  
**Zakres:**
- ✅ Multi-day planning (2-7 dni)
- ✅ Quality + Explainability
- ✅ Versioning (snapshot + rollback)
- ✅ Editing (remove + replace + reflow)
- ✅ FILL_GAP / SMART_REPLACE / Regenerate range
- ✅ Stripe + PDF + Email
- ✅ PostgreSQL + Auth
- ❌ Reorder (Phase 3)
- ❌ Visual diff (Phase 3)
- ❌ Lunch flexibility (Phase 3)

**Bonusy:**
- 2 tygodnie support post-launch
- Video walkthrough
- Code guidelines

---

### 🚀 **OPCJA 2: MVP + Reorder**
**Cena:** 10,200 PLN  
**Timeline:** 8 tygodni  
**Dodatkowo:**
- ✅ Reorder (drag & drop, time-reflow)
- ✅ Pinned items podczas reorder

---

### 💎 **OPCJA 3: Full Editing**
**Cena:** 10,800 PLN  
**Timeline:** 8-9 tygodni  
**Dodatkowo:**
- ✅ Reorder
- ✅ Move lunch (shift window)
- ✅ Remove lunch (replace z soft attraction)

---

### 🔬 **OPCJA 4: MVP + Diff**
**Cena:** 9,600 PLN  
**Timeline:** 7 tygodni  
**Dodatkowo:**
- ✅ Diff between versions (backend JSON)
- ⚠️ Uwaga: Wizualizacja = frontend work

---

## 🤝 CO DALEJ?

### Moja prośba:
Powiedz mi, która opcja (1-4) Cię najbardziej kręci, a ja:
1. Doprecyzuję szczegóły
2. Updatuję umowę
3. Wyślę fakturę #1 (50%)
4. Zaczynamy! 🚀

### Moje pytania do Ciebie:
1. **Opcja:** 1 (MVP) / 2 (+ Reorder) / 3 (+ Full Editing) / 4 (+ Diff)?
2. **Timeline:** 7 tyg @ 20h/tydzień OK? Czy potrzebujesz szybciej?
3. **Priorytet:** Co jest must-have, a co nice-to-have?
   - Reorder?
   - Diff?
   - Lunch flexibility?

### 📞 Live call?
Mogę dzisiaj/jutro 30 min call, jeśli chcesz live doprecyzować? (łatwiej gadać niż pisać 😄)

---

## ✅ TL;DR

| Pytanie | Odpowiedź |
|---------|-----------|
| **Reorder + lunch w cenie?** | ❌ NIE - MVP ma remove/replace. Reorder = +1,200 PLN (opcja 2) |
| **FILL_GAP / SMART_REPLACE?** | ✅ TAK - wszystko w cenie 9k |
| **Diff + Rollback?** | ⚠️ Rollback TAK, visual diff NIE (+ 600 PLN = opcja 4) |
| **Timeline?** | ✅ 7 tygodni (mid-Feb → early April), nie 3 msc |

---

Czekam na feedback! 🙌

Mateusz  
ngencode.dev@gmail.com
