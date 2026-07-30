"""Full client readiness audit — FIX #251 quality gate."""
from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

logging.disable(logging.CRITICAL)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.services.plan_client_audit import (  # noqa: E402
    audit_before_day_start,
    audit_budget_exceeded,
    audit_large_idle_gaps,
    audit_missing_transits,
    audit_orphan_transits,
    audit_timeline_overlaps,
    audit_transit_routing,
    time_min,
)
from app.application.services.plan_service import PlanService  # noqa: E402
from app.domain.models.plan import ItemType  # noqa: E402
from app.domain.models.trip_input import TripInput  # noqa: E402
from app.domain.planner.engine import haversine_distance, is_open  # noqa: E402
from app.infrastructure.repositories import POIRepository  # noqa: E402

JSON_ROOT = ROOT.parent / "json_miasta"
# Primary client cities + Poznań (recent feedback rounds)
CITIES = ("Wrocław", "Warszawa", "Kraków", "Katowice", "Poznań")
OUT = ROOT / "fix251_client_readiness_report.json"

# Windows consoles often use cp1252 — force UTF-8 for Polish city names.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_EN_MARKERS = (
    "matches your",
    "perfect for",
    "great for",
    "budget-friendly",
    "low-crowd",
    "peaceful atmosphere",
    "cultural experience",
    "relaxing activity",
    "active adventure",
    "fits your",
    "highly recommended by locals",
    "must-see attraction in",
    "good value for your budget",
    "free entry (perfect",
    "popular attraction (fits",
    "romantic winter",
    "winter experience",
    "local experience",
    "local tradition",
)


def _tv(it) -> str:
    t = getattr(it, "type", None)
    return str(t.value if hasattr(t, "value") else t)


def audit_plan(plan, payload: dict, label: str, poi_by_id: dict) -> dict:
    day_start = payload.get("daily_time_window", {}).get("start", "09:00")
    daily_limit = (payload.get("budget") or {}).get("daily_limit")
    cats: dict[str, list] = defaultdict(list)

    for day in plan.days:
        items = day.items or []
        prefix = f"{label} day{day.day}: "

        for msg in audit_before_day_start(items, day_start):
            cats["before_day_start"].append(prefix + msg)
        for msg in audit_timeline_overlaps(items):
            cats["overlaps"].append(prefix + msg)
        for msg in audit_missing_transits(items):
            cats["missing_transits"].append(prefix + msg)
        for msg in audit_orphan_transits(items):
            cats["orphan_transits"].append(prefix + msg)
        for msg in audit_large_idle_gaps(items):
            cats["idle_gaps"].append(prefix + msg)
        for msg in audit_budget_exceeded(items, daily_limit):
            cats["budget_exceeded"].append(prefix + msg)
        for msg in audit_transit_routing(items):
            cats["transit_routing"].append(prefix + msg)

        # Closed / out of season via is_open
        ctx_date = payload.get("start_date") or payload.get("dates", {}).get("start")
        # TripInput uses start_date usually
        from datetime import datetime, timedelta

        start = payload.get("start_date")
        if not start and payload.get("trip_dates"):
            start = payload["trip_dates"].get("start")
        if not start:
            start = payload.get("dates", {}).get("from") or payload.get("date")
        day_date = None
        if start:
            try:
                base = datetime.strptime(str(start)[:10], "%Y-%m-%d")
                day_date = base + timedelta(days=day.day - 1)
            except Exception:
                day_date = None

        # Duplicate names same day
        seen = set()
        for it in items:
            if _tv(it) != ItemType.ATTRACTION.value:
                continue
            nm = (getattr(it, "name", "") or "").strip().lower()
            pid = getattr(it, "poi_id", "") or ""
            key = pid or nm
            if key and key in seen:
                cats["duplicates"].append(prefix + f"duplicate {getattr(it, 'name', '?')}")
            if key:
                seen.add(key)

            # empty copy
            desc = (getattr(it, "description_short", None) or "").strip()
            tip = getattr(it, "pro_tip", None)
            if not desc:
                cats["empty_description"].append(prefix + getattr(it, "name", "?"))
            if tip is None or str(tip).strip() == "":
                cats["empty_pro_tip"].append(prefix + getattr(it, "name", "?"))

            # English why_selected
            for reason in getattr(it, "why_selected", None) or []:
                rl = str(reason).lower()
                if any(m in rl for m in _EN_MARKERS):
                    cats["english_why_selected"].append(prefix + f"{getattr(it, 'name', '?')}: {reason}")

            # closed check
            if day_date is not None:
                poi = poi_by_id.get(pid) or {"name": getattr(it, "name", ""), "tags": []}
                st = getattr(it, "start_time", None)
                dur = int(getattr(it, "duration_min", 0) or 60)
                if st and poi.get("opening_hours") or poi.get("opening_hours_seasonal"):
                    ctx = {
                        "date": day_date,
                        "season": (
                            "winter" if day_date.month in (12, 1, 2)
                            else "spring" if day_date.month in (3, 4, 5)
                            else "summer" if day_date.month in (6, 7, 8)
                            else "autumn"
                        ),
                    }
                    try:
                        if not is_open(poi, time_min(st), dur, ctx["season"], ctx):
                            cats["closed_attraction"].append(
                                prefix + f"{getattr(it, 'name', '?')} at {st}"
                            )
                    except Exception:
                        pass

        # Implausible transit speed (e.g. 6km / 5min)
        for it in items:
            if _tv(it) != ItemType.TRANSIT.value:
                continue
            dur = int(getattr(it, "duration_min", 0) or 0)
            dist = getattr(it, "distance_km", None)
            if dist is None:
                # try geometry endpoints via lat of neighboring attrs — skip if unknown
                continue
            try:
                dist = float(dist)
            except (TypeError, ValueError):
                continue
            if dist >= 0.8 and dur > 0:
                speed = dist / (dur / 60.0)  # km/h
                mode = str(getattr(it, "mode", "") or "").lower()
                max_speed = 8 if "walk" in mode else 55
                if speed > max_speed:
                    cats["implausible_transit"].append(
                        prefix
                        + f"{getattr(it, 'from_location', '?')}->{getattr(it, 'to_location', '?')} "
                        f"{dist:.1f}km/{dur}min ({speed:.0f} km/h)"
                    )

        # Meal not on route: lunch/dinner with suggestions but no transit to restaurant
        for i, it in enumerate(items):
            if _tv(it) not in (ItemType.LUNCH_BREAK.value, ItemType.DINNER_BREAK.value):
                continue
            sugs = getattr(it, "suggestions", None) or []
            if not sugs:
                cats["meal_no_suggestions"].append(prefix + _tv(it))
                continue
            rname = (getattr(sugs[0], "name", None) or "").strip()
            if not rname:
                continue
            # any transit mentioning restaurant nearby?
            window = items[max(0, i - 2) : i + 3]
            hit = False
            for w in window:
                if _tv(w) != ItemType.TRANSIT.value:
                    continue
                fr = (getattr(w, "from_location", "") or "")
                to = (getattr(w, "to_location", "") or "")
                if rname in fr or rname in to or fr.lower() == rname.lower() or to.lower() == rname.lower():
                    hit = True
                    break
            if not hit:
                cats["meal_not_on_route"].append(prefix + rname)

        # Budget display consistency: sum cost_estimate vs warning
        day_cost = 0.0
        for it in items:
            try:
                day_cost += float(getattr(it, "cost_estimate", None) or 0)
            except (TypeError, ValueError):
                pass
        if daily_limit and day_cost > float(daily_limit) + 0.5:
            # already covered by audit_budget_exceeded, keep count
            pass

    # Stale / wrong plan warnings for budget
    for w in getattr(plan, "warnings", None) or []:
        if isinstance(w, dict) and w.get("type") == "budget_exceeded":
            # verify actual day cost matches warning
            dnum = w.get("day")
            actual_claimed = w.get("actual_cost")
            for day in plan.days:
                if day.day != dnum:
                    continue
                real = sum(float(getattr(it, "cost_estimate", None) or 0) for it in (day.items or []))
                if actual_claimed is not None and abs(float(actual_claimed) - real) > 5:
                    cats["budget_warning_mismatch"].append(
                        f"{label} day{dnum}: warning={actual_claimed} real={int(real)}"
                    )

    return dict(cats)


