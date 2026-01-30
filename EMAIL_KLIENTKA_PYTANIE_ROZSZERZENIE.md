# ODPOWIEDŹ DLA KLIENTKI - PREFERENCES & TRAVEL STYLE

**Data:** 28.01.2026  
**Temat:** Rozszerzenie ETAPU 1 - preferences + travel_style scoring  

================================================================================

Cześć Karolino,

Dzięki za feedback i link do frontu - wszystko jasne! 👍

Sprawdziłem dokładnie co trzeba zrobić i przygotowałem szczegółowy plan.

---

## ✅ CO BĘDZIE DODANE:

### 1. **Pole `travel_style` w TripInput**
Obecnie go nie ma (był tylko w starych test fixtures). Doda  ję:
```json
{
  "travel_style": "cultural"  // cultural / adventure / relax / balanced
}
```

### 2. **Moduł `preferences.py` - Preferences scoring**
**Logika:**
- User preferences (tags) matchują z POI tags
- **Za każdy matching tag: +5 punktów**

**Przykład:**
```json
user.preferences = ["outdoor", "family"]
poi.tags = ["outdoor", "mountain", "hiking"]

Matching: "outdoor" → +5 punktów
Result: Plan będzie preferował POI z outdoor tagiem
```

### 3. **Moduł `travel_style.py` - Travel style scoring**
**Logika:**
- travel_style (cultural/adventure/relax) matchuje z activity_style POI (active/relax/balanced)
- **Perfect match: +6 punktów**
- **Partial match: +3 punkty**

**Przykład:**
```json
user.travel_style = "adventure"
poi.activity_style = "active"

Perfect match → +6 punktów
Result: Plan dobierze więcej aktywnych atrakcji
```

---

## ⏱️ SZACUNEK CZASOWY:

| Task | Czas |
|------|------|
| Pole travel_style w TripInput | 5 min |
| Moduł preferences.py + 5 testów | 30 min |
| Moduł travel_style.py + 6 testów | 30 min |
| Integracja w engine.py | 10 min |
| Update trip_mapper.py | 5 min |
| Testy integracyjne | 30 min |
| Manual testing + dokumentacja | 20 min |
| Deploy + weryfikacja | 20 min |

**TOTAL: ~2.5h robocze** (0.3 dnia roboczego)

---

## 💰 BUDŻET - CZY TO SIĘ MIEŚCI W ETAPIE 1?

✅ **TAK** - mieści się w zakresie ETAPU 1

**Uzasadnienie:**
1. Umowa zakłada "logikę silnika 1 dnia z scoringiem"
2. Bez tego frontend wygląda jakby był zepsuty (user wybiera ale nic się nie dzieje)
3. To są MINIMALNE features żeby UX miał sens
4. To nie jest "nowa feature" tylko dopełnienie istniejącego systemu scoringowego
5. 2.5h to margines błędu w 5-dniowym projekcie

**Konkluzja:** Brak potrzeby renegocjacji - to jest część scoringu.

---

## 🚀 PLAN WYKONANIA:

**Timeline:**
- **Start:** 28.01.2026 wieczorem (po Twojej akceptacji)
- **Koniec:** 29.01.2026 rano
- **Deploy:** 29.01.2026 przed 12:00
- **Deadline:** 29.01.2026 18:00 ✅ (6h zapasu)

**Kolejność:**
1. Implementacja modułów (1.5h)
2. Testy + weryfikacja (30 min)
3. Deploy (30 min)
4. Email z przykładami

---

## 📝 CO BĘDZIESZ MOGŁA TESTOWAĆ:

**Request A (adventure + outdoor):**
```json
{
  "travel_style": "adventure",
  "preferences": ["outdoor", "hiking"],
  "location": {"city": "Zakopane"},
  ...
}
```

**Request B (relax + museums):**
```json
{
  "travel_style": "relax",
  "preferences": ["museums", "spa"],
  "location": {"city": "Zakopane"},
  ...
}
```

**Expected result:** Plany mają RÓŻNE POI (adventure → aktywne atrakcje, relax → spokojne miejsca)

---

## ❓ PYTANIA DO CIEBIE:

### 1. **Czy akceptujesz ten zakres jako część ETAPU 1?**
✅ TAK, robimy to teraz  
❌ NIE, zostawiamy na ETAP 2

### 2. **Czy wagi scoringu są OK?**
- Preferences: +5 pkt za matching tag
- Travel style: +6 pkt (perfect match), +3 pkt (partial match)

Jeśli wydają Ci się za słabe/mocne - mogę dostosować.

### 3. **Czy są jakieś inne pola z frontu które muszą wpływać na plan?**
Sprawdziłem frontend ale mogłem coś przeoczyć. Jeśli są inne pola - daj znać teraz.

---

## 🎯 NEXT STEPS:

**Po Twojej akceptacji:**
1. Zaczynam implementację dzisiaj wieczorem
2. Jutro rano deploy + testy
3. Email z live URL + przykładami
4. Możesz testować z frontem

**Jeśli odrzucisz:**
- Zostawiamy to na ETAP 2
- Delivery ETAP 1 bez tych features (28.01 wieczorem)

---

Daj znać co decydujesz - czekam na Twoją odpowiedź! 🚀

Pozdrawiam,  
Mateusz

---

**P.S.** Mamy 32h zapasu do deadline (29.01 18:00), więc spokojnie możemy to zrobić bez ryzyka opóźnień.
