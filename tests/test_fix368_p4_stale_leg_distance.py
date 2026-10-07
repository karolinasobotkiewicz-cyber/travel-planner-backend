"""FIX #368 P4 ? recompute stale walk/drive distance+duration from coords."""
from __future__ import annotations

from scripts.plan_quality_validator import Report, validate_day


def _svc():
    from app.application.services.plan_service import PlanService
    from app.infrastructure.repositories.poi_repository import POIRepository
    return PlanService(POIRepository("data/zakopane.xlsx"))


def _tv(it):
    t = getattr(it, "type", None)
    return t.value if hasattr(t, "value") else str(t or "")


def test_bulwary_obwarzanek_stale_short_leg_recomputed():
    """UAT: declared 0.275 km while endpoints are ~2 km apart."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.infrastructure.routing.haversine import haversine_km

    svc = _svc()
    # Approx Krakow Bulwary vs Obwarzanek Museum area (~2km)
    bul = (50.0545, 19.9330)
    obw = (50.0615, 19.9375)
    real = haversine_km(bul[0], bul[1], obw[0], obw[1])
    assert real >= 0.8, real

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Bulwary Wislane",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=bul[0], lng=bul[1], city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Bulwary Wislane",
            to_location="Muzeum Obwarzanka", mode=TransitMode.WALK,
            distance_km=0.275,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="o", name="Muzeum Obwarzanka",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="11:45", duration_min=40,
            lat=obw[0], lng=obw[1], city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [it for it in out if _tv(it) == "transit"]
    assert legs, legs
    leg = next(
        it for it in legs
        if "obwarz" in (getattr(it, "to_location", "") or "").lower()
        or "obwarz" in (getattr(it, "from_location", "") or "").lower()
    )
    km = float(getattr(leg, "distance_km", 0) or 0)
    assert km >= 0.8, km
    assert int(getattr(leg, "duration_min", 0) or 0) >= 10


def test_rogalinek_nooks_long_understated_becomes_car():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    # ~16 km apart-ish (Rogalin-ish vs Poznan center)
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="r", name="Rogalinek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=52.2444, lng=16.9000, city="Poznan",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:10",
            duration_min=10, from_location="Rogalinek",
            to_location="NOOKS", mode=TransitMode.WALK, distance_km=0.4,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="n", name="NOOKS",
            description_short="x", why_selected=["x"],
            start_time="11:10", end_time="12:00", duration_min=50,
            lat=52.406, lng=16.925, city="Poznan",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Poznan", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [
        it for it in out
        if _tv(it) == "transit"
        and "nooks" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert legs, legs
    leg = legs[0]
    km = float(getattr(leg, "distance_km", 0) or 0)
    assert km >= 10.0, km
    mode = str(getattr(getattr(leg, "mode", None), "value", getattr(leg, "mode", ""))).lower()
    assert "car" in mode, mode


def test_botaniczny_sorrento_stale_leg_recomputed():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Ogrod Botaniczny",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.063, lng=19.955, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Ogrod Botaniczny",
            to_location="Sorrento", mode=TransitMode.WALK, distance_km=0.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="s", name="Sorrento",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="12:00", duration_min=55,
            lat=50.052, lng=19.940, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [
        it for it in out
        if _tv(it) == "transit"
        and "sorrento" in (getattr(it, "to_location", "") or "").lower()
    ]
    assert legs
    assert float(getattr(legs[0], "distance_km", 0) or 0) >= 0.8


def test_wroclaw_stale_leg_not_recomputed_by_seal():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Rynek",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=51.11, lng=17.03, city="Wroclaw",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Rynek",
            to_location="Hala Stulecia", mode=TransitMode.WALK, distance_km=0.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Hala Stulecia",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="12:00", duration_min=55,
            lat=51.107, lng=17.077, city="Wroclaw",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Wroclaw", "has_car": True}
    out = svc._seal_fix367_uat_day(items, ctx, day_num=1)
    legs = [it for it in out if _tv(it) == "transit"]
    assert legs and float(getattr(legs[0], "distance_km", 0) or 0) == 0.2


def test_validator_flags_stale_leg_distance():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Bulwary Wislane",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.0545, lng=19.9330, city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Bulwary Wislane",
            to_location="Muzeum Obwarzanka", mode=TransitMode.WALK,
            distance_km=0.275,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Muzeum Obwarzanka",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="11:45", duration_min=40,
            lat=50.0615, lng=19.9375, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    report = Report()
    validate_day(city="Krakow", num=1, day_num=1, items=items, report=report)
    codes = {h.code for h in report.hits}
    assert "stale_leg_distance" in codes, codes



def _ends_before_next(items):
    """Return True when no timed item end exceeds the next item's start."""
    from app.application.services.plan_service import time_to_minutes

    timed = []
    for it in items:
        tv = _tv(it)
        if tv in ("day_start", "day_end"):
            continue
        st = getattr(it, "start_time", None)
        en = getattr(it, "end_time", None)
        if not st:
            continue
        timed.append((time_to_minutes(st), time_to_minutes(en) if en else None, it))
    timed.sort(key=lambda x: x[0])
    for i in range(len(timed) - 1):
        en = timed[i][1]
        nxt = timed[i + 1][0]
        if en is not None and en > nxt:
            return False, timed[i][2], timed[i + 1][2], en, nxt
    return True, None, None, None, None