def main():
    excel = ROOT / "data" / "multi_city_attractions.xlsx"
    svc = PlanService(POIRepository(str(excel)))
    # Build a soft poi lookup once via empty generate is heavy — rebuild per city from loader
    from app.infrastructure.repositories.load_multi_city import load_multi_city_poi

    results = []
    totals = Counter()
    by_city = defaultdict(Counter)

    for city in CITIES:
        folder = JSON_ROOT / city
        if not folder.is_dir():
            continue
        try:
            pois = load_multi_city_poi(str(excel), [city])
        except Exception:
            pois = []
        poi_by_id = {p.get("id"): p for p in pois if p.get("id")}

        for path in sorted(folder.glob("test-*.json")):
            label = f"{city}/{path.name}"
            print(f"=== {label} ===", flush=True)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                plan = svc.generate_plan(TripInput(**payload))
                cats = audit_plan(plan, payload, label, poi_by_id)
                n_issues = sum(len(v) for v in cats.values())
                entry = {
                    "label": label,
                    "city": city,
                    "file": path.name,
                    "days": len(plan.days),
                    "issue_count": n_issues,
                    "categories": {k: v for k, v in cats.items() if v},
                    "ok": n_issues == 0,
                }
                results.append(entry)
                for k, v in cats.items():
                    totals[k] += len(v)
                    by_city[city][k] += len(v)
                print(f"  issues={n_issues} cats={list(cats.keys())}", flush=True)
            except Exception as e:
                results.append({
                    "label": label,
                    "city": city,
                    "file": path.name,
                    "error": str(e),
                    "ok": False,
                    "issue_count": 1,
                    "categories": {"crash": [str(e)]},
                })
                totals["crash"] += 1
                print(f"  CRASH: {e}", flush=True)

    summary = {
        "total_fixtures": len(results),
        "passed": sum(1 for r in results if r.get("ok")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "issue_totals": dict(totals),
        "by_city": {c: dict(cnt) for c, cnt in by_city.items()},
        "failed_labels": [r["label"] for r in results if not r.get("ok")],
        "results": results,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n===== SUMMARY =====", flush=True)
    print(f"passed {summary['passed']}/{summary['total_fixtures']}", flush=True)
    print(json.dumps(summary["issue_totals"], ensure_ascii=False, indent=2), flush=True)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
