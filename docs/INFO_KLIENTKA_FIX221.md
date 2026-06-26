# FIX #221 — feedback klientki (20.06.2026)

Testy: Poznań, Kraków, Katowice, Warszawa po FIX #219/#220.

## Cel

Poprawa **balansu czasu i preferencji** bez regresji routingu (ORS geometry) i bez szerokiego Overpass. Excel POI pozostaje priorytetem; mapa tylko przy dużym `free_time` lub wyczerpaniu puli.

---

## Zmiany

### 1. Free Time (Poznań, Kraków, Katowice, Warszawa)

| Problem | Rozwiązanie |
|---------|-------------|
| Bloki 120–300 min | Cap konsolidacji: **90 min** (miasta), 180 domyślnie, 300 Zakopane |
| Agresywne merge wieczornych bloków | Wyłączony `_aggressive_merge` gdy cap ≤ 90 |
| Za mało gap-fill | Próg top-up: **45 min** (urban), do **5** przebiegów na 5+ dni |
| Dodatkowe pętle gap-fill | Break przy FT ≤ **60 min** (było 90) |

### 2. Overpass / mapa (FIX #220 → #221)

- **Przed:** supplement przed gap-fill przy „sparse day”.
- **Teraz:** supplement **po** gap-fill, tylko gdy:
  - `free_time ≥ 180 min`, lub
  - `free_time ≥ 120 min` i `< 4` atrakcje, lub
  - `0` atrakcji i `free_time ≥ 90 min`, lub
  - flaga `duplication_gap`.

### 3. Powtórzenia POI (Warszawa 7 dni)

- Klaster Warszawa: PKiN, Wilanów, Muzeum Wódki, Taras św. Anny, MSN.
- FIX #219 reopen POI: tylko pule **< 45** POI (duże miasta bez powtórzeń).
- `cross_day_reuse`: tylko gdy `< 2` atrakcje **i** `free_time ≥ 180 min`.

### 4. Micro-POI / niszowe muzea

- Quick-stop: parafie Katowice (św. Anna, św. Michał).
- Penalty scoring: Okrąglak, Domy Kupieckie, Most Świętokrzyski, Pomnik Syreny.
- Niszowe muzea: Geologiczne, Be Happy, Lustrzany Labirynt, Obwarzanki — niższa pozycja, szczególnie dni 1–3.
- Dzień 1: quick-stop **-80** (nie zaczynać od Mostu Świętokrzyskiego itd.).

### 5. Balans preferencji (per dzień)

- `day_preference_counts` — licznik trafień pref w danym dniu.
- Seniors: natura nie dominuje kosztem `museum_heritage`.
- Family + nature + kids: równoważenie kids vs natura.
- Museum vs nature vs relaxation: kara gdy jedna kategoria ≥ 2× bez drugiej.

### 6. Family kids

- Dzień 1: **+55** kids POI, **-40** muzea historyczne.
- Deny: Parafia św. Anny, Kościół św. Michała (Katowice).

### 7. Adventure / Relax

- Friends + adventure (miasto): **+75** escape room, VR, trampoliny, paintball.
- Relax w mieście: limit POI **-1** zamiast **-2** hard (więcej realnych atrakcji, mniej FT).
- 5+ dni miasto: soft **6**, hard **7** atrakcji/dzień.

### 8. Coverage / komunikaty

- Rogalin **nie** liczy się jako `relaxation`.
- Dzień 5 (6+ dni): warning + tytuł „propozycja wycieczki poza miasto”.

---

## Pliki

- `app/application/services/plan_service.py`
- `app/domain/planner/engine.py`
- `app/domain/scoring/preference_coverage.py`
- `app/domain/scoring/family_fit.py`
- `app/infrastructure/routing/poi_supplement.py`
- `tests/test_fix221_client_feedback.py`
- `tests/test_fix220_routing.py` (zaktualizowany trigger)

## Testy

```bash
pytest tests/test_fix221_client_feedback.py tests/test_fix220_routing.py --no-cov
# 24 passed
```

## Bez regresji

- ORS Directions / geometry / matrix — bez zmian.
- Excel POI — pierwszeństwo zachowane.
- FIX #218–#220 — routing i dedup tras nietknięte.

## Do retestu klientki

1. Poznań 7 dni — FT, balans museum/nature/relax, Rogalin coverage, dzień 5 info.
2. Kraków — ikony przed niszowymi muzeami, family_kids dzień 1, mniej FT.
3. Katowice — brak parafii dla family, mniej „kolejnego parku”, FT < 90 min.
4. Warszawa 7 dni — brak powtórzeń PKiN/Wilanów, micro-POI niżej, adventure friends.
