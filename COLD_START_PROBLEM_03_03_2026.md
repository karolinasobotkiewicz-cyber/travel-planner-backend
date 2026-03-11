# PROBLEM: COLD START - API NIE ODPOWIADA

**Data:** 03.03.2026  
**Zgłoszone przez:** Karolina (problem z frontendu)  
**Status:** Zdiagnozowane + rozwiązania poniżej

---

## 🔴 CO SIĘ DZIEJE

**Screenshot pokazuje:**
```
13:32:36 INCOMING HTTP REQUEST DETECTED ...
13:32:39 SERVICE WAKING UP ...
13:32:43 ALLOCATING COMPUTE RESOURCES ...
13:32:46 PREPARING INSTANCE FOR INITIALIZATION ...
13:32:50 STARTING THE INSTANCE ...
13:32:56 ENVIRONMENT VARIABLES INJECTED ...
13:32:58 FINALIZING STARTUP ...
13:33:00 OPTIMIZING DEPLOYMENT ...
13:33:02 STEADY HANDS. CLEAN LOGS. YOUR APP IS ALMOST LIVE...
```

**To jest klasyczny COLD START na Render Free Tier:**
- Po ~15 minutach bez requestów → Render uśypia instancję
- Pierwsze request po przebudzeniu → budzi serwer (30-60 sekund)
- Następne requesty → działają normalnie (instant)

---

## 🧪 WERYFIKACJA (03.03.2026 13:40)

**Test:**
```bash
curl https://travel-planner-backend-xbsp.onrender.com/health
```

**Wynik:**
```json
{
  "status": "ok",
  "service": "travel-planner-api",
  "version": "2.0.0",
  "database": "connected"
}
```

✅ **API DZIAŁA POPRAWNIE**

**Wniosek:** Problem nie jest w backendzie. Backend się budzi i odpowiada - tylko trwa to 30-60 sekund przy cold start.

---

## 🔥 DLACZEGO FRONTEND DOSTAJE BŁĄD

**Prawdopodobna przyczyna:**

Frontend ma **za krótki timeout** (np. 10-15 sekund):
```javascript
// Przykład (gdzieś w kodzie frontu):
axios.get('https://travel-planner-backend-xbsp.onrender.com/api/...', {
  timeout: 10000  // ← 10 sekund to za mało przy cold start!
})
```

**Co się dzieje:**
1. Frontend wysyła request (np. generuj plan)
2. Backend śpi → cold start zaczyna się (30-60 sek)
3. Frontend czeka 10 sekund → timeout → wyrzuca błąd "nie mogę się połączyć"
4. Backend się budzi po 30 sekundach (ale frontend już wyrzucił błąd)

---

## ✅ ROZWIĄZANIA

### **1. FIX FRONTEND (pilne - natychmiast)**

**Co zrobić:**
Zwiększyć timeout w requestach do **90 sekund** (żeby dać czas na cold start).

**Jak:**
```javascript
// W axios config lub fetch config:
axios.get('https://travel-planner-backend-xbsp.onrender.com/api/...', {
  timeout: 90000  // 90 sekund (daje czas na cold start)
})

// Albo w fetch:
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 90000);

fetch('https://travel-planner-backend-xbsp.onrender.com/api/...', {
  signal: controller.signal
})
```

**Plus dodać komunikat dla usera:**
```javascript
// Pokazać loading message:
"Budzę serwer (może zająć 30-60 sekund)..."
// albo
"Przygotowuję system, proszę czekać..."
```

**Gdzie to zmienić:**
- Gdziekolwiek frontend robi requesty do API
- Najpewniej w jakimś `api.js` albo `apiClient.js` albo w componencie

---

### **2. BACKEND: DODAĆ ENDPOINT /PING (szybki fix)**

**Co:**
Dodać lekki endpoint który można pingować co 10 minut żeby nie dopuścić do cold start.

