# ODPOWIEDŹ - SUPABASE STORAGE KONWENCJA

**Data:** 11.03.2026

---

Cześć!

**Struktura buckets - OK ✅**
- `destinations` dla zdjęć miast
- `poi` dla zdjęć atrakcji

**Naming - OK ✅**
- Zgodne z `image_key` (np. `destination_zakopane.jpg`)
- **Format:** Proponuję `.webp` (lepsza kompresja) lub `.jpg` - ustal co wolisz, ja się dostosuję

**URL building - backend zwraca gotowy `image_url` ✅**

**Dlaczego:**
- Bardziej flexible (mogę zmienić storage provider bez zmiany frontu)
- Mogę dodać CDN later
- Mogę dodać signed URLs jak będzie potrzeba security
- Frontend prosty - dostaje gotowy URL, tylko `<img src={image_url}>`

**Co zrobię:**
- Dodam pole `image_url` w odpowiedziach API (destinations, POI)
- Backend compute URL: `{supabase_url}/storage/v1/object/public/{bucket}/{image_key}.webp`
- Jeśli brak zdjęcia → zwrócę `null` albo placeholder URL

**Przykład response:**
```json
{
  "id": "poi_morskie_oko",
  "name": "Morskie Oko",
  "image_key": "poi_morskie_oko",
  "image_url": "https://xxx.supabase.co/storage/v1/object/public/poi/poi_morskie_oko.webp"
}
```

**Jak wrzucisz zdjęcia do buckets - daj znać, dodam `image_url` do API.**

Pozdrawiam,  
Mateusz

---

## UPDATE 11.03.2026 - ODPOWIEDŹ NA PYTANIE O KOLUMNY

**Pytanie:**
> Czy w tabelach atrakcji POI powinnam dodać jakąś kolumnę, gdzie wrzucę nazwę odpowiedniego zdjęcia czy wystarczy po prostu dobrze nazwany w buckets np. poi_morskie_oko?

**Odpowiedź:**

**NIE, nie dodawaj nowych kolumn ✅**

Tabela POI już ma kolumnę `image_key` (np. `"poi_morskie_oko"`).

**Jak to działa:**
1. Backend czyta `image_key` z bazy
2. Buduje URL: `https://xxx.supabase.co/storage/v1/object/public/poi/{image_key}.webp`
3. Zwraca w API jako `image_url`

**Ty musisz tylko:**
- Nazwać plik w bucket zgodnie z `image_key` z bazy
- Przykład: 
  - Baza: `image_key = "poi_morskie_oko"`
  - Bucket: `poi_morskie_oko.webp` lub `poi_morskie_oko.jpg`

**Format pliku:**
Ustal czy `.webp` czy `.jpg` - ja się dostosuję w kodzie. Webp lepszy (mniejszy), ale jpg bardziej kompatybilny.

**Teraz mogę dodać `image_url` do API** - masz już zdjęcia wrzucone?

Pozdrawiam,  
Mateusz

---

## UPDATE 2 - 11.03.2026 - POTWIERDZENIE

**Klientka potwierdziła:**
- ✅ Format: **WebP**
- ✅ Destinations wrzucone do bucket
- ✅ POI przykładowo (czeka na zgody atrakcji)
- ✅ Gotowa na dodanie `image_url` do API

**ZANOTOWANE - WAŻNE DECYZJE:**

### Bucket Structure:
- `destinations` - zdjęcia miast
- `poi` - zdjęcia atrakcji

### Naming & Format:
- **Format plików: `.webp`** (potwierdzony)
- Nazwy: zgodne z `image_key` (np. `poi_morskie_oko.webp`)

### Backend:
- Zwraca gotowy `image_url` w responses
- URL: `{supabase_url}/storage/v1/object/public/{bucket}/{image_key}.webp`
- Fallback dla brakujących: `null` lub placeholder

### Database:
- Używamy istniejącej kolumny `image_key`
- Bez nowych kolumn

**NEXT STEP:** Implementacja `image_url` w API responses (destinations + POI)
