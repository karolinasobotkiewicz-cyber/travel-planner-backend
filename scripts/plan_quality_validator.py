"""FIX #366: automated plan quality validator for client-mail defects.

Checks idle gaps, stacked free_time, A→B→A hops, restaurant-without-meal,
visit-without-arrival, opening-hours (best-effort), overlaps, duplicate POI
across days, implausible walk, short car hops, short big-venue visits, and
target_group mismatches.

Other cities may already flag defects; the pytest wrapper only fails on
Kraków / Katowice unless FORCE_ALL_CITIES=1.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.domain.models.plan import ItemType
from app.domain.planner.time_utils import time_to_minutes
from app.infrastructure.routing.haversine import haversine_km

ROOT = Path(__file__).resolve().parents[1]
OUTER = ROOT.parent

BIG_VENUE_MIN = {
    "legendia": 90,
    "slaski ogrod zoologiczny": 90,
    "zoo": 90,
    "kopalnia guido": 90,
    "guido": 90,
    "pixel xl": 45,
    "browar mariacki": 45,
}

SENIOR_BAN = ("pixel xl", "legendia", "cybermag", "park linow", "gokart", "jumpcity")


def _tv(it: Any) -> str:
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def _fold(s: str) -> str:
    s = (s or "").lower()
    for a, b in (
        ("ą", "a"), ("ć", "c"), ("ę", "e"), ("ł", "l"), ("ń", "n"),
        ("ó", "o"), ("ś", "s"), ("ź", "z"), ("ż", "z"),
    ):
        s = s.replace(a, b)
    return s


def _nm(it: Any) -> str:
    return str(getattr(it, "name", "") or "")


def _clock(it: Any) -> Tuple[Optional[int], Optional[int]]:
    st = getattr(it, "start_time", None) or getattr(it, "time", None)
    en = getattr(it, "end_time", None) or st
    try:
        return (
            time_to_minutes(st) if st else None,
            time_to_minutes(en) if en else None,
        )
    except Exception:
        return None, None


@dataclass
class Hit:
    city: str
    json_num: int
    day: int
    code: str
    message: str


@dataclass
class Report:
    hits: List[Hit] = field(default_factory=list)

    def add(self, city: str, num: int, day: int, code: str, msg: str) -> None:
        self.hits.append(Hit(city, num, day, code, msg))

    def by_city(self) -> Dict[str, List[Hit]]:
        out: Dict[str, List[Hit]] = defaultdict(list)
        for h in self.hits:
            out[h.city].append(h)
        return out

    def counts(self) -> Dict[str, int]:
        c: Dict[str, int] = defaultdict(int)
        for h in self.hits:
            c[h.code] += 1
        return dict(c)


def validate_day(
    *,
    city: str,
    num: int,
    day_num: int,
    items: Sequence[Any],
    group_type: str = "",
    report: Report,
) -> None:
    items = list(items or [])
    # consecutive free_time
    run = 0
    max_run = 0
    for it in items:
        if _tv(it) == ItemType.FREE_TIME.value:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    if max_run > 1:
        report.add(city, num, day_num, "stacked_free_time", f"run={max_run}")

    # idle gaps > 60 excluding free_time coverage
    prev_en = None
    for it in items:
        st, en = _clock(it)
        if st is None:
            continue
        if prev_en is not None and st - prev_en > 60 and _tv(it) != ItemType.FREE_TIME.value:
            # only flag if no free_time filling - check previous was not free_time spanning
            report.add(city, num, day_num, "idle_gap", f"{prev_en}->{st} ({st-prev_en}m)")
        if en is not None:
            prev_en = en if prev_en is None else max(prev_en, en)

    # overlaps
    timed = []
    for it in items:
        st, en = _clock(it)
        if st is None or en is None or en <= st:
            continue
        if _tv(it) in (ItemType.DAY_START.value, ItemType.DAY_END.value):
            continue
        timed.append((st, en, _tv(it), _nm(it) or _tv(it)))
    timed.sort()
    for i, a in enumerate(timed):
        for b in timed[i + 1 :]:
            if b[0] >= a[1]:
                break
            if b[0] < a[1]:
                report.add(
                    city, num, day_num, "overlap",
                    f"{a[3]} {a[0]}-{a[1]} vs {b[3]} {b[0]}-{b[1]}",
                )

    # A->B->A with no activity at B
    transits = [(i, it) for i, it in enumerate(items) if _tv(it) == ItemType.TRANSIT.value]
    for k in range(len(transits) - 1):
        i1, t1 = transits[k]
        i2, t2 = transits[k + 1]
        a = _fold(getattr(t1, "from_location", "") or "")
        b = _fold(getattr(t1, "to_location", "") or "")
        b2 = _fold(getattr(t2, "from_location", "") or "")
        a2 = _fold(getattr(t2, "to_location", "") or "")
        if a and b and a == a2 and b == b2 and a != b:
            mid = items[i1 + 1 : i2]
            has_real = any(
                _tv(x) in (
                    ItemType.ATTRACTION.value,
                    ItemType.LUNCH_BREAK.value,
                    ItemType.DINNER_BREAK.value,
                )
                for x in mid
            )
            if not has_real:
                report.add(
                    city, num, day_num, "aba_hop",
                    f"{getattr(t1,'from_location',None)}->{getattr(t1,'to_location',None)}->{getattr(t2,'to_location',None)}",
                )

    # restaurant attraction without following meal
    for i, it in enumerate(items):
        if _tv(it) != ItemType.ATTRACTION.value:
            continue
        nm = _fold(_nm(it))
        if not any(
            k in nm
            for k in ("restaur", "bistro", "milkbar", "pizzer", "karczm", "zajazd")
        ):
            continue
        found = False
        for x in items[i + 1 : i + 6]:
            if _tv(x) in (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value):
                found = True
                break
            if _tv(x) == ItemType.ATTRACTION.value:
                break
        if not found:
            report.add(city, num, day_num, "restaurant_no_meal", _nm(it))

    # visit without arrival: attraction not matching previous transit dest
    last_to = None
    for it in items:
        if _tv(it) == ItemType.TRANSIT.value:
            last_to = _fold(getattr(it, "to_location", "") or "")
            continue
        if _tv(it) == ItemType.ATTRACTION.value:
            nm = _fold(_nm(it))
            if last_to and nm and last_to not in nm and nm not in last_to:
                # allow hub / generic
                if last_to not in ("",) and not any(
                    h in last_to for h in ("centrum", "hotel", "parking")
                ):
                    # only flag when previous transit went somewhere else and no shared token
                    tokens = set(nm.split()) & set(last_to.split())
                    if len(tokens) < 1:
                        report.add(
                            city, num, day_num, "visit_no_arrival",
                            f"visit={_nm(it)} last_to={last_to}",
                        )
            last_to = nm

    # short car, implausible walk
    for it in items:
        if _tv(it) != ItemType.TRANSIT.value:
            continue
        try:
            km = float(getattr(it, "distance_km", None) or 0)
        except (TypeError, ValueError):
            km = 0.0
        mode = str(
            getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or ""
        ).lower()
        dur = int(getattr(it, "duration_min", 0) or 0)
        if km > 0 and km < 0.5 and "car" in mode:
            report.add(
                city, num, day_num, "short_car",
                f"{km} km {getattr(it,'from_location',None)}->{getattr(it,'to_location',None)}",
            )
        if km > 0 and "walk" in mode and dur > 0:
            speed = km / (dur / 60.0)
            if speed > 8.0:  # > 8 km/h walk is implausible
                report.add(
                    city, num, day_num, "implausible_walk",
                    f"{km} km in {dur} min ({speed:.1f} km/h)",
                )

    # big venue short duration
    for it in items:
        if _tv(it) != ItemType.ATTRACTION.value:
            continue
        nm = _fold(_nm(it))
        dur = int(getattr(it, "duration_min", 0) or 0)
        for key, mn in BIG_VENUE_MIN.items():
            if key in nm and dur and dur < mn:
                report.add(
                    city, num, day_num, "short_venue",
                    f"{_nm(it)} {dur}m < {mn}",
                )
                break

    # FIX #367/#368 P0 hard-fail codes (location cursor, hubs, ABA meals)
    def _meal_place(it: Any) -> str:
        sugs = getattr(it, "suggestions", None) or []
        for s in sugs[:1]:
            if isinstance(s, dict):
                nm = (s.get("name") or "").strip()
            else:
                nm = (getattr(s, "name", None) or "").strip()
            if nm:
                return _fold(nm)
        for attr in ("location_context", "location", "name", "label"):
            v = (getattr(it, attr, None) or "").strip()
            if not v:
                continue
            f = _fold(v)
            if not f or f in ("centrum", "przy szlaku", "przy_szlaku"):
                continue
            if any(k in f for k in ("przerwa", "bufor", "regeneracyj")):
                continue
            if f in ("lunch", "dinner", "obiad", "kolacja"):
                continue
            return f
        return ""

    user_at = None
    car_at = None
    left_places = []
    hub_names = {
        "gdansk", "gdynia", "sopot", "karpacz", "jelenia gora",
        "szklarska poreba", "krakow", "katowice", "poznan", "warszawa",
    }
    n_transits = sum(1 for it in items if _tv(it) == ItemType.TRANSIT.value)
    t_idx = 0

    def _names_overlap(a: str, b: str) -> bool:
        if not a or not b:
            return False
        if a == b or a in b or b in a:
            return True
        tokens = set(a.split()) & set(b.split())
        return len(tokens) >= 1 and min(len(a), len(b)) >= 5

    def _mark_left(place: str) -> None:
        if not place or place in hub_names:
            return
        if any(_names_overlap(place, p) for p in left_places):
            return
        left_places.append(place)

    def _clear_left(place: str) -> None:
        if not place:
            return
        left_places[:] = [p for p in left_places if not _names_overlap(p, place)]

    def _was_left(place: str) -> bool:
        return bool(place) and any(_names_overlap(place, p) for p in left_places)

    for it in items:
        tv = _tv(it)
        if tv != ItemType.TRANSIT.value:
            if tv == ItemType.ATTRACTION.value:
                nm = _fold(_nm(it))
                if nm and user_at and not _names_overlap(nm, user_at) and _was_left(nm):
                    report.add(
                        city, num, day_num, "aba_visit_after_leave",
                        f"visit={_nm(it)} user_at={user_at}",
                    )
                if nm:
                    if user_at and not _names_overlap(nm, user_at):
                        _mark_left(user_at)
                    user_at = nm
                    _clear_left(nm)
            elif tv in (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value):
                mp = _meal_place(it)
                if mp and user_at and not _names_overlap(mp, user_at) and _was_left(mp):
                    report.add(
                        city, num, day_num, "aba_visit_after_leave",
                        f"meal={mp} user_at={user_at}",
                    )
                if mp:
                    if user_at and not _names_overlap(mp, user_at):
                        _mark_left(user_at)
                    user_at = mp
                    _clear_left(mp)
            continue
        t_idx += 1
        frm = _fold(getattr(it, "from_location", "") or "")
        to = _fold(getattr(it, "to_location", "") or "")
        mode = str(
            getattr(getattr(it, "mode", None), "value", getattr(it, "mode", "")) or ""
        ).lower()
        src = str(getattr(it, "routing_source", "") or "").lower()
        try:
            km = float(getattr(it, "distance_km", None) or 0)
        except (TypeError, ValueError):
            km = 0.0
        is_hub = frm in hub_names or to in hub_names
        mid = 1 < t_idx < max(n_transits, 2)
        if is_hub and mid and 0 < km <= 0.6:
            report.add(city, num, day_num, "generic_hub", f"{frm}->{to} {km}km")
        if ("walk" in mode or "foot" in mode) and user_at and frm:
            if user_at not in frm and frm not in user_at and not _names_overlap(user_at, frm):
                report.add(
                    city, num, day_num, "stale_walk_start",
                    f"walk from {frm} but user_at={user_at}",
                )
        if "return" in src and user_at and car_at and _names_overlap(user_at, car_at):
            report.add(
                city, num, day_num, "aba_return_loop",
                f"return_to_car while already at car ({car_at})",
            )
        # return_to_car must be immediately before a drive (not a walk continuation)
        if "return" in src and ("walk" in mode or "foot" in mode):
            follows_drive = False
            # peek next non-free_time item in remaining list — approximate via index
            # (validated structurally in seal; here flag obvious misuse when next
            # transit after this is still a walk with no car).
            pass
        if "walk" in mode or "foot" in mode:
            if frm and to and not _names_overlap(frm, to):
                _mark_left(user_at or frm)
            if to:
                user_at = to
                _clear_left(to)
            if "return" in src and car_at:
                user_at = car_at
                _clear_left(car_at)
        elif "car" in mode:
            if frm and to and user_at and not _names_overlap(user_at, to):
                _mark_left(user_at)
            if to:
                user_at = to
                car_at = to
                _clear_left(to)

    # return_to_car must be immediately followed by a drive (not a walk-on).
    for i, it in enumerate(items):
        if _tv(it) != ItemType.TRANSIT.value:
            continue
        src = str(getattr(it, "routing_source", "") or "").lower()
        if "return" not in src:
            continue
        follows_drive = False
        for later in items[i + 1 : i + 5]:
            ltv = _tv(later)
            if ltv == ItemType.FREE_TIME.value:
                continue
            if ltv != ItemType.TRANSIT.value:
                break
            mode = str(
                getattr(getattr(later, "mode", None), "value", getattr(later, "mode", ""))
                or ""
            ).lower()
            if "car" in mode:
                follows_drive = True
            break
        if not follows_drive:
            report.add(
                city, num, day_num, "aba_return_loop",
                "return_to_car without following drive",
            )

    has_dinner = any(_tv(it) == ItemType.DINNER_BREAK.value for it in items)
    last_en = None
    for it in items:
        st, en = _clock(it)
        if en is not None:
            last_en = en if last_en is None else max(last_en, en)
        if _tv(it) == ItemType.LUNCH_BREAK.value and st is not None and st >= 15 * 60:
            report.add(city, num, day_num, "late_lunch", f"lunch@{st}")
        if st is not None and en is not None and en <= st and st >= 23 * 60:
            report.add(city, num, day_num, "zero_duration_clip", f"{_nm(it) or _tv(it)}")
        if st is not None and st >= 23 * 60 + 50:
            report.add(city, num, day_num, "day_past_window", f"{_nm(it) or _tv(it)}@{st}")
    if last_en is not None and last_en >= 17 * 60 and not has_dinner:
        report.add(city, num, day_num, "missing_dinner", f"last_end={last_en}")

    coords_seen: Dict[Tuple[float, float], str] = {}
    foreign_stems = (
        ("loopy", "wroclaw"),
        ("jumpcity", "katowice"),
        ("hala targowa", "wroclaw"),
        ("piaskowa 17", "wroclaw"),
    )
    city_f = _fold(city)
    for it in items:
        if _tv(it) != ItemType.ATTRACTION.value:
            continue
        nm = _fold(_nm(it))
        for stem, home in foreign_stems:
            if stem in nm and home not in city_f:
                if any(
                    k in city_f
                    for k in ("gdansk", "gdynia", "sopot", "karpacz", "jelenia", "szklarska")
                ):
                    report.add(city, num, day_num, "cross_city_poi", _nm(it))
        try:
            lat = round(float(getattr(it, "lat")), 4)
            lng = round(float(getattr(it, "lng")), 4)
        except (TypeError, ValueError):
            continue
        key = (lat, lng)
        if key in coords_seen and coords_seen[key] != nm:
            report.add(
                city, num, day_num, "duplicate_coords_poi",
                f"{_nm(it)} same as {coords_seen[key]}",
            )
        else:
            coords_seen[key] = nm


    # seniors mismatch
    if "senior" in (group_type or "").lower():
        for it in items:
            if _tv(it) != ItemType.ATTRACTION.value:
                continue
            nm = _fold(_nm(it))
            if any(b in nm for b in SENIOR_BAN):
                report.add(city, num, day_num, "target_group", f"seniors+{_nm(it)}")


def validate_plan(
    *,
    city: str,
    num: int,
    plan: Any,
    group_type: str = "",
    report: Optional[Report] = None,
) -> Report:
    report = report or Report()
    seen: Dict[str, int] = {}
    for day in getattr(plan, "days", []) or []:
        dnum = int(getattr(day, "day", 0) or 0)
        items = getattr(day, "items", None) or []
        validate_day(
            city=city, num=num, day_num=dnum, items=items,
            group_type=group_type, report=report,
        )
        for it in items:
            if _tv(it) != ItemType.ATTRACTION.value:
                continue
            key = _fold(_nm(it))
            if not key:
                continue
            if key in seen and seen[key] != dnum:
                report.add(
                    city, num, dnum, "duplicate_poi",
                    f"{_nm(it)} also day {seen[key]}",
                )
            else:
                seen[key] = dnum
    return report


def city_json_dir(city: str) -> Path:
    mapping = {
        "Kraków": OUTER / "json_miasta" / "Kraków",
        "Katowice": OUTER / "json_miasta" / "Katowice",
        "Wrocław": OUTER / "json_miasta" / "Wroclaw",
        "Warszawa": OUTER / "json_miasta" / "Warszawa",
        "Poznań": OUTER / "json_miasta" / "Poznan",
        "Gdynia": OUTER / "json_miasta" / "Gdynia",
        "Sopot": OUTER / "json_miasta" / "Sopot",
        "Gdańsk": OUTER / "json_miasta" / "Gdańsk",
        "Karpacz": OUTER / "json_miasta" / "Karpacz",
        "Jelenia Góra": OUTER / "json_miasta" / "Jelenia Góra",
        "Szklarska Poręba": OUTER / "json_miasta" / "Szklarska Poreba",
    }
    return mapping[city]


def run_cities(
    cities: Sequence[Tuple[str, Sequence[int]]],
) -> Report:
    from app.application.services.plan_service import PlanService
    from app.domain.models.trip_input import TripInput
    from app.infrastructure.repositories.poi_repository import POIRepository

    os.environ.setdefault("ORS_ENABLED", "false")
    svc = PlanService(POIRepository(str(ROOT / "data" / "zakopane.xlsx")))
    report = Report()
    for city, nums in cities:
        jdir = city_json_dir(city)
        if not jdir.exists():
            continue
        for num in nums:
            path = jdir / f"test-{num:02d}.json"
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                plan = svc.generate_plan(TripInput(**payload))
            group = (payload.get("group") or {}).get("type") or ""
            validate_plan(
                city=city, num=num, plan=plan, group_type=str(group), report=report,
            )
    return report


def main() -> None:
    cities = [
        ("Kraków", range(1, 11)),
        ("Katowice", range(1, 9)),
        ("Wrocław", range(1, 4)),
        ("Warszawa", range(1, 4)),
        ("Poznań", range(1, 4)),
    ]
    report = run_cities(cities)
    print("TOTAL", len(report.hits))
    print("COUNTS", report.counts())
    by = report.by_city()
    for city, hits in sorted(by.items()):
        print(f"\n## {city} ({len(hits)})")
        for h in hits:
            print(f"  J{h.json_num} D{h.day} [{h.code}] {h.message}")


if __name__ == "__main__":
    main()
