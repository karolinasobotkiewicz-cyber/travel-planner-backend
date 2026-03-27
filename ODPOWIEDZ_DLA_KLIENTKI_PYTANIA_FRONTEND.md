Temat: RE: Pytania dot. integracji frontend

Cześć Karolino! 🙂

Odpowiadam na pytania:

---

## 1️⃣ **Lista miast i mapowanie ikonek**

### **ENDPOINT: GET /content/home**

✅ **Jest gotowy endpoint** który zwraca listę 8 destynacji:

```
GET https://travel-planner-backend-xbsp.onrender.com/content/home
```

**Nie wymaga autoryzacji** (public endpoint).

### **Response JSON:**

```json
{
  "destinations": [
    {
      "destination_id": "zakopane",
      "name": "Zakopane",
      "country": "Poland",
      "region_type": "mountain",
      "image_key": "destinations/zakopane.jpg",
      "description_short": "Stolica polskich Tatr - idealna na rodzinne wypady"
    },
    {
      "destination_id": "krakow",
      "name": "Kraków",
      "country": "Poland",
      "region_type": "city",
      "image_key": "destinations/krakow.jpg",
      "description_short": "Historyczne miasto z bogatą kulturą"
    },
    {
      "destination_id": "gdansk",
      "name": "Gdańsk",
      "country": "Poland",
      "region_type": "sea",
      "image_key": "destinations/gdansk.jpg",
      "description_short": "Morskie miasto z piękną starówką"
    }
    // ... 5 więcej
  ],
  "featured_count": 8
}
```

---

### **Mapowanie `region_type` → ikonka:**

**Backend zwraca `region_type`** - frontend mapuje na ikonę:

| `region_type` | Ikona (przykład) | Opis |
|---------------|------------------|------|
| `"mountain"` | 🏔️ / ⛰️ | Góry (Zakopane, Tatry) |
| `"sea"` | 🌊 / 🏖️ | Morze (Gdańsk, Sopot) |
| `"city"` | 🏙️ / 🏛️ | Miasto (Kraków, Warszawa) |
| `"countryside"` | 🌾 / 🏡 | Wieś/natura (opcjonalnie) |

**Frontend decyduje o ikonach** - backend tylko klasyfikuje region.

---

### **Tworzenie planu - mapowanie miasta:**

Kiedy użytkownik wybierze "Zakopane" z listy, frontend wysyła:

```json
{
  "location": {
    "city": "Zakopane",        // ← z destinations[].name
    "country": "Poland",        // ← z destinations[].country
    "region_type": "mountain"   // ← z destinations[].region_type
  },
  "group": { "type": "couples", "size": 2 },
  "trip_length": { "days": 2, "start_date": "2026-03-01" }
  // ... reszta
}
```

**✅ Wszystkie dane są w `/content/home` response!**

---

### **⚠️ WAŻNE: Na razie tylko Zakopane ma pełną bazę POI**

Jeśli frontend wyśle plan dla **Kraków/Gdańsk/Wrocław**:
- Backend zwróci **pusty plan** (brak POI w bazie)
- To jest **normalne** - ETAP 2 obejmuje tylko Zakopane

**ETAP 3 (opcjonalny):** Rozszerzenie bazy POI na inne miasta (7000-9000 PLN, 2-3 tygodnie).

---

## 2️⃣ **Testowanie API - plany vs mocki**

### **✅ TAK, możesz tworzyć testowe plany przez API!**

Backend jest na produkcji i **gotowy do testowania**:
- URL: https://travel-planner-backend-xbsp.onrender.com
- Status: ✅ Live (sprawdź: `/health`)

### **Zalety testowania na prawdziwym API:**

1. ✅ **Catch bugs early** - znajdziesz problemy integracyjne od razu
2. ✅ **Prawdziwe dane** - widzisz jak wyglądają response'y (format, długość tekstu, itp.)
3. ✅ **Weryfikacja autoryzacji** - testujesz JWT flow
4. ✅ **Testowanie błędów** - widzisz jakie error messages zwraca backend

