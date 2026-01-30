# Odpowiedź dla Karoliny - 422 Error w Swaggerze

Cześć Karolino,

Właśnie przetestowałem dokładnie ten sam JSON który wysłałaś - **backend działa**, plan się wygenerował (15 items, Plan ID: ad4eda90-ccd4-410d-a845-7a00e0de0fd3).

Problem jest w Swaggerze - pewnie wypełniłaś pole `budget.level` jako tekst `"medium"` zamiast liczby `2`.

## Jak wypełnić poprawnie w Swagger UI:

1. Idź na: https://travel-planner-backend-xbsp.onrender.com/docs
2. Znajdź **POST /plan/preview**
3. Kliknij **"Try it out"**
4. **USUŃ cały example JSON** który tam jest
5. **Skopiuj i wklej** dokładnie to (CTRL+A, CTRL+V):

```json
{
  "location": {
    "city": "Zakopane",
    "country": "Poland",
    "region_type": "mountain"
  },
  "group": {
    "type": "family_kids",
    "size": 4,
    "crowd_tolerance": 2
  },
  "trip_length": {
    "days": 1,
    "start_date": "2026-02-15"
  },
  "daily_time_window": {
    "start": "09:00",
    "end": "18:00"
  },
  "budget": {
    "level": 2
  },
  "transport_modes": ["car", "walk"]
}
```

6. Kliknij **"Execute"**
7. Czekaj ~2-3s (może dłużej jeśli cold start)

Powinno być **200 OK** i pełny plan z 15 items.

## Najczęstsze błędy w Swaggerze:

❌ **ŹLE:**
```json
"budget": {
  "level": "medium"  ← TO JEST STRING, SWAGGER WYRZUCI 422!
}
```

✅ **DOBRZE:**
```json
"budget": {
  "level": 2  ← TO JEST LICZBA (1, 2 lub 3)
}
```

## Validacja budget.level:
- Musi być **liczba całkowita** (integer)
- Dozwolone wartości: **1** (low), **2** (medium), **3** (high)
- **NIE może być** string: "low", "medium", "high"

## Co zobaczyć w Response (200 OK):

```json
{
  "plan_id": "jakiś-uuid-tutaj",
  "version": 1,
  "days": [
    {
      "day": 1,
      "items": [
        {"type": "day_start", "start_time": "09:00", ...},
        {"type": "parking", "duration_min": 15, ...},
        {"type": "attraction", "poi_id": "poi_0", "name": "Muzeum Oscypka Zakopane", ...},
        ... 12 more items ...
        {"type": "day_end", "end_time": "18:00", ...}
      ]
    }
  ]
}
```

Łącznie 15 items w planie.

## Jeśli dalej 422:

Wyślij mi screenshot **całego Request body** (co dokładnie wkleiłaś w Swaggerze) + **cały błąd validation** (co jest w Response). Wtedy zobaczę co jest nie tak.

Backend na 100% działa - właśnie wygenerował plan z Twojego JSONa.

Pozdrawiam,  
Mateusz

---

**Test wykonany:** 28.01.2026 11:30  
**Status:** Backend OK, plan wygenerowany (15 items)  
**Plan ID:** ad4eda90-ccd4-410d-a845-7a00e0de0fd3
