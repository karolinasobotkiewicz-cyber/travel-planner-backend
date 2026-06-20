# Odpowiedź dla klientki — FIX #207 (19.06.2026)

Dotyczy: **Wrocław** i **Poznań**.

---

## Wrocław

| # | Zgłoszenie | Status | Co zrobiliśmy |
|---|------------|--------|---------------|
| 1 | Ogród Botaniczny — współrzędne Krakowa | **Naprawione** | Poprawiono City/Hub i GPS na Wrocław |
| 2 | Nature Landscape rzadko wybierane | **Poprawione** | Boost natury (+45) w planach miejskich z naturą w top-3 |
| 3 | Duży Free Time | **Częściowo** | Działa cap z FIX #206; długie plany 5–7 dni — kolejna iteracja |
| 4 | Adventure → Rynek, Ostrów… | **Poprawione** | Kara -45 na heritage bez kultury w top-3; mikro-POI quick-stop |
| 5 | Friends słabo wpływa | **Bez zmian** | Wymaga osobnego tasku (jak Kraków/Warszawa) |
| 6 | Mikro-POI za wysoka waga | **Poprawione** | Markery + kary quick-stop (most, bastion, wyspa…) |
| 8 | Relaxation: Hala Stulecia, Muzeum | **Naprawione** | Poprawka dopasowania tagów `spa` + name-deny |
| 9 | Local Food słabo | **Poprawione** | Dodano Hala Targowa Wrocław + boost +40; Browar Stu Mostów **brak w Excelu klientki** |

## Poznań

| # | Zgłoszenie | Status | Co zrobiliśmy |
|---|------------|--------|---------------|
| 1 | Duży Free Time | **Częściowo** | Jak wyżej — cap post-dinner, backfill w toku |
| 2 | Mikro-POI (Pręgierz, Okrąglak…) | **Poprawione** | Quick-stop + democja priority/must_see w danych |
| 3 | Adventure — wciąż muzea/kościoły | **Poprawione** | Heritage penalty + urban active boost (FIX #206) |
| 4 | Nature znika przy museum+history | **Poprawione** | Nature boost + kara muzeów gdy oba w top-3 |
| 5 | Free time w planach 5–7 dni | **Częściowo** | Kolejna iteracja density/backfill |

---

## Prośba do klientki (dane)

1. **Browar Stu Mostów** (Wrocław) — prosimy o dodanie do arkusza atrakcji
   (brak w planer8).
2. Weryfikacja **City** przy imporcie — Ogród Botaniczny Wrocławski miał City=Kraków
   w źródle klientki.

---

Wszystkie testy regresji (w tym Zakopane 10/10) przechodzą po wdrożeniu.