### **Jak testować bezpiecznie:**

**Plany nie mają limitu** - każdy plan to nowy UUID, nie ma "czyszczenia" potrzebnego.

Jeśli chcesz czystego środowiska:
- Używaj **różnych JWT tokenów** (różne user_id)
- Backend przypisuje plan do user_id z tokenu
- Każdy dev może mieć swój "test user"

### **Przykład: Generowanie test tokenu**

Mogę wygenerować **test token dla dev frontendu** (ważny 7 dni):

```bash
# Uruchom w folderze projektu:
python WYGENERUJ_TOKEN_24H.py
```

Albo wyślij mi info ile tokenów potrzebujecie - wygeneruję paczkę (np. 5 tokenów po 7 dni).

---

### **Kiedy używać mocków?**

Mocki są OK dla:
- ❌ Backend jeszcze nie działa (ale nasz działa!)
- ❌ Wolne testy (ale nasze API jest szybkie ~1-2s)
- ❌ Offline development (np. w samolocie)

Ale dla normalnego developmentu: **testuj na prawdziwym API!** 🎯

---

## 📊 Podsumowanie odpowiedzi:

### **Pytanie 1: Lista miast**
✅ Endpoint: `GET /content/home`  
✅ Zwraca: `region_type`, `image_key`, `name`, `country`  
✅ Frontend mapuje `region_type` → ikonę

### **Pytanie 2: Testowanie**
✅ Testuj na prawdziwym API (https://travel-planner-backend-xbsp.onrender.com)  
✅ Nie ma limitu planów  
✅ Mogę wygenerować test tokeny dla całego teamu

---

## 🚀 Następne kroki dla dev frontendu:

1. **Pobierz listę miast:**
   ```bash
   curl https://travel-planner-backend-xbsp.onrender.com/content/home
   ```

2. **Wygeneruj test token** (jeśli potrzeba więcej):
   - Napisz ile tokenów potrzebujecie
   - Podam ważność (7 dni? 14 dni?)

3. **Testuj `/plan/preview`:**
   - Użyj struktury z `test_platnosci.html` (masz naprawiony plik)
   - Przykłady w: OpenAPI spec (ETAP2_API_SPECIFICATION.json)

4. **Dokumentacja:**
   - OpenAPI spec: `ETAP2_API_SPECIFICATION.json`
   - Postman collection: `Travel_Planner_ETAP2.postman_collection.json`
   - Sample responses: `ETAP2_SAMPLE_RESPONSES.md`

---

## 💡 Bonusowe narzędzia dla dev frontendu:

### **1. Swagger UI (interactive docs):**
```
https://travel-planner-backend-xbsp.onrender.com/docs
```
- Testuj endpointy bezpośrednio w przeglądarce
- Authorize z JWT tokenem (kliknij 🔒 w prawym górnym rogu)
- Wypróbuj request/response live

### **2. ReDoc (czytelna dokumentacja):**
```
https://travel-planner-backend-xbsp.onrender.com/redoc
```
- Czytelniejszy format niż Swagger
- Dobry do czytania schemas

---

## 🆘 Jeśli dev frontu ma więcej pytań:

Może pisać bezpośrednio do mnie (przez Ciebie lub bezpośrednio jeśli chcesz):
- Pytania techniczne
- Problemy z integracją
- Prośby o dodatkowe tokeny
- Zmiany w API (jeśli coś nie pasuje do frontendu)

**Jestem dostępny** - lepiej wyjaśnić teraz niż guessować! 🙂

---

Pytania? Daj znać!

Pozdrawiam,
Mateusz

P.S. Jeśli dev frontu potrzebuje **5 test tokenów po 7 dni** → napisz, wygeneruję paczkę! 🎁
