# BUGFIX: free_entry Detection Logic (16.02.2026)

## Problem

Dom do góry nogami zwracał `cost_estimate: 0` mimo że ma bilety:
- ticket_normal: 21 PLN
- ticket_reduced: 17 PLN

Klientka zgłosiła jako **CRITICAL BUG** w CLIENT FEEDBACK.

---

## Root Cause

Stara logika w `normalizer.py` (line 461):
```python
# BŁĘDNA LOGIKA:
price_text = _safe_lower(p.get("Price"))
free_entry = "bezpłatny" in price_text or "free" in price_text
```

**Problem:**
- Kolumna `Price` zawierała tekst: `"bilet normalny: 21 zł, bilet ulgowy: 17 zł, dzieci do lat 3: wstęp bezpłatny"`
- System wykrywał słowo **"bezpłatny"** → ustawiał `free_entry=True`
- Ignorował kolumny `ticket_normal` i `ticket_reduced` (faktyczne ceny)

---

## Solution

**ETAP 1 Decision Reminder:**
> "Bierzemy dane z ticket_normal i ticket_reduced - tam mamy wpisane tylko liczby"

**Poprawna logika (16.02.2026):**
```python
# PRIORYTET 1: Sprawdź kolumny numeryczne (źródło prawdy)
ticket_normal_val = _safe_float(p.get("ticket_normal"), 0)
ticket_reduced_val = _safe_float(p.get("ticket_reduced"), 0)

if ticket_normal_val > 0 or ticket_reduced_val > 0:
    # Ma bilety → NIE jest darmowe (ignoruj tekst w Price)
    free_entry = False
else:
    # PRIORYTET 2: Brak numerycznych cen → sprawdź tekst Price jako fallback
    price_text = _safe_lower(p.get("Price"))
    free_entry = "bezpłatny" in price_text or "free" in price_text
```

---

## Impact

**Naprawione:**
- ✅ Dom do góry nogami: `free_entry=False`, `cost_estimate=76 PLN` (4 osoby)
- ✅ Kolumna Price może zawierać "dzieci do lat 3: bezpłatny" (użyteczna info)
- ✅ Nie trzeba czyścić Excela

**Przypadki testowe:**
- Wielka Krokiew (89/49): free_entry=False → cost=276 PLN family ✅
- Podwodny Świat (28/24): free_entry=False → cost=104 PLN family ✅
- Dom do góry nogami (21/17): free_entry=False → cost=76 PLN family ✅
- POI bez cen (0/0) + "bezpłatny" w Price: free_entry=True → cost=0 ✅

---

## Files Changed

1. **normalizer.py** (line 458-470):
   - Changed free_entry detection logic
   - Priority: numeric tickets > Price text

2. **test_cost_integration.py**:
   - Updated Dom do góry nogami test expectations
   - Added comment explaining new logic

3. **plan_service.py** (line 582-640):
   - Already fixed: uses group_size from user dict
   - Works correctly with new free_entry logic

---

## Knowledge for Future

**ALWAYS:**
- Numeric columns (`ticket_normal`, `ticket_reduced`) = **SOURCE OF TRUTH**
- Text columns (`Price`, `Description`) = descriptive only, may contain exceptions

**NEVER:**
- Don't detect free_entry from text if numeric data exists
- Don't assume Price column is clean (może zawierać info o dzieciach, promocjach)

**Client's Rule (ETAP 1):**
> "Bierzemy dane z ticket_normal i ticket_reduced"

---

## Date: 16.02.2026
## Reported by: Karolina (klientka)
## Fixed by: AI Assistant + Karolina's guidance
## Status: ✅ RESOLVED
