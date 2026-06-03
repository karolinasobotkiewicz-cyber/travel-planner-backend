"""
Lunch Continuity Test — 10 Client Test JSONs (Testy_Klientki)

Checks per day plan:
  1. PRESENCE   — every day has exactly 1 lunch_break item
  2. TIMING     — lunch starts within valid window (group-specific):
                    family_kids → 12:00–13:30
                    seniors     → 12:00–13:30
                    others      → 12:00–14:30
  3. DURATION   — lunch_break lasts 25–90 min (not 5 min, not 2 hours)
  4. NO OVERLAP — no other item (attraction/transfer/free_time) overlaps with lunch
  5. SEQUENTIAL — no attraction is scheduled while lunch is in progress

Usage:
    cd travel-planner-backend
    python test_lunch_continuity_klientka.py
"""
import sys
import os
import json
import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from app.domain.planner.engine import build_day, LUNCH_EARLIEST, LUNCH_LATEST, LUNCH_DURATION_MIN
from app.domain.planner.time_utils import time_to_minutes, minutes_to_time
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

# ─── Paths ────────────────────────────────────────────────────────────────────
TESTS_DIR = BACKEND_DIR.parent / "Testy_Klientki"
DATA_FILE  = BACKEND_DIR / "data" / "zakopane.xlsx"
TEST_NUMBERS = list(range(1, 11))

# ─── Group-specific lunch windows (mirrors engine.py FIX #Problem9) ──────────
LUNCH_WINDOWS = {
    "family_kids": ("12:00", "13:30"),
    "seniors":     ("12:00", "13:30"),
    "_default":    ("12:00", "14:30"),
}
LUNCH_DURATION_MIN_FLOOR  = 25   # below this is suspicious
LUNCH_DURATION_MAX_FLOOR  = 90   # above this is suspicious

# Trail days: if the day contains a trail ending past TRAIL_LUNCH_GRACE_END,
# lunch is allowed up to TRAIL_LUNCH_LATEST_MIN (FIX #45 in engine: trails skip lunch cap)
TRAIL_LUNCH_GRACE_END    = "13:00"   # trail ends after this → "trail day" rules apply
TRAIL_LUNCH_LATEST_MIN   = "16:00"   # latest acceptable lunch start on a trail day


# ─── JSON → engine params (same as transit test) ──────────────────────────────

def _map_season(start_date_str: str) -> str:
    try:
        month = int(start_date_str.split("-")[1])
        if month in (12, 1, 2): return "winter"
        if month in (3, 4, 5):  return "spring"
        if month in (6, 7, 8):  return "summer"
        return "autumn"
    except Exception:
        return "winter"


def load_test_json(test_number: int) -> dict:
    path = TESTS_DIR / f"test-{test_number:02d}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_to_engine_params(test_data: dict) -> dict:
    group      = test_data.get("group", {})
    budget     = test_data.get("budget", {})
    daily_time = test_data.get("daily_time_window", {})
    trip       = test_data.get("trip_length", {})
    transport  = test_data.get("transport_modes", ["car"])

    user = {
        "target_group":   group.get("type", "couples"),
        "children_age":   group.get("children_age"),
        "crowd_tolerance":group.get("crowd_tolerance", 1),
        "budget":         budget.get("level", 2),
        "daily_limit":    budget.get("daily_limit", 500),
        "group_size":     group.get("size", 2),
        "preferences":    test_data.get("preferences", []),
        "travel_style":   test_data.get("travel_style", "balanced"),
    }
    context = {
        "season":      _map_season(trip.get("start_date", "2026-02-20")),
        "region_type": test_data.get("location", {}).get("region_type", "mountain"),
        "transport":   "car" if "car" in transport else "public",
        "has_car":     "car" in transport,
        "date":        (2026, 2, 20, 4),
    }
    return {
        "user":      user,
        "context":   context,
        "day_start": daily_time.get("start", "09:00"),
        "day_end":   daily_time.get("end",   "19:00"),
        "days":      trip.get("days", 1),
    }


# ─── Lunch continuity validators ──────────────────────────────────────────────

def _lunch_window(group_type: str):
    key = group_type if group_type in LUNCH_WINDOWS else "_default"
    lo, hi = LUNCH_WINDOWS[key]
    return time_to_minutes(lo), time_to_minutes(hi)


