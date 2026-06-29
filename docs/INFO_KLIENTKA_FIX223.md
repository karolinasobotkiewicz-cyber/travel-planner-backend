## FIX #223 (29.06.2026) — feedback klientki round 2 (Wrocław)

Kontynuacja FIX #222. Większość problemów to dopracowanie rzeczy, które #222
adresował, ale część była niekompletna lub miała genuine bugi.

> Uwaga wdrożeniowa: część poprawek z FIX #222 (m.in. sezonowy filtr pontonów,
> budżet w gap-fill) trafiła do repo dopiero w commicie `ac1782d`. Jeśli testy
> klientki były robione przed redeployem Render, te problemy mogły jeszcze
> występować mimo poprawnego kodu. **Po pushu FIX #223 → Manual Deploy.**

---

## Zmiany

### 1. Micro-POI / ranking (Browar Stu Mostów, mosty, Hala Targowa, City Golf)

**Root cause:** te POI mają wysoki `Must see score` / `popularity_score` w Excelu
(np. Browar Stu Mostów `must=8`, Most Tumski `pop=10`), więc mimo flagi quick-stop
dostawały duży „iconic boost”.

- `score_poi`: dla quick-stopów **kasujemy must_see** (cap do 4) → tracą iconic boost.
- `_UNIVERSAL_FILLER_NAME_MARKERS`: dodatkowy **-70** dla Browar Stu Mostów
  (klientka: „uniwersalne wypełnienie planu, niezależnie od profilu”).
- Most Tumski / Most Pokoju potwierdzone jako quick-stop (łapane przez prefix `"most "`).

**Weryfikacja (Wrocław luty, family_kids):** Browar Stu Mostów score `-115…-157`,
wypadł z planu (swap na Ogród Botaniczny).

### 2. Hala Stulecia — naprawiony regres z #222

FIX #222 omyłkowo wrzucił `hala stulecia` na listę hard quick-stop, mimo że to
flagowy obiekt UNESCO (`must=9`) i kotwica klastra Szczytnickiego, który klientka
chce trzymać razem. **Usunięte z listy.**

### 3. Sezonowość — Spływy pontonowe Złotniki w lutym

Filtr nazw zimowych (ponton/spływ/złotniki) już działa (FIX #222). Potwierdzone
testem E2E: w planie lutowym brak Spływów Złotniki. (Jeśli klientka nadal widzi —
to brak redeployu Render.)

### 4. Dinner na kilka minut

`_enforce_dinner_before_day_end`: gdy kolacja po docięciu do `day_end` < **30 min**,
**usuwamy ją** zamiast tworzyć „kolację na 8 minut”.

### 5. Coverage — złe dopasowania

- **Katedra** ≠ `relaxation`, `local_food_experience`, `water_attractions`
  (profil water + food + relax).
- Mosty/kładki ≠ `local_food_experience`.

### 6. ZOO przy profilu underground + history_mystery

Kara za ZOO (poza family_kids) rozszerzona o `underground` i wzmocniona do **-110**.

### 7. Styl relax ≠ wielogodzinny Free Time + solo + relax + nature → za dużo muzeów

- `travel_style relax`: **+55** dla realnych POI relaks/natura (parki, spa, ogrody),
  żeby dzień wypełniały atrakcje, nie puste bloki.
- Profil nature/relax (lub styl relax): kara dla muzeów gdy dzień ma już muzeum
  (**-80**) lub trip ma ≥2 muzea (**-45**).

### 8. Rozkład preferencji (stabilność)

Off-profile POI gdy dnia wciąż brakuje preferencji: kara **-110** (miasto) / -85.
Spread boost podniesiony (110 + dzień×14, top-2 pref +40). Uwaga: dla kombinacji
gdzie pula POI jest mała (np. nature+relax we Wrocławiu) część dni nadal może mieć
mniej dopasowanych atrakcji — to ograniczenie danych, nie logiki.

### 9. Budżet — Bungee dla active_sport

Bungee `tn=249/os.` → dla grupy ~498 zł potrafiło zmieścić się pod limit 500.
Dodana kara **-120** dla pojedynczego POI kosztującego > **55%** dziennego limitu
(jeśli nie flagowy must_see≥8). Twarde filtry budżetu (core + gap-fill) bez zmian.

---

## Pliki

| Plik | Zmiana |
|------|--------|
| `app/domain/planner/engine.py` | must_see cap quick-stop, filler penalty, zoo, relax/museum cap, budget dominance, hala stulecia |
| `app/application/services/plan_service.py` | dinner < 30 min → drop |
| `app/domain/scoring/preference_coverage.py` | katedra/mosty denies |
| `tests/test_fix223_client_feedback.py` | unit tests |

---

## Test plan (retest klientki — Wrocław)

1. **Browar Stu Mostów** — nie pojawia się jako pełnoprawny punkt (różne profile).
2. **Mosty / Hala Targowa / City Golf / Grabowy** — niżej, rzadko jako główny punkt.
3. **Hala Stulecia** — nadal obecna (flagowiec, klaster Szczytnicki).
4. **Luty** — brak Spływów Złotniki.
5. **water + food + relax** — brak Katedry jako realizacji tych preferencji.
6. **underground + history_mystery** — brak ZOO.
7. **Kolacje** — żadna < 30 min.
8. **active_sport + budżet 500** — brak Bungee dominującego budżet.
9. **relax** — dzień wypełniony parkami/spa, nie wielogodzinnym Free Time.
