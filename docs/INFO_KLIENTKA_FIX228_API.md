# Poprawki backendu — API / front (01.07.2026)

Poniżej krótko, co zostało naprawione po uwagach frontowca oraz odpowiedzi na Twoje pytania.

## 1. Niespójność `image_url` (destinations)
Był błąd: dla `image_key = "destination_wroclaw.jpg"` backend zwracał
`.../destination_wroclaw.jpg.webp` (podwójne rozszerzenie), a w Supabase jest
plik `destination_wroclaw.webp`.

Naprawione: backend zdejmuje dowolne rozszerzenie z klucza i zawsze buduje
poprawny `.webp`. Dodatkowo `image_key` w odpowiedzi jest teraz bez rozszerzenia
(spójny z `image_url`). Rozwiązany też problem `NaN.webp` — puste/`NaN`/`null`
klucze zwracają `null` zamiast błędnego URL.

## 2. Miasta na stronie głównej (`GET /content/home`)
API zwraca teraz wszystkie 15 miast. Dla każdego jest:
- **name** — nazwa,
- **region_type** — typ regionu,
- **api_city** — dokładna wartość do wysłania w `location.city` do `POST /plan/preview`.

| Nazwa | region_type | Wartość do API (`location.city`) |
|---|---|---|
| Zakopane | mountain | `Zakopane` |
| Kraków | city | `Kraków` |
| Gdańsk | sea | `Gdańsk` |
| Gdynia | sea | `Gdynia` |
| Sopot | sea | `Sopot` |
| Wrocław | city | `Wrocław` |
| Karpacz | mountain | `Karpacz` |
| Jelenia Góra | mountain | `Jelenia Góra` |
| Szklarska Poręba | mountain | `Szklarska Poręba` |
| Polanica-Zdrój | spa_region | `Polanica-Zdrój` |
| Kudowa-Zdrój | spa_region | `Kudowa-Zdrój` |
| Kłodzko | mountain | `Kłodzko` |
| Poznań | city | `Poznań` |
| Katowice | city | `Katowice` |
| Warszawa | city | `Warszawa` |

Front wysyła `location: { "city": <api_city>, "country": "Poland", "region_type": <region_type> }`.

## 3. Status płatności planu
Wcześniej `GET /plan/{id}/status` zawsze zwracał `ready` i nie było jak
sprawdzić, czy plan jest opłacony.

Teraz zwraca dodatkowo:
- `paid` (true/false),
- `payment_status` (`paid` / `unpaid`),
- `is_assigned` (czy plan jest przypisany do konta),
- `city`, `title`, `start_date`, `days_count`.

## 4. Blokada nieopłaconych planów (paywall)
`GET /plan/{id}` blokuje teraz nieopłacone plany dla osób postronnych
(zwraca `402 Payment Required`). Właściciel (po `Authorization` lub nagłówku
`X-Guest-ID`) zawsze widzi swój plan. To zamyka lukę „zmiana `/paywal?plan=`
na `/plan/` pokazuje pełny plan".

## 5. Autentykacja dla planów przypisanych do konta — odpowiedź na pytanie
Tak, rekomendujemy wymagać logowania dla planów przypisanych do konta.
Mechanizm jest już w backendzie i włącza się flagą `ENFORCE_ASSIGNED_PLAN_AUTH=true`
(domyślnie wyłączona, żeby nic nie zepsuć, dopóki front nie wysyła tokenu przy
`GET /plan/{id}`). Po włączeniu: plan przypisany do konta widzi tylko zalogowany
właściciel. Front rozpoznaje takie plany po polu `is_assigned`.

## 6. Nazwa planu „Unknown"
Plany zapisują się teraz z prawdziwym miastem, grupą, budżetem i datą startu.
Zamiast „Unknown" jest czytelna nazwa, np. **„Wrocław — 3 dni"** (pole `title`).
Dotyczy `GET /plan/{id}/status`, `GET /plan/my-plans` i `GET /plan/{id}`.

## 7. Miasto + daty w planie
`GET /plan/{id}` (i odpowiedź z `POST /plan/preview`) zwraca teraz:
- `city`, `region_type`, `group_type`, `start_date`, `days_count`, `title`,
- w każdym dniu: `date` (YYYY-MM-DD) oraz `weekday` (dzień tygodnia po polsku).

## 8. Obrazki `null` / `NaN.webp`
Naprawione globalnie — wszystkie obrazki (miasta, POI, restauracje) budują URL
tą samą, odporną logiką: puste/`NaN` → `null`, reszta → poprawny `.webp`.

## 9. Generowanie i pobieranie PDF
Dodany endpoint **`GET /plan/{id}/pdf`** — generuje i zwraca plan jako plik PDF
(`application/pdf`, jako załącznik). Obsługuje polskie znaki. Ta sama kontrola
dostępu co przy podglądzie planu (paywall / właściciel).