**Jak:**
```python
# W main.py dodać:
@app.get("/ping")
async def ping():
    return {"status": "pong", "timestamp": datetime.now().isoformat()}
```

**Potem frontend może:**
- Co 10 minut wysłać silent request do `/ping` w tle
- Albo użyć external service (UptimeRobot, Pingdom) żeby pingował co 10 minut

**Wady:**
- Render free tier ma limit 750h/miesiąc (pingowanie zużywa ten limit)
- Po ~500h miesięcznie zostaniesz bez free hours

---

### **3. UPGRADE RENDER PLAN (najlepsze długoterminowo)**

**Plan:** Render Starter ($7/miesiąc)

**Co dostaniesz:**
- ✅ Zero cold starts (serwer zawsze online)
- ✅ Szybsze odpowiedzi (instant)
- ✅ Więcej RAM (512MB → 1GB)
- ✅ Lepszy SLA

**Kiedy warto:**
- Przed startem MVP (żeby users nie czekali 60 sekund)
- Jak masz >10 userów dziennie
- Jak robisz demo dla inwestorów/klientów

**Link:** https://render.com/pricing

---

## 🎯 CO POLECAM TERAZ

### **PILNE (dzisiaj):**

**1. Powiedz frontendowi:**
"Zwiększcie timeout do 90 sekund przy requestach do API. Backend działa poprawnie, ale Render free tier ma cold start (30-60 sek gdy serwer śpi). To normalne."

**2. Dodajcie komunikat dla usera:**
"Przygotowuję plan podróży (może zająć do 60 sekund)..."

---

### **OPCJONALNIE (w tym tygodniu):**

**3. Możesz dodać endpoint /ping:**
Ja dodam prosty endpoint `/ping`. Frontend może go pingować co 10 minut w tle żeby serwer nie zasypiał. Ale uwaga: zużyje to free hours na Render.

**Czy chcesz to?** Daj znać, dodam w 5 minut.

---

### **DŁUGOTERMINOWO (przed startem MVP):**

**4. Upgrade Render do $7/miesiąc:**
Jak będziesz gotowa na start publiczny - warto zrobić upgrade. Zero cold starts to must-have dla dobrego UX.

---

## 📊 WERYFIKACJA PO FIXIE

**Jak sprawdzić czy fix działa:**

1. Odczekaj 20 minut (żeby API na pewno zasnęło)
2. Otwórz frontend
3. Spróbuj wygenerować plan
4. **Powinno:**
   - Frontend pokazuje "Loading..." albo "Budzę serwer..."
   - Czeka 30-60 sekund
   - API się budzi
   - Plan się generuje ✅

5. **Sprawdź drugi raz (od razu po pierwszym):**
   - Powinno być instant (bo API już nie śpi)

---

## 🔧 GDY CHCESZ BĄDĘ JA MOGĘ POMÓC

**Jeśli frontend nie wie jak zmienić timeout:**
- Mogę podać dokładny kod (ale potrzebuję wiedzieć czego używają: axios? fetch? inne?)
- Albo mogę dodać od siebie endpoint `/ping` + instrukcje jak go użyć

**Jeśli chcesz upgrade Render:**
- To rob sama (to Twoje konto)
- Ale mogę pomóc z migracją/testami

---

## ✅ PODSUMOWANIE

**Problem:**
- Render free tier = cold start (30-60 sek)
- Frontend timeout za krótki (10 sek)
- Frontend wyrzuca błąd zanim API się obudzi

**Fix:**
1. Frontend: timeout 90 sekund + komunikat "Loading..."
2. Opcjonalnie: /ping endpoint (żeby nie zasypiał)
3. Długoterminowo: Render $7/miesiąc (zero cold starts)

**Backend działa OK** - to nie jest bug, to feature Render free tier 😅

---

**Pytania?** Daj znać jeśli frontend potrzebuje pomocy z timeoutem albo chcesz żebym dodał /ping endpoint.

**Mateusz**
