"""
Transit Continuity Test — 10 Client Test JSONs (Testy_Klientki)

Checks per day plan:
  1. No consecutive duplicate transfer items
  2. All adjacent attraction pairs with distance > 2.0km have a transfer between them
  3. No backward time progression in the timeline
  4. No overlapping items (start < prev_end)
  5. No duplicate (from, to) transfer pairs within the same day [FIX #147]

Usage:
    cd travel-planner-backend
    python test_transit_continuity_klientka.py
"""
import sys
import os
import json
from pathlib import Path

# Ensure imports work from project root
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from app.domain.planner.engine import (
    build_day,
    haversine_distance,
    WALK_THRESHOLD_KM,
)
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

# ─── Paths ────────────────────────────────────────────────────────────────────
TESTS_DIR = BACKEND_DIR.parent / "Testy_Klientki"
DATA_FILE = BACKEND_DIR / "data" / "zakopane.xlsx"

# We test all 10 base Zakopane tests (test-01 … test-10)
TEST_NUMBERS = list(range(1, 11))

# POI distance threshold to require transit (km) — aligns with engine logic
TRANSIT_DISTANCE_THRESHOLD_KM = 2.0


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_test_json(test_number: int) -> dict:
    path = TESTS_DIR / f"test-{test_number:02d}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _map_season(start_date_str: str) -> str:
    """Infer season from start_date string (YYYY-MM-DD)."""
    try:
        month = int(start_date_str.split("-")[1])
        if month in (12, 1, 2):
            return "winter"
        elif month in (3, 4, 5):
            return "spring"
        elif month in (6, 7, 8):
            return "summer"
        else:
            return "autumn"
    except Exception:
        return "winter"


def json_to_engine_params(test_data: dict) -> dict:
    """Convert client test JSON dict → engine params (user, context, day_start, day_end)."""
    group = test_data.get("group", {})
    budget = test_data.get("budget", {})
    daily_time = test_data.get("daily_time_window", {})
    trip = test_data.get("trip_length", {})
    transport_modes = test_data.get("transport_modes", ["car"])

    user = {
        "target_group": group.get("type", "couples"),
        "children_age": group.get("children_age"),
        "crowd_tolerance": group.get("crowd_tolerance", 1),
        "budget": budget.get("level", 2),
        "daily_limit": budget.get("daily_limit", 500),
        "group_size": group.get("size", 2),
        "preferences": test_data.get("preferences", []),
        "travel_style": test_data.get("travel_style", "balanced"),
    }

    context = {
        "season": _map_season(trip.get("start_date", "2026-02-20")),
        "region_type": test_data.get("location", {}).get("region_type", "mountain"),
        "transport": "car" if "car" in transport_modes else "public",
        "has_car": "car" in transport_modes,
        "date": (2026, 2, 20, 4),  # Friday — safe default
    }

    return {
        "user": user,
        "context": context,
        "day_start": daily_time.get("start", "09:00"),
        "day_end": daily_time.get("end", "19:00"),
        "days": trip.get("days", 1),
    }


def item_name(item: dict) -> str:
    """Return a short label for a plan item for error messages."""
    t = item.get("type", "?")
    if t == "attraction":
        return f"attraction({item.get('name', item.get('poi', {}).get('name', '?'))})"
    if t == "transfer":
        return f"transfer({item.get('from', '?')}→{item.get('to', '?')})"
    return f"{t}({item.get('name', '')})"


# ─── Transit Continuity Validators ────────────────────────────────────────────

def check_no_consecutive_transfers(plan: list) -> list:
    """Return issues where two consecutive transfer items appear."""
    issues = []
    for i in range(len(plan) - 1):
        if plan[i].get("type") == "transfer" and plan[i + 1].get("type") == "transfer":
            issues.append(
                f"  CONSECUTIVE TRANSFERS at pos {i}/{i+1}: "
                f"[{item_name(plan[i])}] then [{item_name(plan[i+1])}]"
            )
    return issues


