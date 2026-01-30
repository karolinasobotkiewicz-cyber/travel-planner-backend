# TRAVEL PLANNER - ETAP 1 ROZSZERZONY - PREFERENCES & TRAVEL STYLE

**Data rozszerzenia:** 28.01.2026  
**Powód:** Feedback klientki - frontend wymaga scoring preferences + travel_style  
**Status:** ⏳ DO WYKONANIA  

================================================================================

## 📊 KONTEKST

**Klientka (28.01.2026):**
> "Chcę jednak, żeby te elementy były częścią silnika 1 dnia. Wynika to z tego, że na froncie użytkownik już teraz wybiera styl podróży i konkretne preferencje, więc z perspektywy UX plan musi na nie reagować."

**Front:** https://travel-craft-planner-61.lovable.app/  
**Problem:** User wybiera `travel_style` + `preferences` ale nie wpływają na plan → wygląda jakby było zepsute

================================================================================

## 🎯 ZAKRES ROZSZERZENIA

### 1. **Pole `travel_style` w TripInput** (5 min)

**Lokalizacja:** `app/domain/models/trip_input.py`

```python
travel_style: Optional[str] = Field(
    default=None,
    description="Styl podróży: cultural, adventure, relax, balanced"
)
```

**Walidacja:**
```python
@field_validator("travel_style")
@classmethod
def validate_travel_style(cls, v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    allowed = ["cultural", "adventure", "relax", "balanced"]
    if v not in allowed:
        raise ValueError(f"Travel style must be one of {allowed}, got: {v}")
    return v
```

**Update:** `trip_mapper.py` - dodać mapowanie `travel_style` do user dict

---

### 2. **Moduł `preferences.py`** (30 min)

**Lokalizacja:** `app/domain/scoring/preferences.py`

```python
"""
Scoring module - preference matching.
Bonus za matching user preferences z POI tags.
"""


def calculate_preference_score(poi: dict, user: dict) -> float:
    """
    Dopasowanie preferencji użytkownika do POI tags.
    
    Args:
        poi: POI dictionary z polem "tags" (list)
        user: User dictionary z polem "preferences" (list)
    
    Returns:
        Score bonus za matching tags
        
    Logic:
        - Za każdy matching tag: +5 punktów
        - Jeśli brak preferences: 0 (neutralne)
        
    Examples:
        user["preferences"] = ["outdoor", "family"]
        poi["tags"] = ["outdoor", "mountain", "hiking"]
        
        Matching: "outdoor" → +5 punktów
        Result: 5.0
    """
    score = 0.0
    
    # Get preferences from user
    user_prefs = set(user.get("preferences", []))
    if not user_prefs:
        return 0.0  # Brak preferencji = neutralne
    
    # Get tags from POI
    poi_tags = set(poi.get("tags", []))
    if not poi_tags:
        return 0.0  # POI bez tagów = neutralne
    
    # Count matching tags
    matches = user_prefs & poi_tags
    score += len(matches) * 5.0
    
    return score
```

**Testy:** `tests/unit/domain/test_preferences.py` (5 testów)
- test_perfect_match (2 matching tags)
- test_partial_match (1 matching tag)
- test_no_match (brak matching)
- test_no_preferences (user bez preferences)
- test_no_tags (POI bez tags)

---

### 3. **Moduł `travel_style.py`** (30 min)

**Lokalizacja:** `app/domain/scoring/travel_style.py`

```python
"""
Scoring module - travel style matching.
Dopasowanie travel_style użytkownika do activity_style POI.
"""


def calculate_travel_style_score(poi: dict, user: dict) -> float:
    """
    Dopasowanie stylu podróży do stylu aktywności POI.
    
    Args:
        poi: POI dictionary z polem "activity_style"
        user: User dictionary z polem "travel_style"
    
    Returns:
        Score bonus za matching styles
        
    Logic:
        - Perfect match: +6 punktów
        - Partial match: +3 punkty
        - Balanced zawsze OK: +3 punkty
        - Mismatch: 0 punktów
        
    Matching rules:
        adventure → active (perfect)
        relax → relax (perfect)
        cultural → balanced/active (partial)
        balanced → any (partial)
        any → balanced (partial)
        
    Examples:
        user["travel_style"] = "adventure"
        poi["activity_style"] = "active"
        Result: 6.0 (perfect match)
        
        user["travel_style"] = "relax"
        poi["activity_style"] = "active"
        Result: 0.0 (mismatch)
    """
    score = 0.0
    
    user_style = user.get("travel_style", "balanced")
    if not user_style:
        user_style = "balanced"
    
    poi_style = poi.get("activity_style", "balanced")
    if not poi_style:
        poi_style = "balanced"
    
    # Perfect matches
    if user_style == "adventure" and poi_style == "active":
        return 6.0
    if user_style == "relax" and poi_style == "relax":
        return 6.0
    if user_style == "cultural" and poi_style == "balanced":
        return 6.0
    
    # Partial matches
    if user_style == "cultural" and poi_style == "active":
        return 3.0
    if user_style == "balanced":
        return 3.0  # Balanced user OK z wszystkim
    if poi_style == "balanced":
        return 3.0  # Balanced POI OK z wszystkim
    
    # Mismatch
    return 0.0
```

