# CLIENT FEEDBACK - UAT TESTING (18.02.2026)

**Data:** 18.02.2026  
**Źródło:** Karolina (klientka)  
**Kontekst:** User Acceptance Testing po naprawie 12 problemów + critical overlap bug  
**Status:** Feedback w trakcie zbierania (TEST 01 otrzymany, czekam na resztę)

---

## 📋 STRUKTURA UAT

**Klientka testuje na tych samych grupach co wcześniej:**
- Test 01: Familie z dzieckiem 8 lat (już otrzymany)
- Test 02: (oczekiwany)
- Test 03: (oczekiwany)
- Test 04+: (oczekiwany)

**Cel UAT:**
Weryfikacja że wszystkie 12 problemów + critical overlap bug zostały naprawione i system działa poprawnie w produkcji.

---

## ✅ TEST 01: RODZINA Z DZIECKIEM 8 LAT

### Parametry Testu:
```json
{
  "group": {
    "type": "family_kids",
    "size": 4,
    "children_age": 8,
    "crowd_tolerance": 1
  },
  "trip_length": {
    "days": 3
  },
  "preferences": [
    "nature_landscape",
    "mountain_trails",
    "kids_attractions"
  ],
  "budget": {
    "level": 2
  }
}
```

### ✅ CO WYGLĄDA SUPER:

#### 1. **Brak absurdalnych przeskoków, sensowny rytm dnia**
- Start rano, powrót do 19:00 ✅
- Plan jest logiczny i realistyczny ✅

#### 2. **Czasy przejazdów wiarygodnie**
- 15-20 min między lokalizacjami ✅
- Konsekwentnie wpisane ✅

#### 3. **Brak nadmiarowych przerw**
- Nie ma już przerw co chwilę ✅
- Problem z "free_time co 10 min" naprawiony ✅

#### 4. **Zgodność z preferencjami nature + mountain**
- Dolina Kościeliska ✅
- Rusinowa Polana ✅
- Morskie Oko ✅
- Pełna zgodność z "nature_landscape + mountain_trails" ✅

#### 5. **Proper badges dla core attractions**
- Morskie Oko, Rusinowa Polana, Kościeliska mają:
  * `must_see` ✅
  * `core_attraction` ✅
  * `family_favorite` ✅
- Dla rodziny z dzieckiem 8 lat to jest "core" i prawidłowo oznaczone ✅

#### 6. **Dni są tematyczne**
- **Day 1:** Klasyk szlak + symbol Zakopanego (Wielka Krokiew) ✅
- **Day 2:** Szlak + kultura (Oksza, kaplica, Koliba) ✅
- **Day 3:** Top widokowy (Morskie Oko) + krótki element kultury (kaplica) ✅

#### 7. **Plan jest bardziej czysty i realistyczny**
- Wcześniej w Day 1 wpadało 6-8 drobnych atrakcji "po 20 min"
- Teraz plan jest bardziej czysty i realistyczny ✅

#### 8. **Parking + walk_time_min są obecne**
- To jest "realny" detal, który lubią użytkownicy ✅
- Wszystkie parking items mają walk_time_min ✅

---

### ❌ CO NADAL NIE DO KOŃCA GRA:

#### **Problem #1: Brakuje elementów stricte kids**

**Opis:**
- Preferencje zawierają `kids_attractions`
- W 3 dniach brak stricte kids POI:
  * **Day 1:** Brak stricte kids (poza tym, że Kościeliska i Krokiew są "family friendly")
  * **Day 2:** Kultura (muzea, kaplica)
  * **Day 3:** Morskie Oko + kaplica

**Oczekiwanie:**
- Przy `preferences: ["kids_attractions"]` engine powinien priorytetyzować POI z `kids_only: true` lub `target_groups: ["family_kids"]`
- Przykłady stricte kids POI w Zakopanem:
  * Tatrzańskie Mini Zoo (poi_2)
  * Kuźnice (kolejka)
  * Dom do góry nogami (poi_13)
  * Podwodny Świat akwarium (poi_6)

**Jak to naprawić:**
1. W `score_poi()` w engine.py: dodać bonus za `preferences` match
2. Jeśli `user.preferences` zawiera "kids_attractions":
   - POI z `kids_only: true` → +15 punktów
   - POI z `target_groups: ["family_kids"]` → +10 punktów
3. Zapewnić że co najmniej 1-2 stricte kids POI w planie 3-dniowym

**Priorytet:** 🔴 HIGH (to jest część user preferences, która powinna działać)

---

#### **Problem #2: Day 3 jest trochę "urwany"**

**Opis:**
- Po Morskim Oku (09:22-12:22, 180 min) jest tylko:
  * Free time (13:12-13:34, 22 min)
  * Lunch (13:34-14:14, 40 min)
  * Day end (19:00)
- Zostaje **~4.5 godziny wolnego czasu** (14:14-19:00) bez żadnych aktywności

**Oczekiwanie:**
- Po Morskim Oku powinny być jeszcze 1-2 atrakcje (lekkie, bo po długim szlaku)
- Przykłady sensownych POI po Morskim Oku:
  * Kaplica Jaszczurówka (15 min, relax)
  * Muzeum Tatrzańskie (45-60 min, kultura)
  * Krupówki (shopping/spacer)
  * Termy (lekki relax dla zmęczonej rodziny)

**Jak to naprawić:**
1. W `build_day()` w engine.py: po długiej atrakcji (>120 min) sprawdzić czy jest jeszcze czas na lekką aktywność
2. Jeśli zostaje >3h wolnego czasu → wypełnić 1-2 lekkimi POI
3. Energy system: po długim szlaku (energy -3) proponować lekkie aktywności (energy -1)

**Priorytet:** 🟡 MEDIUM (plan jest funkcjonalny, ale nie optymalny)

---

#### **Problem #3: Crowd_tolerance = 1, a plan ma topowe magnesy**

**Opis:**
- User ma `crowd_tolerance: 1` (0=low, 3=high) → niska tolerancja na tłumy
- Plan zawiera topowe magnesy tłumów:
  * Rusinowa Polana (Day 1)
  * Morskie Oko (Day 3)
