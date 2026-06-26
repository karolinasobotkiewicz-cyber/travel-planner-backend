# FIX #220 — Mapa tras (Leaflet) + OpenRouteService

Backend zwraca geometrię trasy w każdym elemencie `transit` planu. Front nie musi wołać ORS bezpośrednio.

## Pola w `transit`

```json
{
  "type": "transit",
  "from": "Rynek Główny",
  "to": "Ostrów Tumski",
  "duration_min": 14,
  "mode": "walk",
  "geometry": [[17.038, 51.110], [17.042, 51.112]],
  "geometry_latlng": [[51.110, 17.038], [51.112, 17.042]],
  "distance_km": 1.2,
  "routing_source": "ors"
}
```

| Pole | Opis |
|------|------|
| `geometry` | GeoJSON `[lng, lat]` — zgodne z ORS |
| `geometry_latlng` | `[lat, lng]` — gotowe pod **Leaflet** `L.polyline()` |
| `distance_km` | Dystans trasy w km |
| `routing_source` | `ors` \| `cache` \| `haversine` (brak klucza ORS → haversine) |

Pola opcjonalne — gdy `null`, narysuj prostą linię między atrakcjami.

## Leaflet — minimalny przykład

```javascript
import L from 'leaflet';

function drawDayRoutes(day) {
  const layers = [];
  for (const item of day.items) {
    if (item.type !== 'transit' || !item.geometry_latlng?.length) continue;
    const line = L.polyline(item.geometry_latlng, {
      color: item.mode === 'car' ? '#2563eb' : '#16a34a',
      weight: 4,
      opacity: 0.85,
    });
    line.bindPopup(`${item.from} → ${item.to} (${item.duration_min} min)`);
    layers.push(line);
  }
  return L.layerGroup(layers);
}
```

Kafelki mapy (darmowe): `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`

## Włączenie ORS (Render / .env)

```env
ORS_API_KEY=<klucz z openrouteservice.org>
ORS_ENABLED=true
ORS_ROUTING_ENABLED=true
ORS_MATRIX_ENABLED=true
ORS_POI_SUPPLEMENT_ENABLED=true
```

Bez `ORS_ENABLED=true` plan działa jak dotychczas (haversine), bez regresji.

## POI z mapy (Overpass)

Gdy Excel nie wystarcza (pusty/słaby dzień), backend może uzupełnić plan atrakcjami z OpenStreetMap.

- **Priorytet zawsze: Excel**
- Duplikaty (ta sama lokalizacja / nazwa) są odfiltrowywane
- Uzupełnienie tylko w **gap-fill**, nie w głównej pętli engine
- W opisie POI: *„Atrakcja uzupełniająca z mapy (OpenStreetMap)”*
- `poi_id` prefix: `ext_osm_…`

## Limity darmowego ORS

| Endpoint | Limit/dzień | U nas |
|----------|-------------|-------|
| Directions | 2 000 | trasy między atrakcjami (+ cache) |
| Matrix | 500 | optymalizacja kolejności w dniu (≥3 atrakcje) |

Cache tras: domyślnie 60 dni (`.cache/ors_routes` lub `ORS_CACHE_DIR`).

## Testowanie

1. Ustaw `ORS_ENABLED=true` i klucz API.
2. Wygeneruj plan 2–7 dni (np. Wrocław).
3. Sprawdź w response: `transit[].geometry_latlng` niepuste dla `routing_source: ors`.
4. Wyłącz ORS → plan nadal poprawny, `routing_source: haversine`.
