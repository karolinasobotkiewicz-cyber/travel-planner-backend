"""FIX #369 P2: curated Kraków car parks — where the car actually stands.

Every entry is a real, publicly accessible ``amenity=parking`` object in
OpenStreetMap. Coordinates are the OSM centroid returned by Nominatim
(nominatim.openstreetmap.org, queried 2026-10-09); ``access``/``fee`` were
read from the OSM API (api.openstreetmap.org/api/0.6/ways). Objects tagged
``access=private|no|customers`` were rejected (e.g. Wawel "Droga do Zamku"
way 85151352, Plac Nowy way 1250053442, "Parking Kopalnia Soli" way 55694853).
Names are the OSM ``name`` when present, otherwise the street the lot is on;
no label may contain a POI name (the validators match names by substring).
"""
from __future__ import annotations

import math
import unicodedata
from typing import Dict, List, Optional, Tuple

LatLng = Tuple[float, float]

# name, lat, lng, OSM source, area served
KRAKOW_PARKINGS: List[Dict[str, object]] = [
    {"name": "Parking Galeria Krakowska (ul. Pawia 5)", "lat": 50.0677233, "lng": 19.9463019,
     "source": "OSM way 391159441 'Car Park Galeria Krakowska', rooftop, fee", "area": "Kleparz / Dworzec / pl. Matejki"},
    {"name": "Parking ul. Szpitalna", "lat": 50.0642545, "lng": 19.9428476,
     "source": "OSM way 303843180 'Parking płatny', supervised, fee", "area": "Stare Miasto wschód"},
    {"name": "Parking ul. Basztowa", "lat": 50.0660021, "lng": 19.9357082,
     "source": "OSM way 1565834014, access=yes, fee", "area": "Stare Miasto północ / pl. Szczepański"},
    {"name": "Parking ul. Krupnicza", "lat": 50.0631544, "lng": 19.9295848,
     "source": "OSM way 3037325106, surface, access=yes, fee", "area": "Piasek / Stare Miasto zachód"},
    {"name": "Parking Starowiślna (ul. Starowiślna 13)", "lat": 50.0577295, "lng": 19.9430224,
     "source": "OSM way 359540610 'Parking Starowiślna', 130 places, fee", "area": "Stradom / Kazimierz północ"},
    {"name": "Parking plac Na Groblach (pod Wawelem)", "lat": 50.0557117, "lng": 19.9316834,
     "source": "OSM way 1553018285, street_side", "area": "Wawel / Powiśle"},
    {"name": "Parking przy Muzeum (al. 3 Maja)", "lat": 50.0596707, "lng": 19.9235502,
     "source": "OSM way 371916800 'Parking przy Muzeum', underground, 150 places, fee", "area": "Muzeum Narodowe / Błonia wschód"},
    {"name": "Parking al. 3 Maja (Błonia)", "lat": 50.0610032, "lng": 19.9126105,
     "source": "OSM way 1510948009, lane", "area": "Błonia / Cichy Kącik"},
    {"name": "Parking ul. Piastowska 18", "lat": 50.0630212, "lng": 19.9009764,
     "source": "OSM way 1215732988, multi-storey, access=yes, fee", "area": "Błonia zachód / Cichy Kącik"},
    {"name": "Parking pl. Paula McCartneya (pod Kopcem)", "lat": 50.0544376, "lng": 19.8934594,
     "source": "OSM way 1174519553, surface, access=yes, free, 24/7", "area": "Kopiec Kościuszki"},
    {"name": "Parking al. Kasy Oszczędności Miasta Krakowa", "lat": 50.0554676, "lng": 19.8542673,
     "source": "OSM way 25171266, surface, access=yes, fee", "area": "Ogród Zoologiczny / Las Wolski"},
    {"name": "Parking ul. Królowej Jadwigi", "lat": 50.066314, "lng": 19.8718164,
     "source": "OSM way 189431666, surface, access=yes, free", "area": "Wola Justowska / Park Decjusza"},
    {"name": "Parking Dębniki (ul. Tyniecka)", "lat": 50.0463511, "lng": 19.9077279,
     "source": "OSM way 1566426284, street_side", "area": "Dębniki / Skałki Twardowskiego"},
    {"name": "Parking plac Wolnica", "lat": 50.048352, "lng": 19.9439581,
     "source": "OSM way 1104825773, street_side, access=yes, fee", "area": "Kazimierz / pl. Wolnica"},
    {"name": "Parking ul. Dietla", "lat": 50.0573938, "lng": 19.9456033,
     "source": "OSM way 104019245, surface, access=yes, fee", "area": "Stradom / Kazimierz północ"},
    {"name": "Parking Zabłocie (ul. Przemysłowa)", "lat": 50.0483435, "lng": 19.9602879,
     "source": "OSM way 743598740, street_side, access=yes", "area": "Zabłocie / Schindler / MOCAK"},
    {"name": "Parking Podgórze (ul. Na Zjeździe)", "lat": 50.0477622, "lng": 19.9551143,
     "source": "OSM way 306984735, surface, access=yes, free", "area": "pl. Bohaterów Getta"},
    {"name": "Parking przy Rynku Podgórskim", "lat": 50.0438144, "lng": 19.949171,
     "source": "OSM way 1117497874, street_side", "area": "Stare Podgórze / Park Bednarskiego"},
    {"name": "Parking Grzegórzki (ul. Grzegórzecka)", "lat": 50.0583712, "lng": 19.9487727,
     "source": "OSM way 176253043, surface, access=yes, fee", "area": "Grzegórzki / Kazimierz wschód"},
    {"name": "Parking Czyżyny (al. Pokoju)", "lat": 50.0664755, "lng": 19.9930079,
     "source": "OSM way 360935723, street_side", "area": "Park Lotników / Muzeum Lotnictwa"},
    {"name": "Parking ul. Dobrego Pasterza", "lat": 50.0900778, "lng": 19.985503,
     "source": "OSM way 1287485432, street_side", "area": "Park Wodny"},
    {"name": "Parking al. Solidarności", "lat": 50.0729268, "lng": 20.0382661,
     "source": "OSM way 1199246742, street_side, free", "area": "Plac Centralny"},
    {"name": "Parking ul. Daniłowicza", "lat": 49.9824809, "lng": 20.0570592,
     "source": "OSM way 149731735 'Parking Wieliczka', surface, access=yes, fee", "area": "Kopalnia Soli / Tężnia"},
    {"name": "Parking miejski Rynek Górny", "lat": 49.9823844, "lng": 20.059838,
     "source": "OSM way 899239422 'Parking miejski', access=yes, fee", "area": "Rynek Górny w Wieliczce"},
]


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