- Te miejsca w sezonie zimowym potrafią być BARDZO tłoczne

**Current behavior:**
- Plan zaczyna wcześnie (09:00), więc jest lepiej
- Ale brak wyraźnych "antytłumowych" wskazówek

**Oczekiwanie:**
1. **Algorytm powinien:**
   - Dorzucać wyraźne "antytłumowe" tipy w `pro_tip`:
     * "Jedź o 7:00 rano, żeby uniknąć tłumów"
     * "Unikaj weekendów i ferii zimowych"
     * "W sezonie (grudzień-luty) może być bardzo tłoczno"
   - Lub proponować alternatywę "gdy tłum/warunki":
     * "Jeśli Morskie Oko za tłoczne, rozważ Dolinę Pięciu Stawów"

2. **Możliwe rozwiązanie:**
   - W `explainability.py`: dla POI z `popularity: high` + `crowd_tolerance: 0-1`:
     * Dodać warning w `pro_tip`: "Popularne miejsce - jedź wcześnie lub poza sezonem"
   - W `engine.py`: przy `crowd_tolerance: 0-1` preferować POI z `popularity: low` lub `popularity: medium`

**Priorytet:** 🟡 MEDIUM (UX improvement, nie blocker)

---

## 📊 PODSUMOWANIE TEST 01:

**Pozytywne (8 punktów):**
✅ Rytm dnia sensowny  
✅ Czasy przejazdów wiarygodne  
✅ Brak nadmiarowych przerw  
✅ Zgodność z nature/mountain preferences  
✅ Proper badges dla core attractions  
✅ Dni tematyczne  
✅ Plan czysty i realistyczny  
✅ Parking details obecne  

**Do poprawy (3 problemy):**
❌ Brakuje stricte kids attractions (HIGH priority)  
❌ Day 3 urwany po Morskim Oku (MEDIUM priority)  
❌ Brak crowd warnings dla topowych magnesów (MEDIUM priority)  

**Status:** 🟡 **8/11 punktów** - większość działa świetnie, 3 problemy do naprawy

---

## 🔜 NASTĘPNE KROKI:

1. ⏳ **Poczekać na feedback z pozostałych testów** (Test 02, 03, 04...)
2. ⏳ **Zgrupować wszystkie problemy** z wszystkich testów
3. ⏳ **Priorytetyzować** (HIGH/MEDIUM/LOW)
4. ⏳ **Zaplanować implementację** zgodnie z ETAP2_PLAN_DZIALANIA.md
5. ⏳ **Unikać duplikacji kodu** i regressji w istniejących funkcjach

**WAŻNE:**
- Nie wprowadzać zmian dopóki nie mam pełnego feedbacku ze wszystkich testów
- Trzymać się kontekstu i struktury ETAP2_PLAN_DZIALANIA.md
- Unikać sytuacji gdzie jedno robimy, a drugie przestaje działać
- Każda zmiana = testy regresji (wszystkie 12 problemów muszą nadal działać)

---

## 📝 NOTATKI TECHNICZNE:

### Pliki do potencjalnych zmian:
1. **app/domain/planner/engine.py**
   - Funkcja `score_poi()` - dodać bonus za kids_attractions match
   - Funkcja `build_day()` - wypełniać długie luki po długich atrakcjach
   
2. **app/domain/planner/explainability.py**
   - Dodać crowd warnings dla popular POI + low crowd_tolerance

