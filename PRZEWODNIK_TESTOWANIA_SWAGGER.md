# 🧪 PRZEWODNIK TESTOWANIA PRZEZ SWAGGER UI

## ✅ Serwer uruchomiony!

**URL Swagger:** http://127.0.0.1:8080/docs  
**Status:** 🟢 RUNNING (port 8080)

---

## 📋 KROK PO KROKU - JAK PRZETESTOWAĆ

### 1. Otwórz Swagger UI
- **URL:** http://127.0.0.1:8080/docs
- Powinieneś zobaczyć FastAPI Swagger interface z listą endpointów

### 2. Znajdź endpoint `/plan/preview`
- Rozwiń sekcję **"POST /plan/preview"**
- Kliknij **"Try it out"** (prawy górny róg)

### 3. Wklej przykładowy request
**OPCJA A - Z pliku:**
- Otwórz plik `test_swagger_request.json`
- Skopiuj całą zawartość
- Wklej do pola "Request body"

**OPCJA B - Bezpośrednio:**
```json
{
  "location": {
    "city": "zakopane",
    "country": "Poland"
  },
  "trip_length": {
    "days": 1
  },
  "group": {
    "type": "family_kids",
    "size": 4
  },
  "travel_style": "adventure",
  "preferences": ["outdoor"],
  "daily_time_window": {
    "start": "09:00",
    "end": "19:00"
  },
  "transport_modes": ["car"]
}
```

### 4. Wykonaj request
- Kliknij przycisk **"Execute"**
- Poczekaj na response (~2-5 sekund)

### 5. Sprawdź response
**Co powinieneś zobaczyć:**

✅ **Status Code:** `200 OK`

✅ **Response Body - Struktura:**
```json
{
  "plan": {
    "days": [
      {
        "day_number": 1,
        "date": "2026-01-29",
        "items": [
          {
            "type": "attraction",
            "poi_id": "xxx",
            "name": "Nazwa atrakcji",
            "start_time": "09:00",
            "end_time": "10:30",
            "duration_minutes": 90,
            "pro_tip": "Pro tip jeśli dostępny",  // 🆕 NOWE POLE
            "description": "...",
            // ... inne pola
          },
          // ... więcej atrakcji
        ]
      }
    ]
  },
  "metadata": { ... }
}
```

---

## 🔍 CO SPRAWDZIĆ W RESPONSE

### ✅ Checklist - Wszystkie Enhancements

1. **pro_tip Display**
   - ✅ Sprawdź czy niektóre atrakcje mają pole `"pro_tip": "..."`
   - Przykład: `"pro_tip": "Najlepiej odwiedzić rano przed 10:00"`

2. **Brak 2h gaps**
   - ✅ Sprawdź gaps między atrakcjami
   - Luki powinny być <60 min (oprócz końca dnia)
   - Przykład sprawdzania:
     ```
     Atrakcja 1: 09:00-10:30
     Atrakcja 2: 10:35-12:00  → Gap 5 min ✅
     Atrakcja 3: 12:05-13:30  → Gap 5 min ✅
     ```

3. **Seasonality Filter (Winter)**
   - ✅ Data testu: 2026-01-29 (zima)
   - Sprawdź: NIE POWINNO być letnich atrakcji (aquapark letni, plaża, etc)
   - Powinny być: zimowe atrakcje (stok narciarski, termy, indoor activities)

4. **Indoor/Outdoor Dopasowanie**
   - ✅ Pogoda w teście: `partly_cloudy, 5°C` (chłodno)
   - Sprawdź: Mix indoor/outdoor (nie tylko outdoor mimo preference)
   - Priorytet: Indoor activities w chłodną pogodę

5. **Type Matching (family_kids + adventure)**
   - ✅ Powinny być: Zoo, parki rozrywki, aquaparki
   - ❌ NIE powinno być: Nightcluby, bary, extreme sports (zbyt intensywne)

6. **Time of Day**
   - ✅ Evening activities powinny być późno (17:00+)
   - ✅ Morning activities powinny być wcześnie (09:00-12:00)

7. **Budget Perception**
   - ✅ Sprawdź `ticket_price` w atrakcjach
   - Dla family_kids + adventure: Mix różnych cen
   - Expensive activities (termy, parki) mogą być, ale nie dominują

