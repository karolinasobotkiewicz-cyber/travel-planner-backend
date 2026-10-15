"""FIX #369 P1: honest leg physics from coordinates (Kraków UAT 2026-10-09).

Every transit leg is derived from the two endpoint pins:

* straight line (haversine) x detour factor (walk 1.30, car 1.40, transit 1.35);
* in Kraków, a leg whose straight line crosses the Wisła is routed through the
  cheapest real bridge (pedestrian footbridges only for walks);
* minutes from km and a mode speed; walks longer than the profile threshold
  (2.0 km seniors / relax, else 2.5 km) are not offered as walks.

No constant fallbacks (0.5 km / 10 min, 0.8 km / 10 min, 0.4 km / 8 min): a leg
without two pins is reported as unresolved by the caller, never invented.

River line: OSM relation 34392 (Wisła) clipped to Kraków, Douglas-Peucker
simplified (~40 m); every bridge below sits within 80 m of it. Bridges are
Nominatim positions (OSM). Data © OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.infrastructure.routing.haversine import haversine_km

LatLng = Tuple[float, float]

WALK_DETOUR = 1.30
CAR_DETOUR = 1.40
TRANSIT_DETOUR = 1.35

WALK_SPEED_KMH = 4.5
WALK_SPEED_SLOW_KMH = 3.8  # seniors / relax
CAR_URBAN_KMH = 24.0       # Kraków door-to-door average incl. lights
CAR_OPEN_KMH = 55.0        # beyond the urban core (Wieliczka, Ojców, ...)
CAR_OVERHEAD_MIN = 4       # unpark + park at the far end
TRANSIT_KMH = 16.0
TRANSIT_WAIT_MIN = 6

WALK_MAX_KM = 2.5
WALK_MAX_KM_SLOW = 2.0
URBAN_RADIUS_KM = 12.0

# Signatures the old passes stamped without looking at coordinates.
CONSTANT_LEG_SIGNATURES = frozenset({(0.5, 10), (0.8, 10), (0.4, 8)})

KRAKOW_WISLA: Tuple[LatLng, ...] = (
    (49.98342, 19.78008), (49.98498, 19.78488), (49.99172, 19.78858),
    (49.99578, 19.79605), (49.99816, 19.79654), (50.01109, 19.79357),
    (50.01433, 19.79542), (50.01707, 19.79934), (50.02344, 19.80257),
    (50.02523, 19.80483), (50.03065, 19.81925), (50.03548, 19.82986),
    (50.03735, 19.83879), (50.04246, 19.84739), (50.04321, 19.85023),
    (50.04404, 19.86873), (50.04345, 19.8719), (50.03871, 19.87951),
    (50.03809, 19.88824), (50.03889, 19.89743), (50.04126, 19.90104),
    (50.04941, 19.90675), (50.05124, 19.91065), (50.05202, 19.92208),
    (50.05454, 19.92999), (50.05408, 19.93165), (50.04636, 19.93708),
    (50.04484, 19.94136), (50.04512, 19.94393), (50.05271, 19.96138),
    (50.0529, 19.96674), (50.05222, 19.97101), (50.05261, 19.97451),
    (50.05503, 19.98027), (50.05914, 19.98429), (50.05987, 19.98802),
    (50.05913, 19.99178), (50.0569, 19.99569), (50.05107, 19.99938),
    (50.04846, 20.00279), (50.04563, 20.00906), (50.0449, 20.01276),
    (50.04554, 20.01597), (50.04999, 20.01947), (50.05177, 20.02363),
    (50.0511, 20.02699), (50.04839, 20.03249), (50.04781, 20.03713),
    (50.04826, 20.03985), (50.05127, 20.04586), (50.05203, 20.04935),
    (50.05051, 20.0594), (50.05046, 20.0681), (50.05308, 20.08569),
    (50.05283, 20.08858), (50.05127, 20.09195), (50.04874, 20.09414),
    (50.04393, 20.09471), (50.04204, 20.09756), (50.04129, 20.10069),
    (50.04157, 20.10477), (50.04265, 20.10774), (50.04268, 20.1154),
    (50.03993, 20.12368), (50.03962, 20.12728), (50.04073, 20.13054),
    (50.04487, 20.13492), (50.046, 20.13885), (50.04584, 20.14233),
)

# (name, lat, lng, car_allowed)
KRAKOW_BRIDGES: Tuple[Tuple[str, float, float, bool], ...] = (
    ("A4 / Stopień Kościuszko", 50.0306525, 19.8192445, True),
    ("Most Zwierzyniecki", 50.0486875, 19.9066471, True),
    ("Most Dębnicki", 50.0540919, 19.9283920, True),
    ("Most Grunwaldzki", 50.0496035, 19.9342259, True),
    ("Kładka Ludwinów-Kazimierz", 50.0453531, 19.9387638, False),
    ("Most Piłsudskiego", 50.0447807, 19.9448655, True),
    ("Kładka Ojca Bernatka", 50.0465578, 19.9475040, False),
    ("Most Powstańców Śląskich", 50.0493359, 19.9531358, True),
    ("Most Kotlarski", 50.0524590, 19.9610007, True),
    ("Most Nowohucki", 50.0550001, 19.9968037, True),
    ("Most Wandy", 50.0512620, 20.0498078, True),
)

_KRK_BBOX = (49.95, 50.13, 19.75, 20.20)
KRAKOW_HUB: LatLng = (50.0647, 19.9450)  # same pin as plan_service._CITY_CENTER_COORDS


def _xy(p: LatLng) -> Tuple[float, float]:
    # Local equirectangular plane (fine for intersection tests at city scale).
    return p[1] * math.cos(math.radians(50.05)), p[0]


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_cross(p1: LatLng, p2: LatLng, q1: LatLng, q2: LatLng) -> bool:
    a, b, c, d = _xy(p1), _xy(p2), _xy(q1), _xy(q2)
    d1, d2 = _orient(c, d, a), _orient(c, d, b)
    d3, d4 = _orient(a, b, c), _orient(a, b, d)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def in_krakow(p: Optional[LatLng]) -> bool:
    if not p:
        return False
    la0, la1, lo0, lo1 = _KRK_BBOX
    return la0 <= p[0] <= la1 and lo0 <= p[1] <= lo1


def wisla_crossings(a: LatLng, b: LatLng) -> int:
    """How many times the straight line a→b crosses the Wisła in Kraków."""
    n = 0
    for q1, q2 in zip(KRAKOW_WISLA, KRAKOW_WISLA[1:]):
        if _segments_cross(a, b, q1, q2):
            n += 1
    return n


def crosses_wisla(a: LatLng, b: LatLng) -> bool:
    """Opposite banks: the straight line crosses the river an odd number of times."""
    if not (in_krakow(a) or in_krakow(b)):
        return False
    return wisla_crossings(a, b) % 2 == 1


def best_bridge(a: LatLng, b: LatLng, *, walk: bool) -> Optional[Tuple[str, float, float]]:
    best = None
    for name, la, lo, car_ok in KRAKOW_BRIDGES:
        if not walk and not car_ok:
            continue
        via = haversine_km(a[0], a[1], la, lo) + haversine_km(la, lo, b[0], b[1])
        if best is None or via < best[0]:
            best = (via, name, la, lo)
    if best is None:
        return None
    return best[1], best[2], best[3]


Bridge = Tuple[str, float, float]


def base_km(a: LatLng, b: LatLng, *, walk: bool, city: str = "") -> Tuple[float, Optional[Bridge]]:
    """Straight-line km, or km via the cheapest bridge when the leg crosses the Wisła."""
    straight = haversine_km(a[0], a[1], b[0], b[1])
    if _is_krakow(city) and crosses_wisla(a, b):
        br = best_bridge(a, b, walk=walk)
        if br:
            via = haversine_km(a[0], a[1], br[1], br[2]) + haversine_km(br[1], br[2], b[0], b[1])
            return max(straight, via), br
    return straight, None


def _is_krakow(city: str) -> bool:
    c = (city or "").lower()
    return "kraków" in c or "krakow" in c


def is_slow_profile(context: Optional[Dict[str, Any]]) -> bool:
    """Seniors or a relax trip walk slower and shorter."""
    ctx = context or {}
    user = ctx.get("user") if isinstance(ctx.get("user"), dict) else {}
    group = str(
        ctx.get("group_type")
        or (ctx.get("group") or {}).get("type")
        or user.get("target_group")
        or ""
    ).lower()
    style = str(ctx.get("travel_style") or user.get("travel_style") or "").lower()
    return "senior" in group or style in ("relax", "relaxed", "slow")


def walk_threshold_km(context: Optional[Dict[str, Any]]) -> float:
    raw = (context or {}).get("walk_max_km")
    if raw:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    return WALK_MAX_KM_SLOW if is_slow_profile(context) else WALK_MAX_KM


def walk_minutes(km: float, context: Optional[Dict[str, Any]] = None) -> int:
    speed = WALK_SPEED_SLOW_KMH if is_slow_profile(context) else WALK_SPEED_KMH
    return max(2, int(math.ceil(km / speed * 60)))


def car_minutes(km: float) -> int:
    if km <= URBAN_RADIUS_KM:
        drive = km / CAR_URBAN_KMH * 60
    else:
        drive = URBAN_RADIUS_KM / CAR_URBAN_KMH * 60 + (km - URBAN_RADIUS_KM) / CAR_OPEN_KMH * 60
    return max(5, int(math.ceil(drive)) + CAR_OVERHEAD_MIN)


def transit_minutes(km: float) -> int:
    return max(8, int(math.ceil(km / TRANSIT_KMH * 60)) + TRANSIT_WAIT_MIN)


def leg_km(a: LatLng, b: LatLng, mode: str, *, city: str = "") -> Tuple[float, Optional[Bridge]]:
    walk = mode == "walk"
    base, bridge = base_km(a, b, walk=walk, city=city)
    factor = WALK_DETOUR if walk else (CAR_DETOUR if mode == "car" else TRANSIT_DETOUR)
    return round(base * factor, 3), bridge


def leg_minutes(km: float, mode: str, context: Optional[Dict[str, Any]] = None) -> int:
    if mode == "walk":
        return walk_minutes(km, context)
    if mode == "car":
        return car_minutes(km)
    return transit_minutes(km)


def honest_leg(
    a: LatLng,
    b: LatLng,
    *,
    requested_mode: str,
    context: Optional[Dict[str, Any]] = None,
    car_here: bool = False,
    force_walk_or_transit: bool = False,
) -> Dict[str, Any]:
    """Mode, km and minutes for a leg between two pins.

    ``requested_mode`` is what the timeline asked for (walk/car/public_transport).
    A walk above the profile threshold becomes a car ride when the car is at the
    origin, otherwise public transport. ``force_walk_or_transit`` (return to the
    car) never turns into a car ride.
    """
    ctx = context or {}
    city = str(ctx.get("requested_city") or ctx.get("city") or "")
    mode = requested_mode if requested_mode in ("walk", "car", "public_transport") else "walk"
    # FIX #373: a Kraków guest who chose only the car does not also ride MPK.
    # Other cities keep the previous walk/car/transit split.
    modes_allowed = [
        str(getattr(m, "value", m)).lower()
        for m in (ctx.get("transport_modes") or [])
    ]
    if _is_krakow(city):
        pt_allowed = (
            "public_transport" in modes_allowed
            if modes_allowed else not ctx.get("has_car", True)
        )
    else:
        pt_allowed = True
    if not pt_allowed and mode == "public_transport":
        mode = "car" if (ctx.get("has_car", True) and not force_walk_or_transit) else "walk"

    if mode == "walk" or force_walk_or_transit:
        km, bridge = leg_km(a, b, "walk", city=city)
        if km > walk_threshold_km(ctx):
            if not pt_allowed:
                if force_walk_or_transit:
                    mode = "walk"
                elif ctx.get("has_car", True):
                    mode = "car"
                else:
                    mode = "walk"
            elif car_here and not force_walk_or_transit and ctx.get("has_car", True):
                mode = "car"
            else:
                mode = "public_transport"
            km, bridge = leg_km(a, b, mode, city=city)
        else:
            mode = "walk"
    else:
        km, bridge = leg_km(a, b, mode, city=city)
    path: List[LatLng] = [a] + ([(bridge[1], bridge[2])] if bridge else []) + [b]
    return {
        "mode": mode,
        "km": km,
        "minutes": leg_minutes(km, mode, ctx),
        "bridge": bridge[0] if bridge else None,
        "path": path,
        "straight_km": round(haversine_km(a[0], a[1], b[0], b[1]), 3),
    }


def expected_km_bounds(a: LatLng, b: LatLng, mode: str, *, city: str = "") -> Tuple[float, float]:
    """(lower, upper) km a leg between the pins may honestly declare."""
    straight = haversine_km(a[0], a[1], b[0], b[1])
    base, _ = base_km(a, b, walk=(mode == "walk"), city=city)
    lower = 0.9 * straight
    upper = max(base * 2.0, straight * 2.6) + 0.5
    return lower, upper


def has_constant_signature(km: Any, minutes: Any) -> bool:
    try:
        return (round(float(km), 3), int(minutes)) in CONSTANT_LEG_SIGNATURES
    except (TypeError, ValueError):
        return False