**Testy:** `tests/unit/domain/test_travel_style.py` (6 testów)
- test_perfect_match_adventure
- test_perfect_match_relax
- test_perfect_match_cultural
- test_partial_match_cultural_active
- test_balanced_always_ok
- test_mismatch

---

### 4. **Integracja w engine.py** (10 min)

**Lokalizacja:** `app/domain/planner/engine.py` linia ~297

```python
# Import na górze pliku
from app.domain.scoring.preferences import calculate_preference_score
from app.domain.scoring.travel_style import calculate_travel_style_score

# W funkcji score_poi() po linii 297:
def score_poi(p, user, fatigue, used, now, energy_left, context, culture_streak, body_state, finale_done):
    score = 0.0
    
    # ... existing scoring ...
    score += calculate_family_score(p, user)
    score += calculate_budget_score(p, user)
    score += calculate_crowd_score(p, user)
    
    # ===== NOWE SCORING MODULES =====
    score += calculate_preference_score(p, user)
    score += calculate_travel_style_score(p, user)
    # ================================
    
    # ... rest of function ...
```

---

### 5. **Update trip_mapper.py** (5 min)

**Lokalizacja:** `app/application/services/trip_mapper.py` linia ~44

```python
user = {
    "target_group": trip_input.group.type,
    "budget_level": trip_input.budget.level,
    "crowd_tolerance": trip_input.group.crowd_tolerance,
    "preferences": trip_input.preferences or [],
    "travel_style": trip_input.travel_style or "balanced",  # NOWE
}
```

---

### 6. **Testy integracyjne** (30 min)

**Lokalizacja:** `tests/integration/test_preferences_integration.py`

```python
"""
Integration tests - preferences + travel_style wpływają na plan.
"""

def test_preferences_change_plan():
    """Test że zmiana preferences realnie zmienia plan."""
    # Request A: preferences=["outdoor"]
    # Request B: preferences=["museums"]
    # Assert: Plany mają różne POI

def test_travel_style_change_plan():
    """Test że zmiana travel_style realnie zmienia plan."""
    # Request A: travel_style="adventure"
    # Request B: travel_style="relax"
    # Assert: Plany mają różne POI (adventure → active, relax → relax)

def test_preferences_empty_still_works():
    """Test że brak preferences nie psuje planu."""
    # Request: preferences=[]
    # Assert: Plan generowany poprawnie (scoring neutralny)
```

================================================================================

## ⏱️ SZACUNEK CZASOWY

| Task | Czas | Priorytet |
|------|------|-----------|
| 1. Pole travel_style w TripInput | 5 min | HIGH |
| 2. Moduł preferences.py + testy | 30 min | HIGH |
| 3. Moduł travel_style.py + testy | 30 min | HIGH |
| 4. Integracja engine.py | 10 min | HIGH |
| 5. Update trip_mapper.py | 5 min | HIGH |
| 6. Testy integracyjne | 30 min | MEDIUM |
| 7. Manual testing + dokumentacja | 20 min | MEDIUM |
| 8. Deploy + weryfikacja | 20 min | HIGH |

**TOTAL:** ~2.5h robocze = **0.3 dnia roboczego**

---

## 🚀 PLAN WYKONANIA

### Faza 1: Implementacja (1.5h)
**Kolejność:**
1. Dodać pole `travel_style` w TripInput (5 min)
2. Stworzyć `preferences.py` + 5 testów (30 min)
3. Stworzyć `travel_style.py` + 6 testów (30 min)
4. Zintegrować w engine.py (10 min)
5. Update trip_mapper.py (5 min)
6. Testy integracyjne (30 min)

### Faza 2: Weryfikacja (30 min)
1. `pytest tests/` - wszystkie testy GREEN
2. Manual testing - 3 requesty z różnymi preferences/travel_style
3. Sprawdzić że plany się różnią
4. Update dokumentacji (API.md)

### Faza 3: Deploy (30 min)
1. Commit + push to GitHub
2. Deploy na Render.com
3. Test na live URL
4. Email do klientki z przykładami

**Timeline:**
- Start: 28.01.2026 po akceptacji
- Koniec: 29.01.2026 rano (przed deadline 18:00)

---

## 📝 KOMUNIKACJA Z KLIENTKĄ

**Email draft:** (po implementacji)