8. **Crowd Avoidance**
   - ✅ Jeśli atrakcja ma `peak_hours`, nie powinna być w tych godzinach
   - (Ciężko sprawdzić bez POI data, ale engine to robi)

---

## 📊 PRZYKŁADOWY DOBRY RESPONSE

```json
{
  "plan": {
    "days": [
      {
        "day_number": 1,
        "date": "2026-01-29",
        "items": [
          {
            "type": "attraction",
            "name": "DINO PARK",
            "start_time": "09:00",
            "end_time": "11:30",
            "duration_minutes": 150,
            "pro_tip": null,  // ← NOWE POLE (może być null)
            "space": "both",
            "seasonality": ["winter", "summer"]  // ← Winter OK
          },
          {
            "type": "transit",
            "duration_minutes": 5
          },
          {
            "type": "attraction",
            "name": "Termy Bukovina",
            "start_time": "11:35",
            "end_time": "13:35",
            "duration_minutes": 120,
            "pro_tip": "Polecamy część SPA z podgrzewanymi basenami",  // ← NOWE POLE
            "space": "indoor",  // ← Indoor w zimie
            "budget_type": "premium"  // ← Perception 1.3x
          },
          // ... więcej atrakcji
        ]
      }
    ]
  }
}
```

---

## ⚠️ MOŻLIWE PROBLEMY I ROZWIĄZANIA

### Problem 1: Port zajęty
**Error:** `Address already in use`
**Rozwiązanie:** Serwer już działa na http://127.0.0.1:8080

### Problem 2: Brak POI w response
**Error:** `"items": []` (pusta lista)
**Możliwe przyczyny:**
- Brak pliku Excel z POI
- Seasonality filter wykluczył wszystko
**Rozwiązanie:** Sprawdź logi terminala

### Problem 3: 500 Internal Server Error
**Możliwe przyczyny:**
- Bug w nowym kodzie
- Brakujące dane w POI
**Rozwiązanie:** Sprawdź logi terminala (szczegółowy traceback)

---

## 🎯 SZYBKI TEST - 5 KROKÓW

1. ✅ Otwórz: http://127.0.0.1:8080/docs
2. ✅ POST /plan/preview → "Try it out"
3. ✅ Wklej JSON z `test_swagger_request.json`
4. ✅ Kliknij "Execute"
5. ✅ Sprawdź:
   - Status 200 OK
   - 10-12 atrakcji
   - Brak 2h gaps
   - Pole `pro_tip` obecne

---

## 🔄 DODATKOWE TESTY

### Test 2: Seniors + Relax
```json
{
  "location": {"city": "zakopane", "country": "Poland"},
  "trip_length": {"days": 1},
  "group": {"type": "seniors", "size": 2},
  "travel_style": "relax",
  "preferences": ["cultural"],
  "daily_time_window": {"start": "10:00", "end": "18:00"},
  "transport_modes": ["car"]
}
```
**Oczekiwany wynik:**
- Muzea, cultural sites
- SPA, termy
- NIE parki rozrywki (seniors penalty)
- NIE extreme sports

### Test 3: Couples + Romantic
```json
{
  "location": {"city": "zakopane", "country": "Poland"},
  "trip_length": {"days": 1},
  "group": {"type": "couples", "size": 2},
  "travel_style": "balanced",
  "preferences": ["romantic", "relax"],
  "daily_time_window": {"start": "11:00", "end": "20:00"},
  "transport_modes": ["car"]
}
```
**Oczekiwany wynik:**
- Romantic spots (viewpoints, restaurants)
- SPA activities
- Evening activities późno (18:00+)

---

## 📝 JAK ZATRZYMAĆ SERWER

**W terminalu:**
- Naciśnij **CTRL+C**
- Poczekaj na shutdown message

**Lub:**
- Zamknij terminal w VS Code

---

## 🎉 SUCCESS CRITERIA

✅ **Wszystko działa jeśli:**
1. Status 200 OK
2. 10-12 activities wygenerowane
3. Brak 2h gaps (max 60-90 min przy końcu dnia)
4. Pole `pro_tip` obecne w każdej attraction
5. Zimowe atrakcje (nie letnie)
6. Gaps między atrakcjami <20 min
7. Brak crash/500 errors

---

**Serwer:** 🟢 Running on http://127.0.0.1:8080  
**Swagger UI:** http://127.0.0.1:8080/docs  
**Test Request:** `test_swagger_request.json`

**Powodzenia! 🚀**