_BY_FOLD = {_fold(p["name"]): p for p in KRAKOW_PARKINGS}


def _hav(a: LatLng, b: LatLng) -> float:
    r = 6371.0
    dlat = math.radians(b[0] - a[0])
    dlng = math.radians(b[1] - a[1])
    x = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlng / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(x))


def nearest_parking(pt: LatLng) -> Tuple[Dict[str, object], float]:
    """The curated car park closest to ``pt`` and its straight-line km."""
    best = min(KRAKOW_PARKINGS, key=lambda p: _hav(pt, (p["lat"], p["lng"])))
    return best, _hav(pt, (best["lat"], best["lng"]))


def parking_by_label(label: str) -> Optional[Dict[str, object]]:
    return _BY_FOLD.get(_fold(label))


def parking_point(label: str) -> Optional[LatLng]:
    p = parking_by_label(label)
    return (float(p["lat"]), float(p["lng"])) if p else None


def is_parking_label(label: str) -> bool:
    """A concrete car park: a curated entry or any label naming a parking."""
    f = _fold(label)
    return bool(f) and (f in _BY_FOLD or f.startswith("parking"))


# Kraków start point (Rynek Główny, same pin as leg_physics.KRAKOW_HUB users).
def start_parking(hub: LatLng) -> Dict[str, object]:
    """Where the car stands when the day starts: the car park nearest the start."""
    return nearest_parking(hub)[0]