3. **app/domain/scoring/*.py**
   - Możliwe że trzeba zmodyfikować scoring modules dla preferences

### Zasady implementacji:
- ✅ Każda zmiana musi być backward compatible
- ✅ Testy regresji po każdej zmianie (11 test files)
- ✅ Dokumentacja w commit message
- ✅ Update ETAP2_PLAN_DZIALANIA.md po implementacji

---

---

## ✅ TEST 02: PARA - CULTURAL STYLE

### Parametry Testu:
```json
{
  "group": {
    "type": "couples",
    "size": 2
  },
  "trip_length": {
    "days": 3
  },
  "preferences": [
    "museum_heritage",
    "relaxation",
    "local_food_experience"
  ],
  "travel_style": "cultural",
  "budget": {
    "level": 2
  }
}
```

### ✅ CO WYGLĄDA SUPER:

#### 1. **Day 1 ma świetny kręgosłup**
- Muzeum Tatrzańskie → Oksza: logiczne pod kulturę ✅
- Zgodne ze stylem "cultural" ✅

#### 2. **Kulig jako "premium_experience"**
- Bardzo trafione dla pary i zimy ✅

---

### ❌ CO NADAL NIE DO KOŃCA GRA:

#### **Problem A: Plan ignoruje preferences (szczególnie Day 3)**

**Opis:**
- Preferencje: `museum_heritage + relaxation + local_food_experience`
- Plan Day 3 generuje: **Podwodny Świat, Mini Zoo, Myszogród**
- To są typowe "family/kids" atrakcje, a nie cultural dla pary

**Analiza:**
> "System chyba za mocno idzie w 'popularne w Zakopanem' + 'romantic experiences' i zbyt słabo filtruje po preferencjach."

**Oczekiwanie:**
- Day 3 powinien mieć: muzea, galerie, restauracje regionalne, degustacje
- Preferencje powinny być **hard filter**, nie tylko soft scoring

**Priorytet:** 🔴 **CRITICAL** - preferencje użytkownika są całkowicie ignorowane

---

#### **Problem B: why_selected jest szablonowe**

**Opis:**
- Prawie wszystko ma: **"Perfect for couples seeking romantic experiences"**
- Dom do góry nogami: raczej nie należy do romantycznych ❌
- Mini ZOO: nie romantyczne ❌
- Myszogród: nie romantyczne ❌

**Oczekiwanie:**
> "Możemy zrobić tak żeby why_selected wynikało z matchowania do preferencji + stylu + crowd tolerance, a nie z szablonu?"

**Jak to naprawić:**
- `why_selected` powinno być dynamiczne na podstawie:
  * User preferences match
  * Travel style match
  * Crowd tolerance consideration
  * Actual POI characteristics (nie generyczne "romantic")

**Priorytet:** 🟡 **MEDIUM** - UX quality issue

---

#### **Problem C: Dzień 2 jest "pusty"**

**Opis:**
- Day 2: Rusinowa Polana + lunch + Koliba i koniec
- Brakuje:
  * Drugiego muzeum/galerii
  * Spaceru po mieście
  * **Degustacji/kolacji (local_food_experience!)**
  * Term
  * Kawiarni
  * Punktu widokowego

**Oczekiwanie:**
- Preferencja `local_food_experience` powinna generować:
  * Kolację w regionalnej restauracji
  * Degustację oscypka
  * Wizytę w bacówce
- Plan 3-dniowy powinien mieć min 2 muzea (jest tylko 1)

**Priorytet:** 🔴 **HIGH** - preferencja `local_food_experience` całkowicie ignorowana

---

#### **Problem D: Powtarzanie tych samych POI między dniami**

**Opis:**
1. **Kaplica Jaszczurówka** pojawia się w Day 1 i Day 3 ❌
2. **Rusinowa Polana** w planie pary "cultural":
   - To jest ładne i może pasować jako "romantic nature"
   - Ale preferencje **nie zawierają** `nature_trails` ❌

**Oczekiwanie:**
- Cross-day tracking powinien eliminować powtórki
- POI selection powinien filtrować po preferencjach (brak nature_trails = brak szlaków górskich)

**Priorytet:** 🟡 **MEDIUM** - powtórki + niepasujące POI

---

#### **Problem E: Termy Gorący Potok są dopiero Day 3**

**Opis:**
- Preferencja: `relaxation`
- Termy Gorący Potok są dopiero Day 3
- **Powinny być centralnym filarem relaksu**

**Oczekiwanie:**
> "Skoro preferences mają relaxation, to termy powinny być albo Day 2 jako 'reset day' albo Day 1 po muzeach, jeśli nie ma kuligu."

**Priorytet:** 🟡 **MEDIUM** - błędna kolejność w realizacji preferencji

---

## ✅ TEST 03: FRIENDS - ADVENTURE + ACTIVE_SPORT

### Parametry Testu:
```json
{
  "group": {
    "type": "friends",
    "size": 4
  },
  "trip_length": {
    "days": 3
  },
  "preferences": [
    "active_sport",
    "history_mystery",
    "adventure"
  ],
  "travel_style": "adventure",
  "budget": {
    "level": 2
  }
}
```

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: Plan nie realizuje preferencji "active_sport"**

**Opis Day 1:**
- Krokiew (45 min zwiedzania) - to bardziej "viewpoint/attraction", **nie sport** ❌
- Muzea, Dom do góry nogami - to średnio ❌
- Termy na koniec dnia - super ✅

**Analiza:**
> "To jest styl 'mixed city + relax', a nie adventure + active_sport."

**Oczekiwanie:**
- Dla `active_sport` powinno być:
  * Narty/snowboard
  * Wspinaczka w hali
  * Szlaki górskie (intensywne)
  * Kolejki/wyciągi na szczyty
  * Quad/motosanie

**Priorytet:** 🔴 **CRITICAL** - preferencja active_sport całkowicie ignorowana

---

#### **Problem B: "history_mystery" jest prawie nieobecne**

**Opis:**
- Preferencja: `history_mystery`
- W planie brak "mystery" attractions

**Komentarz klientki:**
> "Aczkolwiek podejrzewam że to przez to, że baza na Zakopane jest mocno ograniczona. Możemy w sobotę podpiąć np. całą bazę atrakcji z Małopolski i zrobić testy na innych miastach np. Krakowie?"

**Oczekiwanie:**
- Sprawdzić czy scoring traktuje "history_mystery" jak zwykłe "history/culture"
- Rozszerzyć bazę POI o Małopolskę dla testów w Krakowie

**Priorytet:** 🟡 **MEDIUM** - możliwy problem z bazą danych POI

---

#### **Problem C: Wpychanie atrakcji kids/family jest totalnie nietrafione**

**Opis:**
- Grupa: `friends + adventure`
- Plan zawiera typowe family/kids POI

**Komentarz klientki:**
> "Tutaj też pytanie czy brakuje nam twardego filtra po preferencjach czy też po prostu baza POI jest zbyt ograniczona"

**Oczekiwanie:**
- Dla `friends` grupa: exclude `kids_only` POI
- Dla `adventure` style: preferować outdoor/sport/extreme POI

**Priorytet:** 🔴 **HIGH** - target group filtering nie działa

---

#### **Problem D: Day 1 ma wielkie dziury czasowe (BARDZO WAŻNE)**

**Opis:**
- Po termach dzień kończy się o **16:46**
- Potem: `free_time 19:23-21:00` w **trzech segmentach** (22 + 40 + 35 min)
- **Brakuje czasu 16:46-19:23** (2.5 godziny luki!)

**Oczekiwanie:**
- Wypełnić luki czasowe po atrakcjach
- Nie generować wielokrotnych `free_time` segmentów
- Logiczne domknięcie dnia

**Priorytet:** 🔴 **CRITICAL** - harmonogram dnia jest niepoprawny

---

#### **Problem E: Parking references niespójne**

**Opis:**
- Muzeum Tatrzańskie ma parking "Krupówki 20"
- Ale item parking w Day 1 jest "Parking miejski" pod Krokwią
- Brakuje przystanku parkingowego przed muzeum

**Oczekiwanie:**
- Albo trzeba logicznie reużyć "ten sam parking" z dojazdem pieszo
- Albo dodać nowy parking item przed muzeum

**Priorytet:** 🟡 **MEDIUM** - niespójność w parking logic

---

## ✅ TEST 04: SOLO - 5 DNI, HISTORY_MYSTERY, CROWD_TOLERANCE=1

### Parametry Testu:
```json
{
  "group": {
    "type": "solo",
    "size": 1,
    "crowd_tolerance": 1
  },
  "trip_length": {
    "days": 5
  },
  "preferences": [
    "nature",
    "history_mystery",
    "museum_heritage"
  ],
  "budget": {
    "level": 2
  }
}
```

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: Preferencja "history_mystery" praktycznie nie jest realizowana**

**Opis:**
- W całym 5-dniowym planie nie ma nic, co jest **"mystery"**
- Jest heritage (muzea, kaplica), jest natura
- Brak elementów związanych z tajemnicami, legendami, underground

**Pytanie klientki:**
> "Sprawdź proszę czy scoring traktuje to jak zwykłe 'history/culture'?"

**Oczekiwanie:**
- Scoring powinien różnicować między:
  * `history` (zwykła historia)
  * `mystery` (legendy, tajemnice, underground)
- POI z `mystery` tags powinny dostawać bonus dla `history_mystery` preference

**Priorytet:** 🔴 **HIGH** - preferencja mystery ignorowana

---

#### **Problem B: Tolerancja tłumu = 1, a plan wrzuca Krupówki**

**Opis:**
- User ma `crowd_tolerance: 1` (niska tolerancja na tłumy)
- Plan zawiera:
  * Muzeum Tatrzańskie na Krupówkach - ok, to cel "heritage" ✅
  * **Day 4:** Dom do góry nogami, Podwodny Świat, Mini Zoo - bardzo tłoczne miejsca ❌

**Oczekiwanie:**
- Dla `solo + crowd_tolerance 1` powinno być mocno zbijane
- Preferować spokojne miejsca, mniej popularne trasy

**Priorytet:** 🔴 **HIGH** - crowd_tolerance całkowicie ignorowane

---

#### **Problem C: Day 4 jest tematycznie nietrafiony (family/kids zapychacz)**

**Opis:**
- Preferencje: `nature + history_mystery + museum_heritage`
- Day 4: Koliba (ok) → Dom do góry nogami (nie) → Podwodny świat (nie) → kaplica (ok) → mini zoo (nie)

**Oczekiwanie:**
> "To powinien być dzień spokojny heritage albo lekka natura."

**Priorytet:** 🔴 **HIGH** - day composition całkowicie nietrafiona

---

#### **Problem D: Day 5 ma duży błąd w harmonogramie (dziura czasowa)**

**Opis Day 5:**
- Termy: 09:47–11:47
- Atma: 12:06–12:36
- **Lunch dopiero: 14:28–15:08**
- **Dziura: 12:36–14:28** (prawie 2 godziny pustki!)

**Oczekiwanie:**
- Lunch powinien być między 12:00-14:30 (Problem #8 z poprzedniego feedbacku)
- Nie powinno być dużych luk czasowych między atrakcjami

**Priorytet:** 🔴 **HIGH** - harmonogram niepoprawny

---

## ✅ TEST 05: RODZINA - KIDS_ATTRACTIONS + RELAXATION

### Parametry Testu:
```json
{
  "group": {
    "type": "family_kids",
    "size": 4,
    "children_age": 6
  },
  "trip_length": {
    "days": 2
  },
  "preferences": [
    "kids_attractions",
    "relaxation",
    "local_food"
  ],
  "travel_style": "relax",
  "budget": {
    "level": 2
  }
}
```

### ✅ CO JEST SUPER:

#### **Day 1 (Rusinowa Polana + lunch)**
- 10:00 start i jedna główna aktywność + lunch = relax style faktycznie zachowany ✅
- 150 minut na polanę jest sensowne jako "spacer rodzinny" ✅

---

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: Mało "kids_attractions"**

**Opis:**
- Preferencja: `kids_attractions`
- W planie 2-dniowym brak stricte kids POI
- Powinno być: Mini Zoo, Podwodny Świat, Dom do góry nogami

**Priorytet:** 🔴 **CRITICAL** - preferencja kids_attractions ignorowana (powtórka z Test 01)

---

#### **Problem B: Brak zagospodarowania 14:22-16:00**

**Opis:**
- Od lunchu do końca dnia jest pusto
- **1.5 godziny luki**

**Oczekiwanie:**
- Dodać lekką aktywność dla dzieci (plac zabaw, mini zoo, spacer)

**Priorytet:** 🟡 **MEDIUM** - niepełne wykorzystanie dnia

---

#### **Problem C: Dzień 2 nie realizuje "relaxation"**

**Opis Day 2:**
- Krokiew + kaplica + Podwodny Świat + lunch + Muzeum Stylu
- **Brak:** term, spokojnego miejsca

**Analiza:**
> "To wygląda trochę jak plan 'kultura i must-see', a nie 'relaks + dzieci'."

**Oczekiwanie:**
- Dla `relaxation` preference: termy/spa **must be included**
- Day 2 powinien mieć termy jako główną aktywność relaksową

**Priorytet:** 🔴 **HIGH** - preferencja relaxation ignorowana

---

#### **Problem D: Crowd tolerance = 1 ignorowane**

**Opis:**
- `crowd_tolerance: 1`
- Plan zawiera:
  * Wielka Krokiew - potrafi być tłoczna ❌
  * Muzea w centrum i okolice Krupówek - tłoczne ❌

**Oczekiwanie:**
> "Tu powinien wejść silny filtr/penalty na miejsca popularne (albo przynajmniej preferencja godzin/alternatyw)."

**Priorytet:** 🔴 **HIGH** - crowd_tolerance ignorowane (powtórka)

---

#### **Problem E: why_selected puste dla Podwodnego Świata**

**Opis:**
- Podwodny Świat ma puste lub generyczne `why_selected`

**Priorytet:** 🟡 **LOW** - quality issue, nie blocker

---

## ✅ TEST 06: PARA - RELAX, NATURE_LANDSCAPE, CROWD_TOLERANCE=1

### Parametry Testu:
```json
{
  "group": {
    "type": "couples",
    "size": 2,
    "crowd_tolerance": 1
  },
  "trip_length": {
    "days": 3
  },
  "preferences": [
    "nature_landscape",
    "museum_heritage",
    "relaxation"
  ],
  "travel_style": "relax",
  "budget": {
    "level": 2
  }
}
```

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: Day 1 - Crowd_tolerance=1 a startujesz od Krokwi**

**Opis:**
- Krokiew bywa zatłoczona
- Przy `crowd=1` powinno być:
  * Warning w `pro_tip` o tłumach
  * Alternatywna propozycja
  * Start wcześnie rano (przed tłumami)

**Priorytet:** 🔴 **HIGH** - crowd_tolerance ignorowane (powtórka)

---

#### **Problem B: Brak "relaxation" jako faktycznej atrakcji**

**Opis:**
- Preferencja: `relaxation`
- Brak: term / spa / widokowy spacer (lekki)

**Oczekiwanie:**
- Termy/spa są **must-have** dla relaxation preference

**Priorytet:** 🔴 **CRITICAL** - kluczowa preferencja ignorowana (powtórka)

---

#### **Problem C: Brak "nature_landscape" w dniu 1**

**Opis:**
- Preferencja: `nature_landscape`
- Day 1: 100% miejski-kulturowy (Krokiew, muzea)
- Brak natury

**Oczekiwanie:**
- Day 1 powinien mieć przynajmniej 1 POI nature (polana, dolina, jezioro)

**Priorytet:** 🟡 **MEDIUM** - preferencja słabo realizowana

---

#### **Problem D: Dzień 2 to muzealny maraton, a nie "relax"**

**Opis Day 2:**
- Muzeum Tatrzańskie + Makuszyński + Atma + lunch + Mini Zoo
- To jest maraton kulturowy, nie relaks

**Oczekiwanie:**
- Dla `relax` style: max 2 atrakcje/dzień, więcej czasu na odpoczynek

**Priorytet:** 🟡 **MEDIUM** - travel style ignorowany

---

#### **Problem E: Parking "Krupówki 20" przy crowd_tolerance=1**

**Opis:**
- Parking "Krupówki 20" i okolice to potencjalnie tłum
- Przy `crowd=1` engine powinien preferować spokojniejsze rejony

**Oczekiwanie:**
- Albo `pro_tip` o godzinach i omijaniu szczytu
- Albo wybór spokojniejszego parkingu

**Priorytet:** 🟡 **MEDIUM** - UX improvement

---

#### **Problem F: Day 3 - ogromna luka 14:22–18:00**

**Opis:**
- Rusinowa Polana + lunch i koniec o 14:22
- **Luka: 14:22–18:00** (3.5 godziny!)

**Oczekiwanie:**
> "Myślę że warto tu domknąć dzień dodatkową lekką atrakcją relaksową."

**Priorytet:** 🟡 **MEDIUM** - niepełne wykorzystanie dnia (powtórka)

---

#### **Problem G: Zła logika kosztów**

**Opis:**
- Day 3: Rusinowa Polana ma `cost_estimate=10` przy `ticket_normal=11`
- Logika: cost_estimate powinien być = ticket_normal * group_size

**Oczekiwanie:**
- Dla 2 osób: cost_estimate = 11 * 2 = 22 PLN

**Priorytet:** 🟡 **MEDIUM** - błąd w kalkulacji kosztów

---

## ✅ TEST 07: FRIENDS - ADVENTURE, UNDERGROUND/HISTORY

### Parametry Testu:
```json
{
  "group": {
    "type": "friends",
    "size": 4
  },
  "trip_length": {
    "days": 2
  },
  "preferences": [
    "underground",
    "history",
    "museum"
  ],
  "travel_style": "adventure",
  "budget": {
    "level": 2
  }
}
```

### ✅ CO DZIAŁA SUPER:

#### **Timing bardzo równy**
- To jest plus ✅
- Sporo "muzealno-heritage" w środku dnia ✅

---

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: Za dużo "dziecięcych" atrakcji**

**Opis Day 1:**
- Krokiew → Dom do góry nogami → Muzeum Tatrzańskie → Koliba → Myszogród → Mini Zoo → Podwodny Świat → Jaszczurówka → 3x free_time

**Analiza:**
- Dom do góry nogami, Myszogród, Mini Zoo, Podwodny Świat = typowe "rodzinne ciekawostki"
- Grupa: `friends`
- Travel style: `adventure`
- Preferences: `underground/history/museum`

**Oczekiwanie:**
- Dla friends + adventure: **exclude** family/kids attractions
- Focus na: jaskinie (underground), muzea historyczne, adrenalinę

**Priorytet:** 🔴 **CRITICAL** - target group filtering całkowicie nie działa (powtórka)

---

#### **Problem B: Krokiew jako start mimo braku preferencji**

**Opis:**
- Krokiew wraca jak bumerang w testach
- Brak preferencji: "views / sport / outdoors"

**Analiza:**
> "Wygląda jak:
> - 'globalny must_see override' zbyt wysoko w scoringu,
> - albo 'brak lepszych wyników = wrzucamy Krokiew'."

**Oczekiwanie:**
- Sprawdzić scoring dla Krokwi
- Krokiew powinna być wybierana tylko gdy preferences match (sport/views/adventure)

**Priorytet:** 🔴 **HIGH** - must_see override zbyt silny

---

#### **Problem C: Free_time potrojone na końcu**

**Opis:**
- 3x free_time segmenty na końcu dnia

**Oczekiwanie:**
- Zamiast 3x free_time: dodać 1 sensowną aktywność zamykającą dzień

**Priorytet:** 🟡 **MEDIUM** - UX issue (powtórka)

---

#### **Problem D: Dzień 2 - po Okszy jest "day_end 19:00" bez wypełnienia**

**Opis Day 2:**
- Morskie Oko → lunch → Oksza → koniec
- Brakuje logicznego domknięcia dnia

**Oczekiwanie:**
- Dodać lekką aktywność po Okszy (kawiarnia, spacer, punkt widokowy)

**Priorytet:** 🟡 **MEDIUM** - niepełne wykorzystanie dnia (powtórka)

---

## ✅ TEST 08: COUPLES - 7 DNI

### Parametry Testu:
```json
{
  "group": {
    "type": "couples",
    "size": 2
  },
  "trip_length": {
    "days": 7
  },
  "travel_style": "balanced",
  "budget": {
    "level": 2
  }
}
```

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: Za dużo "family fun" jak na "couples"**

**Opis:**
W planie dla par wracają:
- Dom do góry nogami (dzień 3 i dzień 7) ❌
- Podwodny Świat (dzień 4 i 7) ❌
- Myszogród, Papugarnia, figury woskowe ❌
- Iluzja Park + Illusion House (dzień 6/7) ❌

**Analiza:**
> "Jeśli w danych te atrakcje są wysoko oceniane ogólnie, to może dla couples trzeba dodać mocniejszy filtr/penalty na 'kids-heavy'."

**Oczekiwanie:**
- Dla `couples` grupa: **penalty** na kids-heavy POI
- Preferować: romantyczne miejsca, restauracje, spa, widoki, kultura

**Priorytet:** 🔴 **CRITICAL** - target group filtering nie działa (powtórka masowa)

---

#### **Problem B: W 7-dniowym planie mamy powtórki**

**Opis:**
- Dom do góry nogami (dzień 3, dzień 7) ❌
- Podwodny Świat (dzień 4, dzień 7) ❌
- Kaplica Jaszczurówka (dzień 2, dzień 3) ❌
- Muzea w różnych konfiguracjach - ok, ale też zaczyna się "to samo, tylko inaczej"
- **Termy:** Chochołów, Bukovina, Bania, Zakopiańskie, Gorący Potok = **5 dni z termami w tygodniu** (zdecydowanie za dużo!)

**Oczekiwanie:**
- Cross-day tracking powinien eliminować powtórki POI
- Limit na termy: max 2-3 razy w tygodniu (nie 5!)

**Priorytet:** 🔴 **HIGH** - cross-day uniqueness całkowicie nie działa dla 7-day plan

---

#### **Problem C: Za dużo luk czasowych**

**Przykład: Dzień 1**
- Rusinowa (2,5 h) + lunch + Krokiew (45 min) i koniec dnia o **14:29**
- `day_end` dopiero **20:00**
- **Luka: 14:29-20:00** (5.5 godziny!)

**Oczekiwanie:**
- Wypełnić luki aktywościami

**Priorytet:** 🔴 **HIGH** - harmonogram bardzo niepełny (powtórka masowa)

---

#### **Problem D: Sugestia dodania kolacji**

**Komentarz klientki:**
> "Tak się zastanawiam że jeżeli mamy problem z tym wykorzystaniem dnia szczególnie wieczorami to może dodajmy też kolację? Co o tym myślisz?"

**Analiza:**
- Obecnie plan ma tylko lunch break
- Brak dinner/kolacji jako elementu planu
- To mogłoby wypełnić wieczory (18:00-20:00)

**Oczekiwanie:**
- Dodać `dinner_break` item (18:00-19:30) z rekomendacjami restauracji
- Szczególnie dla preferences `local_food_experience`

**Priorytet:** 🟡 **MEDIUM** - feature request (kolacja jako nowy item type)

---

## ✅ TEST 09: PARA - NATURE + RELAXATION + LOCAL_FOOD

### Parametry Testu:
```json
{
  "group": {
    "type": "couples",
    "size": 2
  },
  "trip_length": {
    "days": 3
  },
  "preferences": [
    "nature",
    "relaxation",
    "local_food"
  ],
  "travel_style": "balanced",
  "budget": {
    "level": 2
  }
}
```

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: W planie brakuje miejsc relaxation (termy/SPA)**

**Opis:**
- Preferencja: `relaxation`
- **Brak:** term/spa w całym planie 3-dniowym

**Oczekiwanie:**
- Dla `relaxation` preference: termy są **must-have**

**Priorytet:** 🔴 **CRITICAL** - kluczowa preferencja całkowicie ignorowana (powtórka masowa)

---

#### **Problem B: Dzień 2 i dzień 3 kończą się za wcześnie**

**Dzień 2:**
- Kościeliska 09:20-12:20
- Lunch 13:12–13:52
- Krokiew 14:12–14:57
- Koniec dnia o **14:57**
- **Luka: 14:57-19:00** (4 godziny!)

**Dzień 3:**
- Rusinowa 09:18-11:48
- Lunch
- Oksza 13:44-14:29
- Koniec o **14:29**
- **Luka: 14:29-19:00** (4.5 godziny - pół dnia wolne!)

**Priorytet:** 🔴 **CRITICAL** - harmonogram bardzo niepełny (powtórka masowa)

---

## ✅ TEST 10: COUPLES - WATER_ATTRACTIONS + BUDGET 200 PLN/DZIEŃ

### Parametry Testu:
```json
{
  "group": {
    "type": "couples",
    "size": 2,
    "daily_limit": 200
  },
  "trip_length": {
    "days": 2
  },
  "preferences": [
    "water_attractions",
    "relaxation",
    "local_food"
  ],
  "travel_style": "relax",
  "budget": {
    "level": 1,
    "daily_limit": 200
  }
}
```

### ❌ CO MUSIMY POPRAWIĆ:

#### **Problem A: Dopasowanie do preferencji water_attractions**

**Opis:**
- Preferencja: `water_attractions`
- **Brakuje:** term/basenów

**Analiza:**
> "To jest numer 1 w Zakopanem przy 'water_attractions + relaxation'."

**Oczekiwanie:**
- Dla `water_attractions`: termy są **must-have** (baseny, aquaparki)

**Priorytet:** 🔴 **CRITICAL** - preferencja water_attractions ignorowana

---

#### **Problem B: Dzień 1 - Rusinowa + lunch i koniec o 18:00**

**Opis:**
- Day 1: Rusinowa + lunch i koniec o 18:00
- To nie do końca jest "water + relax + food"

**Oczekiwanie:**
- Day 1 powinien mieć termy jako główną aktywność

**Priorytet:** 🟡 **MEDIUM** - day composition nietrafiona

---

#### **Problem C: Dzień 2 - budżet 200 PLN przekroczony!**

**Opis Day 2:**
- Krokiew: 25 zł/os = 50 zł
- Mini zoo: 40 zł/os = 80 zł
- Podwodny: 28 zł/os = 56 zł
- Muzeum: 22 zł/os = 44 zł
- Dom do góry nogami: 21 zł/os = 42 zł
- **SUMA: 272 PLN** ❌

**Budget constraint:**
- `daily_limit: 200 PLN`
- **Przekroczenie: 272 - 200 = 72 PLN** (36% over budget!)

**Oczekiwanie:**
- Engine **musi** respektować `daily_limit`
- Hard constraint: suma cost_estimate <= daily_limit

**Priorytet:** 🔴 **CRITICAL** - budget constraint całkowicie ignorowany!

---

#### **Problem D: "Couples + relax" a dobór atrakcji**

**Opis Day 2:**
- Mini zoo, dom do góry nogami, iluzje
- To nie jest klimat "para + relaks"

**Oczekiwanie:**
> "Dla pary przy tym profilu powinno być:
> - termy / strefa saun,
> - spokojna kolacja (albo chociaż rekomendacja),
> - spacer widokowy z łatwym dojściem,
> - a nie do końca 'zaliczanie atrakcji po 20–30 minut'."

**Priorytet:** 🔴 **HIGH** - target group + travel style ignorowane (powtórka masowa)

---

## 📊 PODSUMOWANIE WSZYSTKICH TESTÓW (01-10):

### 🔥 KRYTYCZNE PROBLEMY (Muszą być naprawione):

#### **1. Preferencje użytkownika są całkowicie lub częściowo ignorowane** 🔴 CRITICAL
**Dotknięte testy:** 01, 02, 03, 04, 05, 06, 09, 10
**Preferencje ignorowane:**
- `kids_attractions` (Test 01, 05)
- `relaxation` (Test 02, 05, 06, 09, 10) - **brak term/spa**
- `local_food_experience` (Test 02) - **brak kolacji/degustacji**
- `active_sport` (Test 03) - **brak sportu**
- `history_mystery` (Test 03, 04) - traktowane jak zwykłe `history`
- `water_attractions` (Test 10) - **brak basenów/term**

**Root cause:**
- Scoring module nie daje wystarczającego bonusu za preferences match
- Preferences powinny być **hard filter** lub bardzo silny scoring boost

**Jak naprawić:**
1. W `engine.py` funkcja `score_poi()`: dodać **+20-30 punktów** za preferences match
2. Dla kluczowych preferences (relaxation, kids_attractions, water_attractions): **ensure at least 1-2 POI** w planie

---

#### **2. Target group filtering nie działa** 🔴 CRITICAL
**Dotknięte testy:** 02, 03, 04, 05, 07, 08, 10
**Problem:**
- Dla `couples` wracają family/kids POI (Dom do góry nogami, Mini Zoo, Podwodny Świat, Myszogród)
- Dla `friends + adventure` wracają family/kids POI
- Dla `solo` wracają family/kids POI

**Obecny mechanizm:**
- `should_exclude_by_target_group()` jest w kodzie (Cortex context)
- Ale prawdopodobnie **nie jest używany** lub jest zbyt słaby

**Jak naprawić:**
1. W `engine.py` przed dodaniem POI do planu: wywołać `should_exclude_by_target_group()`
2. Jeśli returns `True` → **EXCLUDE** POI z candidates
3. Dla `couples`: dodać **penalty -20 punktów** na POI z `kids_only: true`

---

#### **3. Crowd_tolerance całkowicie ignorowane** 🔴 CRITICAL
**Dotknięte testy:** 02, 04, 05, 06
**Problem:**
- `crowd_tolerance: 1` (niska tolerancja)
- Plan zawiera topowe magnesy tłumów: Morskie Oko, Krupówki, Wielka Krokiew

**Jak naprawić:**
1. W `score_poi()`: dla POI z `popularity: high` + `crowd_tolerance: 0-1`:
   - **Penalty -15 punktów**
2. W `explainability.py`: dodać warning w `pro_tip`:
   - "Popularne miejsce - jedź wcześnie rano (przed 9:00) lub poza weekendem"

---

#### **4. Harmonogram dnia niepoprawny - ogromne luki czasowe** 🔴 CRITICAL
**Dotknięte testy:** 03, 06, 07, 08, 09
**Problem:**
- Po głównej atrakcji zostaje 3-5 godzin pustki do `day_end`
- Przykład: dzień kończy się o 14:30, a `day_end` jest o 19:00 (4.5h luki)

**Jak naprawić:**
1. W `build_day()` w engine.py: po każdej atrakcji sprawdzić:
   - `if (day_end - current_time) > 180 min` (3h)
   - → dodać lekką aktywność (muzeum 45min, spacer, punkt widokowy)
2. Nie generować wielokrotnych `free_time` segmentów
3. Logicznie domykać dzień ostatnią aktywnością

---

#### **5. Budget constraint ignorowany** 🔴 CRITICAL
**Dotknięty test:** 10
**Problem:**
- `daily_limit: 200 PLN`
- Day 2 suma kosztów: **272 PLN** (36% over budget!)

**Jak naprawić:**
1. W `build_day()`: track `daily_cost_so_far`
2. Przed dodaniem POI: `if daily_cost_so_far + poi.cost_estimate > daily_limit`: **skip POI**
3. Hard constraint: suma cost_estimate <= daily_limit

---

#### **6. Cross-day uniqueness nie działa dla 7-day plans** 🔴 HIGH
**Dotknięty test:** 08
**Problem:**
- Dom do góry nogami (dzień 3, dzień 7)
- Podwodny Świat (dzień 4, dzień 7)
- Kaplica Jaszczurówka (dzień 2, dzień 3)
- **5 dni z termami w 7-dniowym planie!**

**Jak naprawić:**
1. Cross-day tracking już istnieje (Day 13-14 bugfix)
2. Problem: może nie działa dla 7+ dni
3. Dodać limit na termy: **max 2-3 razy** w planie wielodniowym
4. Sprawdzić czy `global_used` set jest poprawnie przekazywany przez wszystkie dni

---

### 🟡 WAŻNE PROBLEMY (Powinny być naprawione):

#### **7. why_selected jest szablonowe** 🟡 MEDIUM
**Dotknięte testy:** 02, 05
**Problem:**
- Wszystko ma "Perfect for couples seeking romantic experiences"
- Nawet Dom do góry nogami, Mini Zoo

**Jak naprawić:**
- W `explainability.py`: `why_selected` powinno być dynamiczne:
  * Match z user preferences
  * Match z travel style
  * Match z POI actual characteristics
  * Nie generyczne szablony

---

#### **8. cost_estimate błędny** 🟡 MEDIUM
**Dotknięty test:** 06
**Problem:**
- `cost_estimate: 10` przy `ticket_normal: 11` dla 2 osób
- Powinno być: 11 * 2 = 22 PLN

**Jak naprawić:**
- W funkcji wyliczającej `cost_estimate`: `ticket_normal * group_size`

---

#### **9. Parking references niespójne** 🟡 MEDIUM
**Dotknięty test:** 03
**Problem:**
- Muzeum ma parking "Krupówki 20", ale item parking to "Parking miejski" pod Krokwią

**Jak naprawić:**
- Reużyć ten sam parking logicznie z dojazdem pieszo
- Lub generować nowy parking item przed każdą główną atrakcją

---

#### **10. Must_see override zbyt silny (Krokiew wraca jak bumerang)** 🟡 HIGH
**Dotknięte testy:** 03, 06, 07, 08, 09
**Problem:**
- Wielka Krokiew pojawia się w prawie każdym planie
- Nawet gdy brak preferencji "views / sport / outdoors"

**Jak naprawić:**
- Sprawdzić scoring dla Krokwi
- Krokiew powinna być wybierana tylko gdy preferences match
- Zmniejszyć bonus za `must_see` badge (obecnie może być za wysoki)

---

### 🆕 FEATURE REQUESTS:

#### **11. Dodanie kolacji (dinner_break)** 🟡 MEDIUM
**Źródło:** Test 08, feedback klientki
**Opis:**
> "Jeżeli mamy problem z tym wykorzystaniem dnia szczególnie wieczorami to może dodajmy też kolację?"

**Implementacja:**
1. Nowy item type: `dinner_break`
2. Timeframe: 18:00-20:00 (jeśli jest jeszcze czas w dniu)
3. Szczególnie dla preferences `local_food_experience`
4. Suggestions: restauracje regionalne, bacówki, degustacje

---

#### **12. Rozszerzenie bazy POI o Małopolskę** 🟡 MEDIUM
**Źródło:** Test 03, feedback klientki
**Opis:**
> "Możemy w sobotę podpiąć np. całą bazę atrakcji z Małopolski i zrobić testy na innych miastach np. Krakowie?"

**Plan:**
- Sobota: rozszerzyć Excel o POI z całej Małopolski
- Testy w Krakowie zamiast Zakopanego
- Sprawdzić czy `history_mystery` działa lepiej z szerszą bazą

---

## 🎯 PLAN NAPRAWY (Priority Order):

### **ETAP 1: KRYTYCZNE BUGS (Must-fix przed production)**

1. **Preferences filtering** 🔴 CRITICAL
   - File: `app/domain/planner/engine.py`
   - Function: `score_poi()`
   - Add: +20-30 punktów za preferences match
   - Ensure: min 1-2 POI per preference w planie

2. **Target group filtering** 🔴 CRITICAL
   - File: `app/domain/planner/engine.py`
   - Function: `build_day()` (przed dodaniem POI)
   - Use existing: `should_exclude_by_target_group()`
   - For couples: penalty -20 na kids_only POI

3. **Crowd_tolerance enforcement** 🔴 CRITICAL
   - File: `app/domain/scoring/*.py` lub `engine.py`
   - For popularity: high + crowd_tolerance: 0-1 → penalty -15
   - File: `app/domain/planner/explainability.py`
   - Add warnings w `pro_tip`

4. **Harmonogram - wypełnianie luk** 🔴 CRITICAL
   - File: `app/domain/planner/engine.py`
   - Function: `build_day()`
   - If luka > 180 min → dodaj lekką aktywność
   - Nie generować wielokrotnych free_time

5. **Budget constraint** 🔴 CRITICAL
   - File: `app/domain/planner/engine.py`
   - Function: `build_day()`
   - Track: `daily_cost_so_far`
   - If cost > daily_limit → skip POI

6. **Cross-day uniqueness dla 7+ dni** 🔴 HIGH
   - File: `app/domain/planner/engine.py`
   - Function: `plan_multiple_days()`
   - Verify: `global_used` set działa przez wszystkie dni
   - Add limit: max 2-3 termy w tygodniu

---

### **ETAP 2: WAŻNE IMPROVEMENTS (Should-fix)**

7. **why_selected dynamiczne** 🟡 MEDIUM
   - File: `app/domain/planner/explainability.py`
   - Match z preferences + style + POI characteristics

8. **cost_estimate fix** 🟡 MEDIUM
   - File: kalkulacja kosztów
   - Formula: `ticket_normal * group_size`

9. **Parking logic** 🟡 MEDIUM
   - Reużyć parking lub generować nowy

10. **Must_see override tuning** 🟡 HIGH
    - Zmniejszyć bonus za must_see badge
    - Krokiew tylko gdy preferences match

---

### **ETAP 3: FEATURE REQUESTS (Nice-to-have)**

11. **Dinner_break** 🟡 MEDIUM
    - Nowy item type
    - Timeframe 18:00-20:00

12. **Baza POI Małopolska** 🟡 MEDIUM
    - Rozszerzyć Excel
    - Testy w Krakowie

---

## 📝 ZASADY IMPLEMENTACJI:

✅ **Backward compatibility:**
- Wszystkie 12 problemów z Day 13-14 muszą nadal działać
- Zero regressions

✅ **Testing strategy:**
- Po każdej zmianie: uruchomić 11 test files (z Day 13-14)
- Testy UAT: wygenerować plany dla 10 scenariuszy ponownie
- Porównać przed/po

✅ **Code quality:**
- Unikać duplikacji kodu
- Trzymać się obecnej struktury (engine.py, scoring/, explainability.py)
- Dokumentacja w commit messages

✅ **Documentation:**
- Update [ETAP2_PLAN_DZIALANIA.md](ETAP2_PLAN_DZIALANIA.md) po implementacji
- Create: `BUGFIX_UAT_18_02_2026.md` z detalami fixów

---

**Last Updated:** 18.02.2026  
**Author:** Mateusz Zurowski (based on Karolina's complete UAT feedback)  
**Status:** 🔴 **READY TO IMPLEMENT** - wszystkie 10 testów zanotowane, prioritization complete