def check_lunch_presence(plan: list) -> list:
    """Every day plan must have exactly one lunch_break."""
    lunches = [it for it in plan if it.get("type") == "lunch_break"]
    if len(lunches) == 0:
        return ["  MISSING LUNCH: No lunch_break found in this day plan"]
    if len(lunches) > 1:
        times = [f"{it.get('start_time')}–{it.get('end_time')}" for it in lunches]
        return [f"  DUPLICATE LUNCH: {len(lunches)} lunch_break items found: {times}"]
    return []


def _is_trail_day(plan: list) -> bool:
    """True if the day contains a trail that ends past TRAIL_LUNCH_GRACE_END.

    Engine FIX #45 explicitly lets trails span past lunch time, so a day with
    a long mountain trail will inherently have a later lunch — this is correct
    behavior (hiker eats after the trail, not mid-hike).
    """
    grace_min = time_to_minutes(TRAIL_LUNCH_GRACE_END)
    for it in plan:
        if it.get("type") == "attraction":
            # The type field lives inside the nested 'poi' dict (item['poi']['type'])
            poi_obj  = it.get("poi") or {}
            poi_type = str(poi_obj.get("type", "")).lower()
            is_trail = (poi_type == "trail")
            if is_trail:
                try:
                    end_min = time_to_minutes(it["end_time"])
                    if end_min > grace_min:
                        return True
                except Exception:
                    pass
    return False


def check_lunch_timing(plan: list, group_type: str) -> list:
    """Lunch start must be within the group-specific valid window.

    Exception (FIX #45): trail days are allowed a later lunch up to
    TRAIL_LUNCH_LATEST_MIN — hiking a 5h mountain trail naturally pushes lunch
    past the standard window; eating after the trail is correct behavior.
    """
    issues = []
    lo_min, hi_min = _lunch_window(group_type)
    trail_day = _is_trail_day(plan)
    trail_latest_min = time_to_minutes(TRAIL_LUNCH_LATEST_MIN)

    for it in plan:
        if it.get("type") != "lunch_break":
            continue
        try:
            start_min = time_to_minutes(it["start_time"])
        except Exception:
            issues.append(f"  LUNCH TIMING: missing start_time on lunch_break item")
            continue

        if trail_day:
            # On a trail day: only flag if lunch is absurdly late (past 16:00)
            if start_min > trail_latest_min:
                issues.append(
                    f"  LUNCH TOO LATE (trail day): starts {it['start_time']} "
                    f"(max allowed on trail day: {TRAIL_LUNCH_LATEST_MIN})"
                )
        else:
            if start_min < lo_min:
                issues.append(
                    f"  LUNCH TOO EARLY: starts {it['start_time']} "
                    f"(window for '{group_type}': {minutes_to_time(lo_min)}–{minutes_to_time(hi_min)})"
                )
            elif start_min > hi_min:
                issues.append(
                    f"  LUNCH TOO LATE: starts {it['start_time']} "
                    f"(window for '{group_type}': {minutes_to_time(lo_min)}–{minutes_to_time(hi_min)})"
                )
    return issues


def check_lunch_duration(plan: list) -> list:
    """Lunch duration must be within reasonable bounds."""
    issues = []
    for it in plan:
        if it.get("type") != "lunch_break":
            continue
        try:
            start_min = time_to_minutes(it["start_time"])
            end_min   = time_to_minutes(it["end_time"])
            dur = end_min - start_min
        except Exception:
            issues.append("  LUNCH DURATION: cannot compute duration (missing times)")
            continue
        if dur < LUNCH_DURATION_MIN_FLOOR:
            issues.append(
                f"  LUNCH TOO SHORT: {it['start_time']}–{it['end_time']} = {dur} min "
                f"(minimum expected: {LUNCH_DURATION_MIN_FLOOR} min)"
            )
        elif dur > LUNCH_DURATION_MAX_FLOOR:
            issues.append(
                f"  LUNCH TOO LONG: {it['start_time']}–{it['end_time']} = {dur} min "
                f"(maximum expected: {LUNCH_DURATION_MAX_FLOOR} min)"
            )
    return issues