def test_p4_recompute_never_overlaps_next_item():
    """Regression: lengthening a stale leg must not push end past next start."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.application.services.plan_service import time_to_minutes

    svc = _svc()
    # ~2 km apart, only 5 min declared window before next attraction.
    bul = (50.0545, 19.9330)
    obw = (50.0615, 19.9375)
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Bulwary Wislane",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=bul[0], lng=bul[1], city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Bulwary Wislane",
            to_location="Muzeum Obwarzanka", mode=TransitMode.WALK,
            distance_km=0.275,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="o", name="Muzeum Obwarzanka",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="11:45", duration_min=40,
            lat=obw[0], lng=obw[1], city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix368_p4_recompute_legs(items, ctx, day_num=1)
    ok, a, b, en, nxt = _ends_before_next(out)
    assert ok, f"overlap {en}>{nxt}: {getattr(a,'name',a)} vs {getattr(b,'name',b)}"
    legs = [it for it in out if _tv(it) == "transit"]
    assert legs
    # Distance refreshed; clocks stay non-overlapping (cascade or cap).
    assert float(getattr(legs[0], "distance_km", 0) or 0) >= 0.8
    leg_en = time_to_minutes(getattr(legs[0], "end_time"))
    next_attr = next(it for it in out if _tv(it) == "attraction"
                     and "obwarz" in (getattr(it, "name", "") or "").lower())
    assert leg_en <= time_to_minutes(next_attr.start_time)


def test_p4_recompute_cascades_when_room_too_small():
    """When honest duration exceeds the free window, later items shift."""
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )
    from app.application.services.plan_service import time_to_minutes

    svc = _svc()
    a = (50.0545, 19.9330)
    b = (50.0700, 19.9500)  # farther ~2+ km
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Place A",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=a[0], lng=a[1], city="Krakow",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:05",
            duration_min=5, from_location="Place A",
            to_location="Place B", mode=TransitMode.WALK, distance_km=0.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Place B",
            description_short="x", why_selected=["x"],
            start_time="11:05", end_time="11:45", duration_min=40,
            lat=b[0], lng=b[1], city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True, "day_end": "19:00"}
    out = svc._seal_fix368_p4_recompute_legs(items, ctx, day_num=1)
    ok, *_ = _ends_before_next(out)
    assert ok
    attr_b = next(it for it in out if getattr(it, "name", "") == "Place B")
    # Cascaded past the original 11:05 tight window.
    assert time_to_minutes(attr_b.start_time) >= time_to_minutes("11:05")
    leg = next(it for it in out if _tv(it) == "transit")
    assert float(getattr(leg, "distance_km", 0) or 0) >= 1.0
    assert time_to_minutes(leg.end_time) <= time_to_minutes(attr_b.start_time)


def test_hop_ledger_repair_drops_self_and_rewrites_from():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, ItemType, TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Wawel",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.054, lng=19.935, city="Krakow",
        ),
        # from_mismatch: claims from elsewhere while user is at Wawel
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:00", end_time="11:15",
            duration_min=15, from_location="Rynek Glowny",
            to_location="Kazimierz", mode=TransitMode.WALK, distance_km=1.2,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="k", name="Kazimierz",
            description_short="x", why_selected=["x"],
            start_time="11:15", end_time="12:00", duration_min=45,
            lat=50.051, lng=19.945, city="Krakow",
        ),
        # self_hop
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="12:00", end_time="12:05",
            duration_min=5, from_location="Kazimierz",
            to_location="Kazimierz", mode=TransitMode.WALK, distance_km=0.1,
        ),
        DayEndItem(time="19:00"),
    ]
    ctx = {"requested_city": "Krakow", "has_car": True}
    out = svc._seal_fix368_repair_hop_ledger(items, ctx, day_num=1)
    legs = [it for it in out if _tv(it) == "transit"]
    assert not any(
        _place_match(getattr(it, "from_location", ""), getattr(it, "to_location", ""))
        for it in legs
    ), legs
    # from rewritten to Wawel
    first = next(
        it for it in legs
        if "kazimierz" in (getattr(it, "to_location", "") or "").lower()
    )
    assert "wawel" in (getattr(first, "from_location", "") or "").lower()


def _place_match(a, b):
    from app.application.services import plan_service as ps
    return ps._place_names_match(a or "", b or "")


def test_overlap_repair_clips_free_time_and_cascades():
    from app.domain.models.plan import (
        AttractionItem, DayEndItem, DayStartItem, FreeTimeItem, ItemType,
        TransitItem, TransitMode,
    )

    svc = _svc()
    items = [
        DayStartItem(time="09:00"),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="a", name="Place A",
            description_short="x", why_selected=["x"],
            start_time="10:00", end_time="11:00", duration_min=60,
            lat=50.05, lng=19.93, city="Krakow",
        ),
        FreeTimeItem.model_construct(
            type=ItemType.FREE_TIME, start_time="10:45", end_time="11:15",
            duration_min=30, description="pad",
        ),
        TransitItem.model_construct(
            type=ItemType.TRANSIT, start_time="11:10", end_time="11:25",
            duration_min=15, from_location="Place A",
            to_location="Place B", mode=TransitMode.WALK, distance_km=1.0,
        ),
        AttractionItem.model_construct(
            type=ItemType.ATTRACTION, poi_id="b", name="Place B",
            description_short="x", why_selected=["x"],
            start_time="11:20", end_time="12:00", duration_min=40,
            lat=50.06, lng=19.94, city="Krakow",
        ),
        DayEndItem(time="19:00"),
    ]
    out = svc._seal_fix368_repair_overlaps(
        items, {"requested_city": "Krakow"}, day_num=1,
    )
    ok, *_rest = _ends_before_next(out)
    assert ok, "overlap remains after repair"
