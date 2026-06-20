# Odpowiedź — FIX #209 (Kotlina Kłodzka)

Dziękujemy za szczegółowy feedback dotyczący Kudowy-Zdroju, Polanicy-Zdroju i Kotliny Kłodzkiej. Poniżej co zostało naprawione w tej rundzie.

## Co poprawiliśmy

### Puste dni przy rodzinach z dziećmi
Planner odrzucał większość atrakcji, bo w Excelu tylko kilka miało wpisane `family_kids`. Teraz rodzinom pokazujemy też atrakcje oznaczone jako `friends` / `couples` (bez profili typowo seniorskich). Dla Kotliny, gdy w jednym uzdrowisku jest mało punktów, planer automatycznie korzysta z puli całego regionu (Kłodzko + Polanica + Kudowa), trzymając pierwsze dni w wybranym mieście bazowym.

### Sezonowość (Góralka w lutym)
Letni tor saneczkowy Góralka nie powinien już pojawiać się w planach zimowych. Naprawiliśmy mapowanie sezonowości z Excela oraz filtrowanie w silniku i przy wypełnianiu luk.

### Local Food Experience
Dodaliśmy obsługę tagów kulinarnych (sery, wędzarnie, rzemiosło) i boost dla m.in. **Sery Lutomierskie** i **Złoty Pstrąg** przy preferencji `local_food_experience`. Dzięki rozszerzeniu puli na całą Kotlinę te POI mogą trafić do planu.

### Relaxation zamiast samego free_time
Dla regionu uzdrowiskowego planner częściej wybiera pijalnie wód, parki zdrojowe i parki wodne zamiast pustych bloków relaksu.

### Mikro-atrakcje (Most św. Jana, Brama Wodna, Plac Chrobrego…)
Traktujemy je jako krótkie postoje fotograficzne, nie pełnoprawne atrakcje dnia.

### Kopalnia Złota a nature_landscape
Kopalnia nie powinna już być liczona jako realizacja kategorii przyrody.

### Powtórki muzeów / historii
Przy dłuższych pobytach z `museum_heritage` + `history_mystery` wprowadziliśmy silniejszą karę za kolejne muzea po 2–3 już zaplanowanych.

## Co nadal wymaga uwagi

- **Duże bloki Free Time** — plany są gęstsze (6 atrakcji/dzień w testach), ale popołudniowe luki nadal mogą być znaczące; pełne „dopicie” harmonogramu to osobna iteracja.
- **Friends jako osobny profil rankingowy** — bez zmian (odroczone).
- Przy bardzo długich pobytach (5–7 dni) w jednym uzdrowisku nadal warto rozważyć `is_cluster=true`, aby planer świadomie mieszał trzy miasta regionu.

## Testy regresji
- `test_fix203.py`: 54/54 PASS  
- `test_naturalness_klientka.py`: 10/10 PASS  

Prosimy o ponowne odpalenie scenariuszy Kudowa / Polanica / Kłodzko (szczególnie family_kids, local_food, museum+history, 4–5 dni).
