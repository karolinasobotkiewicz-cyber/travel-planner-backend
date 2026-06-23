# Baza Excel v2 — import potwierdzony ✅

> Dla: klientka (Etap 3)  
> Data: **23 czerwca 2026** (druga poprawka tego dnia)  
> Status: **zaimportowana, gotowa do testów**

---

## Podsumowanie

| | v1 (rano) | v2 (popołudnie) |
|---|---:|---:|
| Wiersze | 713 | **711** |
| Valid POI (silnik) | 709 | **711** |
| Błędy walidatora | 6 | **0** |

**Commit produkcyjny:** po pushu na `origin/main`.

---

## Co poprawiła klientka w v2 ✅

| Punkt | Status |
|-------|--------|
| **Browary Warszawskie** | ✅ Lat/Lng/City uzupełnione, w loaderze |
| **Hala Targowa** | ✅ Lat/Lng/City uzupełnione (City=Gdańsk), w loaderze |
| **Puste wiersze Jelenia Góra** | ✅ Usunięte (0 problematycznych) |
| **Pomnik Syreny** | ✅ must_see obniżony do **4** |
| **Góralski Ślizg** | ✅ `spring,summer,autumn` |
| Wszystkie mikro-POI must_see | ✅ ≤7 |
| Browar Stu Mostów | ✅ nadal obecny |
| seniors friends | ✅ OK |

---

## Wyjaśnienie: „puste wiersze w Jeleniej Górze”

W poprzedniej wersji (v1) były **2 wiersze z `City=Jelenia Góra`, ale bez nazwy POI** (pusta komórka `Name`). W Excelu wyglądały jak zwykłe puste komórki w środku arkusza — łatwo je przeoczyć, bo nie miały nazwy ani współrzędnych.

W v2 klientka je **usunęła** — stąd 713 → 711 wierszy i **0 błędów** walidatora.

---

## Zmiany vs poprzednia produkcja (v1)

Głównie **doprecyzowanie nazw** (dodanie miasta w nazwie POI):

- `Muzeum Historii i Militariów` → `Muzeum Historii i Militariów w Jeleniej Górze`
- `Złoty Pstrąg` → `Łowisko Złoty Pstrąg`
- `Sery Lutomierskie` → `Zagroda Pasternak - Sery Lutomierskie`
- itd.

**Nowe / przywrócone POI:** m.in. Zagroda Pasternak, Łowisko Złoty Pstrąg, Muzeum w JG z pełną nazwą.

**Usunięte:** m.in. `Hala Koszyki`, `Muzeum Fabryka Czekolady`, `Zapora na Łomnicy` (zastąpione innymi wersjami nazw).

---

## Testy po imporcie

| Test | Wynik |
|------|-------|
| Walidator Excel | **0 errors**, 45 warnings |
| Loader | ✅ 711 POI |
| `test_naturalness_klientka.py` | ✅ **10/10** |
| `test_fix203.py` coverage | ✅ **61/61** |
| `test_fix203.py` micro-POI | ⚠️ 1 fail: `plac Ratuszowy` JG — celowo usunięty |

---

## Otwarte (P2, nie blokuje)

- ~24 typy unknown tags (`outdoor_activity`, `easy_nature` itd.) — ignorowane w scoringu
- `priority_level=2` w kilku wierszach — powinno być high/medium/low
- Hel/Rewa Hub — część ma Hub=Hel zamiast Gdańsk/Gdynia

---

## Wiadomość do klientki (gotowa)

> Baza zaktualizowana ✅ — możesz robić testy.
>
> Wszystko wygląda dobrze: Browary Warszawskie i Hala Targowa uzupełnione, Pomnik Syreny i Góralski Ślizg poprawione, **711 POI** bez błędów.
>
> Co do pustych wierszy w Jeleniej Górze — w poprzedniej wersji były 2 wiersze z samym miastem, bez nazwy atrakcji (niewidoczne na pierwszy rzut oka). W Twojej nowej wersji ich już nie ma 👍

---

*Import v2 | stan silnika: FIX #211/#212*
