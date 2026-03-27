# WYCENA - ETAP 3

**Data:** 02.03.2026  
**Dla:** Karolina Sobotkiewicz  
**Przygotował:** Mateusz (Backend Developer)

---

## CO WYCENIAM

To jest etap przygotowania systemu przed wypuszczeniem do użytkowników. Nie dodajemy tu jeszcze 25-30 miast (to będzie później), tylko robimy infrastrukturę żeby system był gotowy na nie.

---

## ZAKRES PRAC

### **1. DESTINATIONS ENDPOINT + INFRASTRUKTURA**

**Co robię:**
- Nowy endpoint GET /destinations - zwraca listę wszystkich miast dostępnych w systemie
- Każde miasto ma: nazwę, slug, kraj, typ regionu, ikonę, koordynaty, czy aktywne
- Plus opcjonalnie ile ma POI i jakiś obrazek
- Przygotowanie systemu żeby ogarnął 25-30 miast (teraz mamy tylko Zakopane)
- Stabilne filtrowanie - żeby frontend mógł pytać "daj mi tylko góry" albo "daj mi tylko miasta"
- Fallbacki - jak jest mało POI to system nie wywala błędu tylko robi sensowny plan z tego co ma

**Ile czasu:** 3-4 dni
- Dzień 1: Endpoint + model danych
- Dzień 2: Logika filtrowania + testy
- Dzień 3: Fallbacki przy małej bazie POI
- Dzień 4: Testy + optymalizacja

**Dlaczego aż 4 dni:**
Fallbacki to nie jest proste "if poi < 10 then error". Trzeba ogarnąć:
- Co jeśli user chce 5 dni ale miasto ma POI na 2 dni?
- Co jeśli wszystkie POI są premium (ponad budget)?
- Co jeśli user wyłączył wszystkie kategorie preferowanych POI?
To musi działać sensownie, nie crashować i dawać userowi jakąś wartość.

---

### **2. PREVIEW / PAYWALL**

**Co robię:**
- Backend generuje CAŁY plan (pełne 5 dni czy ile tam user chciał)
- Zapisuje go w bazie normalnie
- Ale API zwraca tylko połowę pierwszego dnia jak user nie zapłacił
- Po płatności - zwraca full plan
- Nowe pola w odpowiedzi: access_level (preview albo full), payment_status, entitlements
- Update endpointu GET /plan/{id}/status żeby pokazywał czy user ma dostęp czy nie

**Ile czasu:** 2-3 dni
- Dzień 1: Logika preview vs full w API
- Dzień 2: Pola access_level, payment_status, entitlements
- Dzień 3: Testy + integracja z Stripe (sprawdzanie czy zapłacono)

**Dlaczego aż 3 dni:**
To nie jest tylko "zwróć połowę danych". Trzeba:
- Ogarnąć który plan pokazać (bo można mieć kilka planów)
- Sprawdzić payment_status w Stripe
- Obsłużyć przypadki gdy user ma kilka sesji płatności
- Zabezpieczyć żeby user nie obchodził paywall

---

### **3. QUALITY & SAFETY**

**Co robię:**
- System sprawdza czy wygenerowany plan ma sens:
  - Czy nie ma za dużo free_time (dziury w planie)
  - Czy są core POI (Morskie Oko w Zakopanem itp)
  - Czy atrakcje są otwarte (nie dajemy muzeum jak jest zamknięte)
- Edge cases - co jak miasto ma 5 POI a user chce 3 dni?
- Statusy generowania:
  - pending - plan się generuje
  - ready - gotowe
  - failed - coś poszło nie tak
  - payment_required - wygenerowane ale trzeba zapłacić żeby zobaczyć
- Warnings - ostrzeżenia typu "plan ma mało POI", "niektóre atrakcje mogą być zamknięte"
- Fail_reason - dlaczego nie udało się wygenerować
- Logging - żeby Karolina widziała w Render/Supabase co się dzieje jak coś nie działa

**Ile czasu:** 4-5 dni
- Dzień 1: Quality checks (free_time, core POI, opening hours)
- Dzień 2: Edge cases handling
- Dzień 3-4: Statusy + warnings + fail_reason
- Dzień 5: Logging (structured logs w Render)

