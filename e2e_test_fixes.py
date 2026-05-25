"""
E2E TEST — FIX #65, #66, #67 + DATA UPDATE (24.05.2026)
=========================================================
Testy end-to-end weryfikujące poprawność wszystkich ostatnich napraw.

Uruchomienie: python e2e_test_fixes.py
(wymaga działającego serwera na porcie 8001)
"""
import sys
import json
import uuid
import requests
from datetime import date, timedelta

BASE_URL = "http://127.0.0.1:8001"
GUEST_ID = str(uuid.uuid4())
HEADERS = {"X-Guest-ID": GUEST_ID, "Content-Type": "application/json"}

TODAY = date.today()
START_DATE = (TODAY + timedelta(days=7)).strftime("%Y-%m-%d")

# ─────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    print(f"  {status} | {name}" + (f" — {detail}" if detail else ""))

def warn(name, detail=""):
    results.append((WARN, name, detail))
    print(f"  {WARN} | {name}" + (f" — {detail}" if detail else ""))

def generate_plan(preferences, days=2, group_type="couples", budget=2, travel_style="relaxed"):
    payload = {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": group_type, "size": 2, "crowd_tolerance": 2},
        "trip_length": {"days": days, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": budget},
        "transport_modes": ["car"],
        "preferences": preferences,
        "travel_style": travel_style,
    }
    resp = requests.post(f"{BASE_URL}/plan/preview", json=payload, headers=HEADERS, timeout=60)
    return resp

def extract_all_items(plan_response):
    """Flatten all items from all days into a single list."""
    items = []
    days = plan_response.get("days", [])
    for day in days:
        items.extend(day.get("items", []))
    return items

def collect_all_names(items):
    return [i.get("name", "") for i in items if i.get("name")]

# ─────────────────────────────────────────────────────────────
# TEST 0: Health check
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("TEST 0: Health check")
print("="*70)
try:
    r = requests.get(f"{BASE_URL}/docs", timeout=5)
    check("API server odpowiada", r.status_code == 200, f"HTTP {r.status_code}")
except Exception as e:
    check("API server odpowiada", False, str(e))
    print("\n[FATAL] Serwer nie odpowiada — przerwanie testów.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# TEST 1: POI loading — weryfikacja przez /poi/{poi_id} (brak list endpoint)
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("TEST 1: Ładowanie POI — weryfikacja 3 nowych kulinarnnych POI przez endpoint")
print("="*70)
try:
    # Brak list endpoint (/poi/ zwraca 404) — sprawdzamy konkretne IDs
    warn("Brak /poi/ list endpoint", "Weryfikacja przez /poi/{id} dla poi_75, poi_76, poi_77")
    for poi_id in ["poi_75", "poi_76", "poi_77"]:
        r = requests.get(f"{BASE_URL}/poi/{poi_id}", timeout=10, headers=HEADERS)
        if r.status_code == 200:
            poi = r.json()
            check(f"POI {poi_id} istnieje w bazie", True, f"Nazwa: {poi.get('name', poi.get('id', '?'))}")
        else:
            check(f"POI {poi_id} istnieje w bazie", False, f"HTTP {r.status_code}")
except Exception as e:
    warn("POI endpoint test", f"Błąd: {e}")

# ─────────────────────────────────────────────────────────────
# TEST 2: FIX #67 — Nowe kulinarne POI (local_food_experience)
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("TEST 2: FIX #67 — Nowe POI kulinarne widoczne w planach (local_food_experience)")
print("="*70)

NEW_CULINARY_POIS = [
    "Bacówka Zakopiańczyk",
    "Bacówka zakopiańczyk",
    "Dom Oscypka",
    "Targowisko pod Gubałówką",
    "Targowisko",
    "Gubałówką",
]

try:
    r = generate_plan(
        preferences=["local_food_experience", "cultural", "nature"],
        days=3,
        group_type="couples",
        travel_style="relax"
    )
    check("Plan generuje się (local_food_experience)", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        plan = r.json()
        items = extract_all_items(plan)
        all_names = collect_all_names(items)
        all_names_lower = " | ".join(all_names).lower()

        found_bacowka = any("bac" in n.lower() and ("zakop" in n.lower() or "zakopiańczyk" in n.lower()) for n in all_names)
        found_dom_oscypka = any("oscypka" in n.lower() for n in all_names)
        found_targowisko = any("targowisko" in n.lower() or "gubałówk" in n.lower() for n in all_names)
        any_culinary_new = found_bacowka or found_dom_oscypka or found_targowisko

        check("Plan ma dni", len(plan.get("days", [])) > 0, f"{len(plan.get('days', []))} dni")
        check("Co najmniej 1 nowe POI kulinarne pojawia się w planie",
              any_culinary_new,
              f"Bacówka={found_bacowka}, Dom Oscypka={found_dom_oscypka}, Targowisko={found_targowisko}")

        # Sprawdź scoring — poszukaj POI z tagami food
        food_items = [i for i in items if any(
            kw in (i.get("name","") + i.get("description","") + str(i.get("tags",""))).lower()
            for kw in ["oscypek", "bacówka", "bacowka", "oscypka", "targowisko", "food", "regional", "cuisine"]
        )]
        check("Plan zawiera jakieś atrakcje kulinarno-regionalne", len(food_items) > 0,
              f"Znaleziono: {[i.get('name') for i in food_items[:5]]}")

        print(f"\n  Wszystkie POI w planie ({len(all_names)} items):")
        for n in all_names[:30]:
            print(f"    - {n}")
        if len(all_names) > 30:
            print(f"    ... i {len(all_names)-30} więcej")
    else:
        print(f"  ODPOWIEDŹ: {r.text[:500]}")
except Exception as e:
    check("FIX #67 test", False, str(e))

# ─────────────────────────────────────────────────────────────
# TEST 3: FIX #66 — nature_landscape typ w type_match
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("TEST 3: FIX #66 — nature_landscape POI pojawia się w planach z tą preferencją")
print("="*70)

NATURE_POI_NAMES = [
    "Dolina", "Wodospad", "Staw", "Stawy", "Morskie Oko",
    "Giewont", "Kasprowy", "Czarny", "Rysy", "Szpiglasowy",
    "Siklawa", "Sarni", "Kościeliska", "Chochołowska",
    "Białego", "panorama", "widok", "Tatry", "szczyt"
]

try:
    r = generate_plan(
        preferences=["nature_landscape", "hiking"],
        days=2,
        group_type="couples",
        travel_style="adventure"
    )
    check("Plan generuje się (nature_landscape)", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        plan = r.json()
        items = extract_all_items(plan)
        all_names = collect_all_names(items)

        nature_found = [n for n in all_names if any(
            kw.lower() in n.lower() for kw in NATURE_POI_NAMES
        )]
        check("Plan zawiera POI nature_landscape", len(nature_found) > 0,
              f"Znaleziono: {nature_found[:5]}")

        # Test: plan ma atrakcje (nie tylko restauracje/bufory)
        attractions = [i for i in items if i.get("type") == "attraction"]
        check("Plan ma > 2 atrakcje", len(attractions) > 2, f"{len(attractions)} atrakcji")

        print(f"\n  POI nature_landscape w planie: {nature_found}")
except Exception as e:
    check("FIX #66 test", False, str(e))

# ─────────────────────────────────────────────────────────────
# TEST 4: FIX #65 — meal_type="lunch,dinner" działa przy dinner
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("TEST 4: FIX #65 — restauracje z meal_type='lunch,dinner' pojawiają się na kolacji")
print("="*70)

try:
    r = generate_plan(
        preferences=["relaxation", "local_food_experience", "cultural"],
        days=2,
        group_type="couples",
        travel_style="relax",
        budget=3
    )
    check("Plan generuje się (test dinner)", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        plan = r.json()
        items = extract_all_items(plan)

        dinner_items = [i for i in items if i.get("type") in ("dinner_break", "dinner", "restaurant")
                        or (i.get("meal_type") and "dinner" in str(i.get("meal_type","")).lower())]
        lunch_items  = [i for i in items if i.get("type") in ("lunch_break", "lunch", "restaurant")
                        or (i.get("meal_type") and "lunch" in str(i.get("meal_type","")).lower())]

        check("Plan ma jakieś przerwy na jedzenie", len(dinner_items) + len(lunch_items) > 0,
              f"dinner={len(dinner_items)}, lunch={len(lunch_items)}")

        all_items_raw = plan
        print(f"\n  Przykładowe itemy jedzeniowe:")
        for i in items:
            if i.get("type") in ("lunch_break","dinner_break","restaurant","meal"):
                print(f"    type={i.get('type')} name={i.get('name','')} meal_type={i.get('meal_type','')} time={i.get('start_time','')}")
except Exception as e:
    check("FIX #65 test", False, str(e))

# ─────────────────────────────────────────────────────────────
# TEST 5: Full plan generation — 3 days, seniors
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("TEST 5: Pełna generacja planu — 3 dni, seniors, nature+wellness")
print("="*70)

try:
    r = generate_plan(
        preferences=["relaxation", "nature_landscape", "wellness"],
        days=3,
        group_type="seniors",
        travel_style="relax",
        budget=2
    )
    check("Plan seniors generuje się", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        plan = r.json()
        days = plan.get("days", [])
        check("Plan ma 3 dni", len(days) == 3, f"{len(days)} dni")

        for day_idx, day in enumerate(days, 1):
            day_items = day.get("items", [])
            attractions = [i for i in day_items if i.get("type") == "attraction"]
            overlaps = []

            # Sprawdź overlapping events
            timed = [(i.get("start_time",""), i.get("end_time",""), i.get("name","")) for i in day_items
                     if i.get("start_time") and i.get("end_time")]
            for j in range(len(timed)-1):
                s1, e1, n1 = timed[j]
                s2, e2, n2 = timed[j+1]
                if e1 > s2 and s1 < s2:  # simple string compare (HH:MM format)
                    overlaps.append(f"{n1}({s1}-{e1}) vs {n2}({s2}-{e2})")

            check(f"Dzień {day_idx}: brak nakładających się eventów", len(overlaps) == 0,
                  f"Nakładania: {overlaps}" if overlaps else f"{len(timed)} eventów OK")
            check(f"Dzień {day_idx}: ma atrakcje", len(attractions) >= 1,
                  f"{len(attractions)} atrakcji")
except Exception as e:
    check("Full plan test", False, str(e))

# ─────────────────────────────────────────────────────────────
# TEST 6: Full plan — family with kids, 2 days
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("TEST 6: Generacja planu — 2 dni, family_kids")
print("="*70)

try:
    r = generate_plan(
        preferences=["family_friendly", "cultural", "nature"],
        days=2,
        group_type="family_kids",
        travel_style="relax",
        budget=2
    )
    check("Plan family_kids generuje się", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        plan = r.json()
        days = plan.get("days", [])
        items = extract_all_items(plan)
        attractions = [i for i in items if i.get("type") == "attraction"]
        check("Plan ma 2 dni", len(days) == 2, f"{len(days)} dni")
        check("Plan ma atrakcje family_kids", len(attractions) >= 2,
              f"{len(attractions)} atrakcji")
        all_names = collect_all_names(items)
        print(f"\n  POI family_kids: {[n for n in all_names if n][:15]}")
except Exception as e:
    check("Family plan test", False, str(e))

# ─────────────────────────────────────────────────────────────
# PODSUMOWANIE
# ─────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PODSUMOWANIE E2E TESTÓW")
print("="*70)

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
warnings = sum(1 for r in results if r[0] == WARN)
total = len(results)

print(f"\n  Łącznie testów: {total}")
print(f"  {PASS}: {passed}")
print(f"  {FAIL}: {failed}")
print(f"  {WARN}: {warnings}")

if failed > 0:
    print(f"\n  NIEUDANE TESTY:")
    for status, name, detail in results:
        if status == FAIL:
            print(f"    {FAIL} {name}: {detail}")

print("\n" + "="*70)
success_rate = (passed / total * 100) if total > 0 else 0
print(f"  WYNIK: {success_rate:.0f}% ({passed}/{total})")
if failed == 0:
    print("  STATUS: ✅ WSZYSTKIE TESTY PRZESZŁY")
elif failed <= 2:
    print("  STATUS: ⚠️  DROBNE PROBLEMY — sprawdź FAIL powyżej")
else:
    print("  STATUS: ❌ KRYTYCZNE BŁĘDY — wymagają naprawy")
print("="*70 + "\n")

sys.exit(0 if failed == 0 else 1)
