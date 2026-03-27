# ODPOWIEDŹ DO KLIENTKI - COLD START PROBLEM

**Data:** 03.03.2026

---

## EMAIL/WIADOMOŚĆ DO KAROLINY

---

Hej!

Sprawdziłem - backend **działa poprawnie**. To co widzisz na screenshocie to normalny **cold start** na Render free tier.

### **Co się dzieje:**

Render free tier uśypia serwer po ~15 minutach bez użycia. Pierwsze request po przebudzeniu trwa **30-60 sekund** (to co widzisz: "WAKING UP", "ALLOCATING RESOURCES" itp.). Następne requesty działają instant.

### **Problem:**

Frontend prawdopodobnie ma **za krótki timeout** (np. 10 sekund) i wyrzuca błąd "nie mogę się połączyć" zanim API się w pełni obudzi.

### **Rozwiązanie (dla frontendu):**

**1. Zwiększyć timeout do 90 sekund:**
```javascript
// W axios/fetch config:
timeout: 90000  // 90 sekund (daje czas na cold start)
```

**2. Dodać komunikat dla usera:**
```
"Przygotowuję plan (może zająć do 60 sekund)..."
```

Przepuść to do frontu - to po jego stronie fix. Backend działa OK, tylko trzeba dać mu czas na przebudzenie.

### **Opcje długoterminowe:**

**Przed startem MVP:** Warto zrobić upgrade Render do $7/miesiąc - wtedy **zero cold starts**, serwer zawsze online. To standard dla produkcji.

### **Mogę pomóc:**

Jeśli frontend nie wie jak to zrobić - mogę podać dokładny kod (muszę wiedzieć czego używają: axios? fetch?).

Albo mogę dodać endpoint `/ping` żeby frontend pingował API co 10 minut w tle (wtedy nie zaśnie). Ale to zużyje free hours na Render.

Daj znać co wolisz!

**Pozdrawiam,**  
Mateusz

---

**TL;DR:** Backend OK. Frontend: zwiększyć timeout do 90 sek + pokazać "Loading...". Cold start to normalne na Render free tier.