**Dlaczego aż 5 dni:**
Quality checks to dużo logiki:
- Opening hours - trzeba sprawdzić każdy POI czy dziś ma otwarte
- Core POI - trzeba oznaczyć które są "core" dla danego miasta
- Free_time - trzeba policzyć ile czasu zostaje między atrakcjami
- Edge cases - dużo scenariuszy do ogarnięcia i przetestowania
- Logging - żeby było sensowne a nie spam

---

### **4. RESTAURACJE + SZLAKI (w cenie)**

**Co robię:**
- Restauracje:
  - Dodać typ POI "restaurant"
  - Logika: obiad 12-13:30 już mamy, ale można dodać kolacje/śniadania
  - Filtrowanie po typie kuchni, cenie
  - Integracja w plan (żeby nie dawało 3 restauracji pod rząd)

- Szlaki górskie:
  - Dodać typ POI "hiking_trail"
  - Czas trwania (szlaki mogą być 2-6h)
  - Trudność (łatwy/średni/trudny)
  - Warunki pogodowe (może być zamknięty zimą)

**Ile czasu:** 3-4 dni (razem oba)
- Dzień 1-2: Restauracje (model + logika)
- Dzień 3-4: Szlaki górskie (model + logika)

**Dlaczego w pakiecie:**
Restauracje to podstawa - ludzie pytają "gdzie zjeść".
Szlaki - w Zakopanem to must-have (Morskie Oko to szlak w sumie).
Lepiej mieć to od razu na starcie niż dokładać później.

---

### **5. BONUS 1 - EKSPORT DO PDF (w cenie)**

**Co robię:**
- User może pobrać cały plan jako elegancki PDF
- PDF zawiera: pełny harmonogram, mapę, szczegóły każdego POI (godziny, ceny, GPS)
- Profesjonalny layout z logo, dni podzielone sekcjami, czytelna typografia
- Praktyczne info do wydruku - user zabiera w podróż i ma wszystko pod ręką
- Opcjonalnie: QR kod z linkiem do online version

**Ile czasu:** 2 dni
- Dzień 1: Integracja z PDF library (ReportLab/WeasyPrint) + podstawowy template
- Dzień 2: Formatowanie, testy, optymalizacja (żeby PDF szybko się generował)

**Dlaczego bonus:**
Każdy porządny travel planner powinien mieć PDF export. Users chcą mieć plan offline, wydrukować przed wyjazdem, pokazać współpasażerom. To wygląda profesjonalnie i daje praktyczną wartość.

**Wartość:** Normalnie 800 PLN (PDF generation to oddzielna funkcjonalność), teraz wliczone.

---

### **6. BONUS 2 - EMAIL NOTIFICATIONS (w cenie)**

**Co robię:**
- User dostaje email gdy jego plan jest gotowy do pobrania
- Email po pomyślnej płatności (potwierdzenie)
- Email jak generowanie się nie udało (z info dlaczego)
- Proste, czytelne emaile (nie spam)

**Ile czasu:** 1-2 dni
- Dzień 1: Integracja z email service (np. SendGrid/AWS SES)
- Dzień 2: Templates + testy

**Dlaczego bonus:**
Lepsze UX - user nie musi odświeżać strony co 5 sekund żeby sprawdzić czy plan gotowy. Dostaje email i wraca jak ma czas.

**Wartość:** Normalnie 800 PLN (email system to oddzielna integracja), teraz wliczone.

---

## PODSUMOWANIE CZASU

### **ZAKRES KOMPLETNY:**
- Destinations + infrastruktura: 3-4 dni
- Preview/Paywall: 2-3 dni
- Quality & Safety: 4-5 dni
- Restauracje + Szlaki: 3-4 dni
- BONUS 1 - Eksport do PDF: 2 dni
- BONUS 2 - Email notifications: 1-2 dni

**TOTAL: 15-20 dni roboczych**

---

## WYCENA

**Stawka:** 400 PLN/dzień (tak jak ETAP 1 i 2)

### **PAKIET KOMPLETNY - MVP READY: 8000 PLN**

**Normalnie osobno:**
- Destinations + infrastruktura: 4 dni × 400 = 1600 PLN
- Preview/Paywall: 3 dni × 400 = 1200 PLN
- Quality & Safety: 5 dni × 400 = 2000 PLN
- Restauracje + Szlaki: 4 dni × 400 = 1600 PLN
- BONUS 1 (Eksport do PDF): 2 dni × 400 = 800 PLN
- BONUS 2 (Email notifications): 2 dni × 400 = 800 PLN