def check_distant_pois_have_transit(plan: list) -> list:
    """Return issues where distant attraction pairs (>2km) lack a transfer."""
    issues = []
    attractions = [(idx, it) for idx, it in enumerate(plan) if it.get("type") == "attraction"]

    for k in range(len(attractions) - 1):
        idx1, attr1 = attractions[k]
        idx2, attr2 = attractions[k + 1]

        poi1 = attr1.get("poi", {})
        poi2 = attr2.get("poi", {})
        lat1, lng1 = poi1.get("lat"), poi1.get("lng")
        lat2, lng2 = poi2.get("lat"), poi2.get("lng")

        if not all([lat1, lng1, lat2, lng2]):
            continue  # Can't compute distance — skip

        dist = haversine_distance(lat1, lng1, lat2, lng2)

        if dist > TRANSIT_DISTANCE_THRESHOLD_KM:
            # Is there any transfer item between idx1 and idx2?
            has_transfer = any(
                plan[j].get("type") == "transfer"
                for j in range(idx1 + 1, idx2)
            )
            if not has_transfer:
                issues.append(
                    f"  MISSING TRANSIT: {poi1.get('name','?')} → {poi2.get('name','?')} "
                    f"({dist:.2f}km > {TRANSIT_DISTANCE_THRESHOLD_KM}km threshold)"
                )
    return issues


def check_time_continuity(plan: list) -> list:
    """Return issues where the timeline goes backward or items overlap."""
    issues = []
    timed_items = [
        (i, it) for i, it in enumerate(plan)
        if it.get("start_time") and it.get("end_time")
    ]

    prev_end_min = None
    for i, item in timed_items:
        try:
            start_min = time_to_minutes(item["start_time"])
            end_min = time_to_minutes(item["end_time"])
        except Exception:
            continue

        # Internal sanity: end >= start
        if end_min < start_min:
            issues.append(
                f"  BACKWARD ITEM: {item_name(item)} "
                f"{item['start_time']}→{item['end_time']}"
            )

        # Overlap with previous item
        if prev_end_min is not None and start_min < prev_end_min - 1:
            issues.append(
                f"  TIMELINE OVERLAP at pos {i}: {item_name(item)} "
                f"starts {item['start_time']}, prev ended {minutes_to_time(prev_end_min)}"
            )

        prev_end_min = end_min

    return issues


def check_no_duplicate_transfer_destination(plan: list) -> list:
    """Return issues where a transfer destination was just visited."""
    issues = []
    visited_names: list = []  # ordered list of attraction names

    for item in plan:
        if item.get("type") == "attraction":
            visited_names.append(item.get("name", ""))
        elif item.get("type") == "transfer":
            dest = item.get("to", "")
            # If dest is the very last visited attraction → pointless transit
            if visited_names and dest == visited_names[-1]:
                issues.append(
                    f"  TRANSFER TO JUST-VISITED: destination '{dest}' was just the previous attraction"
                )
    return issues


def check_no_duplicate_transfer_pair(plan: list) -> list:
    """Return issues where the same (from, to) transfer pair appears more than once in a day.
    FIX #147: This verifies the deduplication added in FIX #147/#128/#142/#144 works correctly.
    """
    from collections import Counter
    issues = []
    pairs = [
        (it.get("from", ""), it.get("to", ""))
        for it in plan
        if it.get("type") == "transfer"
    ]
    dup = {k: v for k, v in Counter(pairs).items() if v > 1}
    for (fr, to), count in dup.items():
        issues.append(
            f"  DUPLICATE TRANSFER PAIR ({count}x): {fr} → {to}"
        )
    return issues


