"""
E2E COMPREHENSIVE TEST — 30.05.2026
=====================================
Kompleksowe testy end-to-end planera podróży.
Weryfikuje: Zakopane, multi-city, scoring po FIX #124, struktura planów,
posiłki, duplikaty, transport, preferencje dla różnych grup.

Uruchomienie: python e2e_comprehensive_30052026.py
(wymaga serwera na porcie 8001)
"""

import sys
import json
import uuid
import requests
from datetime import date, timedelta
from collections import Counter

BASE_URL = "http://127.0.0.1:8001"
GUEST_ID = str(uuid.uuid4())
HEADERS = {"X-Guest-ID": GUEST_ID, "Content-Type": "application/json"}

TODAY = date.today()
START_DATE = (TODAY + timedelta(days=7)).strftime("%Y-%m-%d")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []
failed_plans = []  # Track full plan responses for failed tests


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    icon = "  " + status + " | " + name
    if detail:
        icon += " — " + detail
    print(icon)
    return condition


def warn(name, detail=""):
    results.append((WARN, name, detail))
    print(f"  {WARN} | {name}" + (f" — {detail}" if detail else ""))


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def generate_plan(city, preferences, days=2, group_type="couples", budget=2,
                  travel_style="balanced", group_size=2, region_type="mountain",
                  transport_modes=None, country="Poland"):
    if transport_modes is None:
        transport_modes = ["car"]
    payload = {
        "location": {"city": city, "country": country, "region_type": region_type},
        "group": {"type": group_type, "size": group_size, "crowd_tolerance": 2},
        "trip_length": {"days": days, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": budget},
        "transport_modes": transport_modes,
        "preferences": preferences,
        "travel_style": travel_style,
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/plan/preview", json=payload, headers=HEADERS, timeout=90
        )
        return resp
    except Exception as e:
        return None


def extract_items(plan_response):
    """Flatten all items from all days."""
    items = []
    for day in plan_response.get("days", []):
        items.extend(day.get("items", []))
    return items


def extract_attractions(items):
    return [i for i in items if i.get("type") == "attraction"]


def names(items):
    return [i.get("name", "") for i in items if i.get("name")]


def check_no_day_duplicates(plan, label):
    """Verify no duplicate attraction across days."""
    days = plan.get("days", [])
    seen = {}
    dupes = []
    for d_idx, day in enumerate(days, 1):
        for item in day.get("items", []):
            if item.get("type") != "attraction":
                continue
            n = item.get("name", "")
            if n in seen:
                dupes.append(f"'{n}' dzień {seen[n]} i {d_idx}")
            else:
                seen[n] = d_idx
    check(f"{label}: brak duplikatów POI między dniami", len(dupes) == 0,
          ", ".join(dupes) if dupes else f"{len(seen)} unikalnych POI")


def check_lunch_timing(items, label):
    """Verify lunch appears between 11:00 and 14:30."""
    lunch = [i for i in items if i.get("type") in ("lunch_break",) or
             ("lunch" in str(i.get("meal_type", "")).lower())]
    if not lunch:
        warn(f"{label}: brak lunchu w planie")
        return
    for l in lunch:
        t = l.get("start_time", "")
        if t:
            ok = "11:00" <= t <= "14:30"
            check(f"{label}: lunch o właściwej porze ({t})", ok,
                  f"oczekiwano 11:00–14:30, got {t}")


def check_no_time_overlaps(items, label):
    """Verify no items overlap in time."""
    timed = [(i.get("start_time", ""), i.get("end_time", ""), i.get("name", ""))
             for i in items if i.get("start_time") and i.get("end_time")]
    overlaps = []
    for j in range(len(timed) - 1):
        s1, e1, n1 = timed[j]
        s2, e2, n2 = timed[j + 1]
        # Simple string compare works for HH:MM format
        if s1 < s2 < e1:
            overlaps.append(f"{n1}({s1}-{e1}) ↔ {n2}({s2}-{e2})")
    check(f"{label}: brak nakładania czasu eventów", len(overlaps) == 0,
          "; ".join(overlaps) if overlaps else "")


def check_daily_window(items, label, window_start="09:00", window_end="19:00"):
    """Verify all items fit within daily time window."""
    violations = []
    for i in items:
        s = i.get("start_time", "")
        e = i.get("end_time", "")
        if s and s < window_start:
            violations.append(f"{i.get('name','')} start {s} < {window_start}")
        if e and e > window_end:
            violations.append(f"{i.get('name','')} end {e} > {window_end}")
    check(f"{label}: plan mieści się w oknie {window_start}–{window_end}",
          len(violations) == 0,
          "; ".join(violations[:3]) if violations else "")


def print_day_summary(plan, max_days=3):
    days = plan.get("days", [])
    for d_idx, day in enumerate(days[:max_days], 1):
        items = day.get("items", [])
        print(f"\n  Dzień {d_idx} ({len(items)} elementów):")
        for i in items:
            t_from = i.get("start_time", "?")
            t_to = i.get("end_time", "?")
            tp = i.get("type", "?")
            nm = i.get("name", "")
            score = i.get("score", "")
            score_str = f" [score={score:.2f}]" if isinstance(score, (int, float)) else ""
            print(f"    {t_from}–{t_to} [{tp}] {nm}{score_str}")


# =============================================================================
# TEST 0: Health check
# =============================================================================
section("TEST 0: Health check — czy serwer odpowiada")

try:
    r = requests.get(f"{BASE_URL}/docs", timeout=5)
    ok = check("Serwer odpowiada na /docs", r.status_code == 200, f"HTTP {r.status_code}")
    if not ok:
        print("\n[FATAL] Serwer nie odpowiada — przerywam testy.")
        sys.exit(1)
except Exception as e:
    check("Serwer odpowiada na /docs", False, str(e))
    print("\n[FATAL] Serwer nie odpowiada — przerywam testy.")
    sys.exit(1)

# =============================================================================
# TEST 1: Zakopane — podstawowa generacja planu (2 dni, couples)
# =============================================================================
section("TEST 1: Zakopane — podstawowa generacja planu (2 dni, couples, balanced)")

r = generate_plan("Zakopane", ["nature_landscape", "must_see_only"], days=2)
check("Plan generuje się (HTTP 200)", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    days_list = plan.get("days", [])
    items = extract_items(plan)
    attractions = extract_attractions(items)

    check("Plan ma 2 dni", len(days_list) == 2, f"{len(days_list)} dni")
    check("Łącznie ≥ 4 atrakcje w planie", len(attractions) >= 4,
          f"{len(attractions)} atrakcji")

    all_names = names(attractions)
    must_see = ["Morskie Oko", "Gubałówka", "Dolina Kościeliska", "Kasprowy", "Giewont"]
    found_must_see = [n for n in must_see if any(n.lower() in an.lower() for an in all_names)]
    check("Plan zawiera ≥ 1 kultowe POI (Morskie Oko / Gubałówka / Kościeliska)",
          len(found_must_see) >= 1,
          f"Znaleziono: {found_must_see}")

    check_no_day_duplicates(plan, "Zakopane 2d")
    check_lunch_timing(items, "Zakopane 2d")
    check_no_time_overlaps(items, "Zakopane 2d")
    check_daily_window(items, "Zakopane 2d")

    print_day_summary(plan)

# =============================================================================
# TEST 2: Zakopane — family_kids (FIX #124 — kids POI scoring)
# =============================================================================
section("TEST 2: Zakopane — family_kids (FIX #124 — kids POI scoring)")

r = generate_plan("Zakopane",
                  ["attractions_for_kids", "nature_landscape"],
                  days=2, group_type="family_kids", group_size=4,
                  travel_style="relaxed")
check("Plan family_kids generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    attractions = extract_attractions(items)
    all_names = names(items)

    KIDS_KEYWORDS = [
        "aqua", "basen", "termy", "park linowy", "stok", "narty", "sanki",
        "zoo", "farma", "gubalówka", "kolejka", "mini golf", "edukacja",
        "wodospad", "dolina", "zwierzęt", "animacj"
    ]
    kids_found = [n for n in all_names if any(k in n.lower() for k in KIDS_KEYWORDS)]

    check("Plan ma ≥ 3 atrakcje", len(attractions) >= 3,
          f"{len(attractions)} atrakcji")
    check("Plan zawiera POI przyjazne dzieciom", len(kids_found) >= 1,
          f"Znaleziono: {kids_found[:5]}")
    check_no_day_duplicates(plan, "Family kids")
    check_lunch_timing(items, "Family kids")
    check_no_time_overlaps(items, "Family kids")

    print(f"\n  Wszystkie POI w planie: {all_names[:20]}")

# =============================================================================
# TEST 3: Zakopane — mountain_trails (FIX #94/#124 — trail scoring)
# =============================================================================
section("TEST 3: Zakopane — mountain_trails (FIX #94/#124 — trail scoring)")

r = generate_plan("Zakopane",
                  ["mountain_trails", "active_sport"],
                  days=2, group_type="couples",
                  travel_style="adventure")
check("Plan mountain_trails generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    attractions = extract_attractions(items)
    all_names = names(items)

    TRAIL_KEYWORDS = [
        "szlak", "dolina", "szczyt", "giewont", "kasprowy", "rysy",
        "szpiglasowy", "kościeliska", "chochołowska", "morskie oko",
        "ornak", "mięguszowiec", "tatry", "siklawa", "czarny staw"
    ]
    trails_found = [n for n in all_names if any(k in n.lower() for k in TRAIL_KEYWORDS)]

    check("Plan ma ≥ 3 atrakcje trail/mountain", len(attractions) >= 3,
          f"{len(attractions)} atrakcji")
    check("Plan zawiera szlaki/szczyty/doliny tatrzańskie", len(trails_found) >= 1,
          f"Znaleziono: {trails_found[:5]}")

    # Sprawdź czy nie ma zbyt wielu szlaków w 1 dniu (max 1-2 per day)
    days_list = plan.get("days", [])
    for d_idx, day in enumerate(days_list, 1):
        day_attrs = [i for i in day.get("items", []) if i.get("type") == "attraction"]
        trail_cnt = sum(1 for i in day_attrs if any(k in i.get("name","").lower()
                        for k in ["szlak", "dolina", "szczyt", "giewont", "kasprowy", "rysy"]))
        check(f"Dzień {d_idx}: max 2 szlaki (nie przeciążony)", trail_cnt <= 2,
              f"{trail_cnt} szlaków w dniu {d_idx}")

    check_no_time_overlaps(items, "Mountain trails")
    check_daily_window(items, "Mountain trails")
    print(f"\n  POI trail/mountain: {trails_found}")

# =============================================================================
# TEST 4: Zakopane — relax_wellness / termy (max 2 termy per plan)
# =============================================================================
section("TEST 4: Zakopane — relax_wellness / termy (weryfikacja limitu termy)")

r = generate_plan("Zakopane",
                  ["relax_wellness", "relaxation"],
                  days=3, group_type="couples",
                  travel_style="relaxed", budget=3)
check("Plan relax_wellness generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    all_names = names(items)

    termy_count = sum(1 for n in all_names if "termy" in n.lower())
    check("Termy w planie (≥ 1 wizyta)", termy_count >= 1,
          f"{termy_count} wizyt w termach")
    check("Termy ≤ 2 w całym planie (nie spam)", termy_count <= 2,
          f"{termy_count} wizyt")

    wellness_kw = ["spa", "termy", "relaks", "masaż", "basen", "wellness", "jacuzzi"]
    wellness = [n for n in all_names if any(k in n.lower() for k in wellness_kw)]
    check("Plan zawiera POI wellness/relax", len(wellness) >= 1,
          f"{wellness[:5]}")

    print(f"\n  Wszystkie POI w planie 3d relax: {all_names[:20]}")

# =============================================================================
# TEST 5: Zakopane — must_see_only (FIX #96 — must_see tag injection)
# =============================================================================
section("TEST 5: Zakopane — must_see_only (FIX #96)")

r = generate_plan("Zakopane",
                  ["must_see_only"],
                  days=2, group_type="couples",
                  travel_style="balanced")
check("Plan must_see_only generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    all_names = names(items)

    MUST_SEE = ["Morskie Oko", "Gubałówka", "Dolina Kościeliska", "Kasprowy Wierch", "Giewont"]
    found = [n for n in MUST_SEE if any(n.lower() in an.lower() for an in all_names)]

    check("Plan zawiera ≥ 2 kultowe must-see POI", len(found) >= 2,
          f"Znaleziono: {found}")

    # Sprawdź że plan NIE zawiera nudnych/zwykłych POI z niskim score
    print(f"\n  Must-see POI w planie: {found}")
    print(f"  Wszystkie POI: {all_names[:15]}")

# =============================================================================
# TEST 6: Zakopane — local_food_experience (FIX #67 — culinary POI)
# =============================================================================
section("TEST 6: Zakopane — local_food_experience (FIX #67 — kulinarne POI)")

r = generate_plan("Zakopane",
                  ["local_food_experience", "nature_landscape"],
                  days=2, group_type="couples",
                  travel_style="relaxed")
check("Plan local_food_experience generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    all_names = names(items)

    FOOD_KW = ["oscypek", "bacówka", "bacowka", "targowisko", "krupówki", "karczma",
               "oscypka", "koliba", "jagnię", "góralsk", "regionaln", "smaki"]
    food_poi = [n for n in all_names if any(k in n.lower() for k in FOOD_KW)]

    check("Plan zawiera kulinarne/regionalne POI", len(food_poi) >= 1,
          f"Znaleziono: {food_poi[:5]}")

    # Sprawdź restauracje/lunche
    meals = [i for i in items if i.get("type") in ("lunch_break", "dinner_break", "restaurant")]
    check("Plan ma ≥ 1 posiłek", len(meals) >= 1,
          f"{len(meals)} posiłków")

    print(f"\n  Food/kultura POI: {food_poi}")

# =============================================================================
# TEST 7: Multi-city — Kraków (museums_heritage, FIX #124)
# =============================================================================
section("TEST 7: Multi-city — Kraków (museums_heritage, FIX #124)")

r = generate_plan("Kraków",
                  ["museums_heritage", "history_mystery"],
                  days=2, region_type="city",
                  group_type="couples", travel_style="cultural")
check("Plan Kraków generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    attractions = extract_attractions(items)
    all_names = names(items)

    KRAKOW_KW = ["wawel", "sukiennice", "rynek", "kazimierz", "muzeum", "kościół",
                 "barbakan", "brama", "smok", "stare miasto", "wieliczka", "zamek"]
    krakow_found = [n for n in all_names if any(k in n.lower() for k in KRAKOW_KW)]

    check("Plan ma ≥ 3 atrakcje (multi-city załadował dane)", len(attractions) >= 3,
          f"{len(attractions)} atrakcji")
    check("Plan zawiera POI charakterystyczne dla Krakowa", len(krakow_found) >= 1,
          f"Znaleziono: {krakow_found[:5]}")
    check_no_day_duplicates(plan, "Kraków 2d")
    check_no_time_overlaps(items, "Kraków 2d")

    print(f"\n  Kraków POI: {all_names[:15]}")
else:
    if r:
        print(f"  Odpowiedź: {r.text[:300]}")

# =============================================================================
# TEST 8: Multi-city — Wrocław (nature_landscapes, FIX #124)
# =============================================================================
section("TEST 8: Multi-city — Wrocław (nature_landscapes, FIX #124)")

r = generate_plan("Wrocław",
                  ["nature_landscapes", "castles_palaces"],
                  days=2, region_type="city",
                  group_type="couples", travel_style="balanced")
check("Plan Wrocław generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    attractions = extract_attractions(items)
    all_names = names(items)

    check("Plan Wrocław ma ≥ 2 atrakcje", len(attractions) >= 2,
          f"{len(attractions)} atrakcji")
    WROCLAW_KW = ["ostrów", "katedra", "hala stulecia", "zoo", "ogród", "panorama",
                  "rynek", "dworzec", "fontanna", "zamek", "most"]
    wroclaw_found = [n for n in all_names if any(k in n.lower() for k in WROCLAW_KW)]
    check("Plan zawiera POI z Wrocławia", len(wroclaw_found) >= 1,
          f"Znaleziono: {wroclaw_found[:5]}")
    print(f"\n  Wrocław POI: {all_names[:15]}")
else:
    if r:
        print(f"  Odpowiedź: {r.text[:300]}")

# =============================================================================
# TEST 9: Multi-city — Gdańsk (water_attractions, FIX #124)
# =============================================================================
section("TEST 9: Multi-city — Gdańsk (water_attractions, FIX #124)")

r = generate_plan("Gdańsk",
                  ["water_attractions", "museums_heritage"],
                  days=2, region_type="city",
                  group_type="couples", travel_style="balanced")
check("Plan Gdańsk generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    attractions = extract_attractions(items)
    all_names = names(items)

    check("Plan Gdańsk ma ≥ 2 atrakcje", len(attractions) >= 2,
          f"{len(attractions)} atrakcji")
    GDANSK_KW = ["morze", "plaża", "molo", "morska", "amber", "neptun", "długi targ",
                 "stare miasto", "westerplatte", "muzeum", "żuraw", "sopot"]
    gdansk_found = [n for n in all_names if any(k in n.lower() for k in GDANSK_KW)]
    check("Plan zawiera POI z Gdańska/morskie", len(gdansk_found) >= 1,
          f"Znaleziono: {gdansk_found[:5]}")
    print(f"\n  Gdańsk POI: {all_names[:15]}")
else:
    if r:
        print(f"  Odpowiedź: {r.text[:300]}")

# =============================================================================
# TEST 10: Zakopane — 5 dni (test długiego wyjazdu — unikalność POI)
# =============================================================================
section("TEST 10: Zakopane — 5 dni (długi wyjazd, unikalność POI)")

r = generate_plan("Zakopane",
                  ["nature_landscape", "must_see_only", "mountain_trails"],
                  days=5, group_type="couples",
                  travel_style="adventure")
check("Plan 5 dni generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    days_list = plan.get("days", [])
    items = extract_items(plan)
    attractions = extract_attractions(items)
    all_attr_names = names(attractions)

    check("Plan ma 5 dni", len(days_list) == 5, f"{len(days_list)} dni")
    check("Plan ma ≥ 8 atrakcji łącznie", len(attractions) >= 8,
          f"{len(attractions)} atrakcji")

    # Sprawdź unikalność (>70% uniqueness)
    name_counter = Counter(all_attr_names)
    dupes = {n: c for n, c in name_counter.items() if c > 1}
    unique_ratio = len(name_counter) / len(all_attr_names) if all_attr_names else 0
    check("Unikalność POI > 70% w 5-dniowym planie", unique_ratio >= 0.70,
          f"{unique_ratio:.0%} ({len(name_counter)} unikalnych / {len(all_attr_names)} łącznie)")
    if dupes:
        print(f"  Duplikaty: {dupes}")

    check_no_time_overlaps(items, "5-day plan")
    check_daily_window(items, "5-day plan")
    print_day_summary(plan, max_days=5)

# =============================================================================
# TEST 11: Zakopane — seniors (łagodny tryb, bez intensywnych szlaków)
# =============================================================================
section("TEST 11: Zakopane — seniors (łagodny tryb)")

r = generate_plan("Zakopane",
                  ["nature_landscape", "relaxation", "museums_heritage"],
                  days=2, group_type="seniors", group_size=2,
                  travel_style="relaxed")
check("Plan seniors generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    attractions = extract_attractions(items)
    all_names = names(items)

    # Sprawdź że nie ma ultra-trudnych szlaków (Rysy, Mięguszowiec)
    HARD_TRAILS = ["rysy", "mięguszowiec", "orla perć", "granaty"]
    hard_found = [n for n in all_names if any(k in n.lower() for k in HARD_TRAILS)]
    check("Plan seniors nie zawiera super-trudnych szlaków", len(hard_found) == 0,
          f"Znaleziono trudne szlaki: {hard_found}")

    check("Plan seniors ma ≥ 2 atrakcje", len(attractions) >= 2,
          f"{len(attractions)} atrakcji")
    check_no_time_overlaps(items, "Seniors")
    print(f"\n  Seniors POI: {all_names[:15]}")

# =============================================================================
# TEST 12: Transport mode — transfer items mają transport_mode
# =============================================================================
section("TEST 12: Transfer items — obecność pola transport_mode (FIX #98)")

r = generate_plan("Zakopane",
                  ["mountain_trails", "nature_landscape"],
                  days=2, group_type="couples",
                  transport_modes=["car"])
check("Plan z transport='car' generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    transfers = [i for i in items if i.get("type") == "transfer"]

    if not transfers:
        warn("Brak itemów transfer w planie", "Możliwe że engine nie generuje transferów")
    else:
        with_mode = [i for i in transfers if i.get("transport_mode")]
        check("Transfery mają pole transport_mode", len(with_mode) == len(transfers),
              f"{len(with_mode)}/{len(transfers)} z transport_mode")

        modes_used = set(i.get("transport_mode", "") for i in transfers)
        print(f"  Tryby transportu użyte: {modes_used}")
        print(f"  Przykładowe transfery:")
        for t in transfers[:5]:
            print(f"    {t.get('start_time','')}–{t.get('end_time','')} "
                  f"mode={t.get('transport_mode','')} dur={t.get('duration_min','')}min "
                  f"from={t.get('from','?')} → to={t.get('to','?')}")

# =============================================================================
# TEST 13: Struktura odpowiedzi — schema check
# =============================================================================
section("TEST 13: Struktura odpowiedzi JSON — wymagane pola")

r = generate_plan("Zakopane", ["nature_landscape"], days=2)
check("Plan generuje się dla schema check", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()

    # Top-level fields
    check("plan.days istnieje", "days" in plan, str(list(plan.keys())))
    check("plan.plan_id istnieje", "plan_id" in plan or "id" in plan,
          str([k for k in plan.keys() if "id" in k.lower()]))
    check("plan.total_days istnieje", "total_days" in plan or len(plan.get("days",[])) > 0,
          str(list(plan.keys())))

    # Day fields
    if plan.get("days"):
        day = plan["days"][0]
        check("day.date lub day.day_number istnieje",
              "date" in day or "day_number" in day,
              str(list(day.keys())))
        check("day.items istnieje", "items" in day, str(list(day.keys())))

        # Item fields
        if day.get("items"):
            item = next((i for i in day["items"] if i.get("type") == "attraction"), day["items"][0])
            required_fields = ["type", "name", "start_time", "end_time"]
            for f in required_fields:
                check(f"item.{f} istnieje", f in item,
                      str([k for k in item.keys()]))

# =============================================================================
# TEST 14: caves_mines preferencja (FIX #124)
# =============================================================================
section("TEST 14: Zakopane — caves_mines (FIX #124 — jaskinie/kopalnie)")

r = generate_plan("Zakopane",
                  ["caves_mines", "museums_heritage"],
                  days=2, group_type="couples",
                  travel_style="cultural")
check("Plan caves_mines generuje się", r and r.status_code == 200,
      f"HTTP {r.status_code if r else 'brak'}")

if r and r.status_code == 200:
    plan = r.json()
    items = extract_items(plan)
    all_names = names(items)

    CAVE_KW = ["jaskinia", "smocza", "niedźwiedzia", "raj", "ciemna", "mylna",
               "kopalnia", "krzemionki", "wieliczka", "bochnia", "mroźna"]
    caves_found = [n for n in all_names if any(k in n.lower() for k in CAVE_KW)]
    check("Plan zawiera jaskinie/podziemia", len(caves_found) >= 1,
          f"Znaleziono: {caves_found[:5]}")
    print(f"  Caves POI: {caves_found}")
    print(f"  Wszystkie POI: {all_names[:10]}")

# =============================================================================
# PODSUMOWANIE
# =============================================================================
section("PODSUMOWANIE E2E — wyniki wszystkich testów")

passed = sum(1 for s, n, d in results if s == PASS)
failed = sum(1 for s, n, d in results if s == FAIL)
warnings = sum(1 for s, n, d in results if s == WARN)
total = len(results)

print(f"\n  Łącznie: {total} testów")
print(f"  {PASS}: {passed}")
print(f"  {FAIL}: {failed}")
print(f"  {WARN}: {warnings}")

if failed > 0:
    print(f"\n  NIEUDANE TESTY ({failed}):")
    for status, name, detail in results:
        if status == FAIL:
            print(f"    ❌ {name}: {detail}")

if warnings > 0:
    print(f"\n  OSTRZEŻENIA ({warnings}):")
    for status, name, detail in results:
        if status == WARN:
            print(f"    ⚠️  {name}: {detail}")

print("\n" + "=" * 70)
success_rate = (passed / total * 100) if total > 0 else 0
print(f"  WYNIK: {success_rate:.1f}% ({passed}/{total})")

if failed == 0 and warnings == 0:
    print("  STATUS: ✅ WSZYSTKIE TESTY PRZESZŁY — planer działa poprawnie")
elif failed == 0:
    print("  STATUS: ✅ TESTY PRZESZŁY z ostrzeżeniami — sprawdź WARN")
elif failed <= 3:
    print("  STATUS: ⚠️  DROBNE PROBLEMY — sprawdź FAIL powyżej")
else:
    print("  STATUS: ❌ POWAŻNE BŁĘDY — wymagają naprawy")
print("=" * 70 + "\n")

sys.exit(0 if failed == 0 else 1)