**RAZEM normalnie: 8000 PLN**

### **CENA PAKIETOWA: 8000 PLN**

To nie rabat - to uczciwa cena za pakiet "all-inclusive" przed startem MVP. Dostajesz wszystko co potrzebujesz w jednej cenie, bez ukrytych kosztów i bez "a to extra", "a tamto extra".

---

## DLACZEGO TO DOBRA CENA?

**Co dostajesz za 8000 PLN:**

1. **Destinations endpoint** - lista wszystkich miast z pełnymi danymi
2. **Infrastruktura pod 25-30 miast** - stabilna, szybka, nie crashuje
3. **Preview/Paywall** - user widzi tylko połowę 1 dnia przed płatnością (bo tu się kręci kasa)
4. **Quality & Safety** - checks, statusy, warnings, logging (żeby widzieć co się psuje)
5. **Restauracje** - pełna obsługa (śniadania, obiady, kolacje)
6. **Szlaki górskie** - czas, trudność, warunki pogodowe
7. **BONUS 1:** Eksport do PDF (wydruk planu, praktyczne offline)
8. **BONUS 2:** Email notifications (plan gotowy, płatność OK, błędy)

**To znaczy:**
- Wszystko gotowe do startu publicznego
- Nie musisz dokładać później "a mogę jeszcze to", "a mogę jeszcze tamto"
- Jedna cena, wszystko załatwione
- MVP kompletne

**Alternatywa (robienie osobno):**
- Teraz: podstawa za 4800 PLN
- Za miesiąc: "a mogę restauracje?" → +1600 PLN
- Za 2 miesiące: "a mogę PDF export?" → +800 PLN  
- Za 3 miesiące: "a mogę email notifications?" → +800 PLN
- **RAZEM: 8000 PLN + 3 osobne zamówienia + 3 osobne deployments**

**Z pakietem:**
- Teraz: 8000 PLN za wszystko
- 1 zamówienie, 1 deployment
- MVP kompletne w 15-17 dni
- Wszystko spójne i przetestowane razem
- Nie tracisz czasu na osobne wyceny później

---

## TIMELINE

**Start:** Jak skończysz frontend i będzie gotowe do pełnych testów (Ty decydujesz kiedy)

**Delivery:** ~15-17 dni roboczych od startu (w praktyce 2.5-3 tygodnie)

**Płatność:** 8000 PLN - po zakończeniu i akceptacji (tak jak ETAP 1 i 2)

---

## CO DOSTAJESZ - SZYBKIE PODSUMOWANIE

**Za 8000 PLN:**
1. ✅ Destinations endpoint (GET /destinations)
2. ✅ Infrastruktura pod 25-30 miast
3. ✅ Preview/Paywall (połowa 1 dnia przed płatnością)
4. ✅ Quality & Safety (checks + statusy + warnings + logging)
5. ✅ Restauracje (śniadania, obiady, kolacje)
6. ✅ Szlaki górskie (czas, trudność, pogoda)
7. ✅ BONUS: Eksport do PDF
8. ✅ BONUS: Email notifications

**Czas:** 15-17 dni roboczych (2.5-3 tygodnie)

**Płatność:** Po zakończeniu, tak jak ETAP 1 i 2

---

## CO NIE JEST WLICZONE

**Dodawanie konkretnych miast (Kraków, Warszawa, etc.):**
- To będzie osobny zakres PÓŹNIEJ (po starcie MVP)
- Research POI robisz Ty sama (znasz polski rynek lepiej niż ja)
- Ja dostaję gotową listę POI od Ciebie (nazwa, adres, godziny, cena, kategoria)
- Dodaję do bazy + testy: ~0.5-1 dzień × miasto
- Wycena: ~300-400 PLN/miasto (tylko implementacja, bez researchu)

**Przykład:**
- 5 miast (Kraków, Warszawa, Gdańsk, Wrocław, Poznań) = ~1500-2000 PLN
- Ty zbierasz POI (znasz rynek, masz wizję), ja wrzucam do systemu i testuję
- To zrobimy jak zobaczysz które miasta users najbardziej chcą

---

## PYTANIA?

Jeśli coś niejasne albo chcesz zmienić zakres - daj znać, ogadamy.

---

**Pozdrawiam,**  
Mateusz

---

**Data:** 02.03.2026  
**Status:** Wycena wstępna - czeka na decision
