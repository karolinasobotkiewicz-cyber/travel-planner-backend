# Odpowiedź dla Karoliny - Working Plan Example

Cześć Karolino!

Tak, mam gotowy przykład - właśnie testowałem dzisiaj wieczorem przez Swagger UI i plan się wygenerował poprawnie z 6 POI.

## ✅ Working Example - Request Body

Wysyłam Ci request body który zadziałał u mnie (przez Swagger UI na https://travel-planner-backend-xbsp.onrender.com/docs):

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

**WAŻNE:**
- `budget.level` to **liczba** (1, 2, lub 3), NIE string "medium"!
- `start_date` w formacie "YYYY-MM-DD"
- `transport_modes` jako array

## ✅ Response który dostałem (200 OK)

Plan ID: `3dbdaf19-283b-4575-90a7-86780d7d570f`

**15 items w planie:**
1. day_start (09:00)
2. **parking** (09:00-09:15) - 15 min dla car mode ✅
3. attraction - Muzeum Oscypka Zakopane (45 min)
4. transit - walk 5 min
5. attraction - Myszogród (30 min)
6. transit - walk 5 min
7. attraction - Tatrzańskie Mini Zoo (30 min)
8. **lunch_break** (13:05-13:45, 40 min) - ZAWSZE obecny ✅
9. transit - walk 5 min
10. attraction - Wystawa Figur Woskowych EXPO Krupówki (30 min)
11. transit - walk 5 min
12. attraction - Dom do góry nogami (20 min)
13. transit - walk 5 min
14. attraction - Iluzja Park (60 min)
15. day_end (18:00)

**6 atrakcji razem**, wszystkie z Zakopane (z Twojego zakopane.xlsx).

## 🔍 Twój Problem - Debugging

Napisałaś że dostałaś tylko day_start i day_end bez POI. To może być:

1. **Request body inny format?**
   - Czy wysyłałaś przez Swagger UI (/docs)?
   - Czy przez curl/Postman?
   - Możesz podesłać dokładny JSON który wysłałaś?

2. **Destination problem?**
   - Backend ma tylko POI dla "Zakopane" (z Twojego Excel)
   - Jeśli `location.city` było inne = pusty plan

3. **POI nie załadowały się?**
   - Backend powinien załadować 32 POI z zakopane.xlsx przy starcie
   - Sprawdzę logi na Render

## 📝 Jak przetestować przez Swagger UI (najprostsze)

1. Wejdź: https://travel-planner-backend-xbsp.onrender.com/docs
2. Znajdź **POST /plan/preview** (zielony button)
3. Kliknij → "Try it out"
4. Wklej JSON z góry (cały blok)
5. Kliknij "Execute"
6. Sprawdź Response Body

Jeśli przez Swagger zadziała = request body OK, backend OK.
Jeśli przez Swagger też pusty = sprawdzę logi.

## 🚨 Jeśli nadal pusty plan

Prześlij mi:
1. Request body który wysyłasz (cały JSON)
2. Response który dostajesz (cały JSON)
3. Przez co testujesz (Swagger UI / curl / Postman)

Sprawdzę logi na Render i zobaczę co się dzieje z POI loading.

---

**P.S.** U mnie zadziałało dzisiaj o 22:30, więc backend w teorii OK. Najprawdopodobniej format request body albo destination mismatch.

Daj znać!

Mateusz