def validate_plan(plan: list) -> tuple:
    """Run all transit continuity checks. Returns (all_passed, issues_list)."""
    all_issues = []
    all_issues += check_no_consecutive_transfers(plan)
    all_issues += check_distant_pois_have_transit(plan)
    all_issues += check_time_continuity(plan)
    all_issues += check_no_duplicate_transfer_destination(plan)
    all_issues += check_no_duplicate_transfer_pair(plan)
    return (len(all_issues) == 0, all_issues)


# ─── Main Test Runner ─────────────────────────────────────────────────────────

def run_tests():
    print("=" * 70)
    print("TRANSIT CONTINUITY TEST — Testy_Klientki (test-01 … test-10)")
    print("=" * 70)

    # Load POI data once
    print(f"\nLoading Zakopane POIs from: {DATA_FILE}")
    try:
        pois = load_zakopane_poi(str(DATA_FILE))
        print(f"  → Loaded {len(pois)} POIs\n")
    except Exception as e:
        print(f"  ERROR loading POIs: {e}")
        sys.exit(1)

    # Build a simple pois_dict for reuse
    total_pass = 0
    total_fail = 0
    total_days = 0
    all_results = []

    for test_num in TEST_NUMBERS:
        test_name = f"test-{test_num:02d}"
        try:
            test_data = load_test_json(test_num)
        except FileNotFoundError:
            print(f"[SKIP] {test_name} — file not found")
            continue

        params = json_to_engine_params(test_data)
        days = params["days"]
        test_pass = True
        test_issues = []

        print(f"{'─'*60}")
        print(f"TEST: {test_name}  ({test_data['group']['type']}, {days} day(s), "
              f"style={test_data.get('travel_style','?')}, "
              f"prefs={test_data.get('preferences',[])})")

        for day_num in range(1, days + 1):
            total_days += 1
            ctx = dict(params["context"])
            # Shift date by day offset
            base_y, base_m, base_d, base_wd = ctx.get("date", (2026, 2, 20, 4))
            import datetime
            day_date = datetime.date(base_y, base_m, base_d) + datetime.timedelta(days=day_num - 1)
            ctx["date"] = (day_date.year, day_date.month, day_date.day, day_date.weekday())

            try:
                day_plan = build_day(
                    pois=pois,
                    user=params["user"],
                    context=ctx,
                    day_start=params["day_start"],
                    day_end=params["day_end"],
                )
            except Exception as e:
                msg = f"  Day {day_num}: BUILD_DAY ERROR — {e}"
                test_issues.append(msg)
                test_pass = False
                print(msg)
                continue

            day_ok, day_issues = validate_plan(day_plan)

            # Summary counts
            attractions_in_day = sum(1 for it in day_plan if it.get("type") == "attraction")
            transfers_in_day = sum(1 for it in day_plan if it.get("type") == "transfer")

            status = "PASS ✓" if day_ok else "FAIL ✗"
            print(f"  Day {day_num}: {status}  "
                  f"[{attractions_in_day} attractions, {transfers_in_day} transfers, "
                  f"{len(day_plan)} items total]")

            if day_issues:
                test_pass = False
                for iss in day_issues:
                    print(iss)
                    test_issues.append(iss)

        if test_pass:
            total_pass += 1
            print(f"  → RESULT: PASS ✓")
        else:
            total_fail += 1
            print(f"  → RESULT: FAIL ✗  ({len(test_issues)} issue(s))")

        all_results.append((test_name, test_pass, test_issues))

    # ─── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print(f"SUMMARY: {total_pass}/{len(TEST_NUMBERS)} tests PASSED   "
          f"({total_days} total day plans validated)")
    print("=" * 70)

    for test_name, passed, issues in all_results:
        mark = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {mark}  {test_name}")
        if not passed:
            for iss in issues:
                print(f"         {iss.strip()}")

    if total_fail == 0:
        print("\n🟢 ALL TESTS PASSED — ready to push to git")
    else:
        print(f"\n🔴 {total_fail} test(s) FAILED — review issues above before pushing")

    return total_fail == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