```
Cześć Karolino,

Zrobione! 🎯

## Co dodałem:

1. **Pole `travel_style`** w TripInput
   - cultural / adventure / relax / balanced
   
2. **Preferences scoring**
   - User preferences (tags) matchują z POI tags
   - +5 punktów za każdy matching tag
   
3. **Travel style scoring**
   - travel_style matchuje z activity_style POI
   - Perfect match: +6 punktów
   - Partial match: +3 punkty

## Test:

**Request A (adventure + outdoor):**
```json
{
  "travel_style": "adventure",
  "preferences": ["outdoor", "hiking"]
}
```

**Request B (relax + museums):**
```json
{
  "travel_style": "relax",
  "preferences": ["museums", "spa"]
}
```

**Result:** Plany mają RÓŻNE POI (weryfikowane ✅)

## Live:

Backend: https://travel-planner-backend-xbsp.onrender.com
Swagger: https://travel-planner-backend-xbsp.onrender.com/docs

Możesz już testować z frontem.

Pozdrawiam,
Mateusz
```

================================================================================

## 💰 BUDŻET

**ETAP 1 umowa:**
- **5 500 PLN** (netto) za silnik 1 dnia
- Zakres: "Logika silnika 1 dnia (engine.py) z scoringiem"

**Rozszerzenie:**
- **2.5h robocze** (~0.3 dnia)
- Koszt: **~300-400 PLN** (jeśli stawka 100-150 PLN/h)

**Czy to się mieści w ETAPIE 1?**

✅ **TAK** - to jest część "scoringu" który był w zakresie  
✅ Bez tego frontend wygląda jakby był zepsuty  
✅ To są MINIMALNE features żeby UX miał sens  
❌ Nie jest to dodatkowo płatne rozszerzenie  

**Uzasadnienie:**
- Klientka słusznie zauważyła że frontend już ma te pola
- Scoring bez preferences/travel_style jest niekompletny
- To nie jest "nowa feature" tylko dopełnienie istniejącego scoring systemu
- 2.5h to margines błędu w 5-dniowym projekcie

**Konkluzja:** Mieści się w zakresie ETAPU 1, brak potrzeby renegocjacji.

================================================================================

## ✅ ACCEPTANCE CRITERIA

**Definition of Done:**

1. ✅ Pole `travel_style` w TripInput z walidacją
2. ✅ Moduł `preferences.py` z testami (5/5 GREEN)
3. ✅ Moduł `travel_style.py` z testami (6/6 GREEN)
4. ✅ Integracja w engine.py (wywołania w score_poi)
5. ✅ trip_mapper.py mapuje nowe pola
6. ✅ Testy integracyjne pokazują że plany się różnią
7. ✅ Wszystkie testy GREEN (poprzednie + nowe)
8. ✅ Deploy na Render.com
9. ✅ Manual testing na live URL
10. ✅ Email do klientki z przykładami

**Klientka akceptuje gdy:**
- Zmiana `preferences` realnie zmienia plan
- Zmiana `travel_style` realnie zmienia plan
- Frontend może używać tych pól bez "zepsutego" UX

================================================================================

## 🚨 RYZYKA

**Ryzyko 1: POI data nie ma odpowiednich tags**
- **Impact:** LOW
- **Mitigation:** preferences scoring daje 0 gdy brak match (neutralne)
- **Backup:** Dodać przykładowe tags do zakopane.xlsx jeśli potrzeba

**Ryzyko 2: activity_style w POI nie wypełnione**
- **Impact:** LOW
- **Mitigation:** Domyślnie "balanced" → zawsze dostaje +3 punkty
- **Backup:** Dodać activity_style do zakopane.xlsx jeśli potrzeba

**Ryzyko 3: Scoring zbyt słabo wpływa (waga za mała)**
- **Impact:** MEDIUM
- **Mitigation:** Zmienić wagę z +5 na +8 jeśli potrzeba
- **Backup:** Klientka testuje i daje feedback

**Ryzyko 4: Deadline 29.01 18:00**
- **Impact:** LOW
- **Mitigation:** 2.5h work + mamy 1.5 dnia zapasu
- **Backup:** Można zrobić dzisiaj wieczorem

================================================================================

## 📊 STATUS

**Current:** 🚀 ZAAKCEPTOWANE - GOTOWE DO IMPLEMENTACJI  
**Akceptacja:** 28.01.2026 21:00 (klientka: "Tak, akceptuję ten zakres jako część ETAPU 1")  
**Next:** 🔨 IMPLEMENTACJA (start po potwierdzeniu użytkownika)  
**Deadline:** 29.01.2026 18:00 (32h zapasu)  

================================================================================

**Created:** 28.01.2026 20:45  
**Akceptacja klientki:** 28.01.2026 21:00  
**Last update:** 28.01.2026 21:00  