def check_lunch_no_overlap(plan: list) -> list:
    """No item may overlap with the lunch_break time window."""
    issues = []
    lunches = [it for it in plan if it.get("type") == "lunch_break"]
    if not lunches:
        return []
    lunch = lunches[0]
    try:
        lunch_start = time_to_minutes(lunch["start_time"])
        lunch_end   = time_to_minutes(lunch["end_time"])
    except Exception:
        return []

    for it in plan:
        if it is lunch:
            continue
        if not it.get("start_time") or not it.get("end_time"):
            continue
        try:
            s = time_to_minutes(it["start_time"])
            e = time_to_minutes(it["end_time"])
        except Exception:
            continue
        # Overlap: item starts before lunch ends AND ends after lunch starts
        if s < lunch_end and e > lunch_start:
            issues.append(
                f"  LUNCH OVERLAP: {it.get('type','?')}({it.get('name','')}) "
                f"{it['start_time']}–{it['end_time']} "
                f"overlaps lunch {lunch['start_time']}–{lunch['end_time']}"
            )
    return issues


def check_no_attraction_during_lunch(plan: list) -> list:
    """No attraction may START while lunch is in progress."""
    issues = []
    lunches = [it for it in plan if it.get("type") == "lunch_break"]
    if not lunches:
        return []
    lunch = lunches[0]
    try:
        lunch_start = time_to_minutes(lunch["start_time"])
        lunch_end   = time_to_minutes(lunch["end_time"])
    except Exception:
        return []

    for it in plan:
        if it.get("type") != "attraction":
            continue
        try:
            s = time_to_minutes(it["start_time"])
        except Exception:
            continue
        if lunch_start < s < lunch_end:
            issues.append(
                f"  ATTRACTION DURING LUNCH: {it.get('name','')} starts {it['start_time']} "
                f"(lunch {lunch['start_time']}–{lunch['end_time']})"
            )
    return issues


def validate_lunch(plan: list, group_type: str) -> tuple:
    """Run all lunch continuity checks. Returns (all_passed, issues_list)."""
    all_issues = []
    all_issues += check_lunch_presence(plan)
    all_issues += check_lunch_timing(plan, group_type)
    all_issues += check_lunch_duration(plan)
    all_issues += check_lunch_no_overlap(plan)
    all_issues += check_no_attraction_during_lunch(plan)
    return (len(all_issues) == 0, all_issues)


# ─── Main test runner ─────────────────────────────────────────────────────────

def run_tests():
    print("=" * 70)
    print("LUNCH CONTINUITY TEST — Testy_Klientki (test-01 … test-10)")
    print("=" * 70)

    print(f"\nLoading Zakopane POIs from: {DATA_FILE}")
    try:
        pois = load_zakopane_poi(str(DATA_FILE))
        print(f"  → Loaded {len(pois)} POIs\n")
    except Exception as e:
        print(f"  ERROR loading POIs: {e}")
        sys.exit(1)

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

        params     = json_to_engine_params(test_data)
        days       = params["days"]
        group_type = params["user"]["target_group"]
        test_pass  = True
        test_issues = []

        lo, hi = _lunch_window(group_type)
        print(f"{'─'*60}")
        print(f"TEST: {test_name}  ({group_type}, {days} day(s), "
              f"style={test_data.get('travel_style','?')}, "
              f"lunch window: {minutes_to_time(lo)}–{minutes_to_time(hi)})")

        for day_num in range(1, days + 1):
            total_days += 1
            ctx = dict(params["context"])
            base_y, base_m, base_d, base_wd = ctx.get("date", (2026, 2, 20, 4))
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

            day_ok, day_issues = validate_lunch(day_plan, group_type)

            # Find lunch item for summary
            lunch_item = next((it for it in day_plan if it.get("type") == "lunch_break"), None)
            lunch_summary = (
                f"{lunch_item['start_time']}–{lunch_item['end_time']} "
                f"({time_to_minutes(lunch_item['end_time']) - time_to_minutes(lunch_item['start_time'])} min)"
                if lunch_item and lunch_item.get("start_time") and lunch_item.get("end_time")
                else "NOT FOUND"
            )

            status = "PASS ✓" if day_ok else "FAIL ✗"
            print(f"  Day {day_num}: {status}  [lunch: {lunch_summary}]")

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
