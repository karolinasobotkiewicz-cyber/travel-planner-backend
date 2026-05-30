"""
Komprehensywny test E2E planera podróży
Testuje: pojedyncze miasto, multi-city (cluster), różne grupy, preferencje, style podróży.
Uruchom z travel-planner-backend/ z działającym serwerem na :8001
"""
import requests
import json
import time
from datetime import date, timedelta

BASE = "http://localhost:8001"
HEADERS = {"X-Guest-ID": "00000000-0000-4000-8000-000000000001", "Content-Type": "application/json"}

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

results = []

# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────

def post(payload):
    try:
        r = requests.post(f"{BASE}/plan/preview", json=payload, headers=HEADERS, timeout=60)
        return r
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        return None

def analyze_plan(data: dict, test_name: str) -> dict:
    """Analizuje plan i zwraca kluczowe metryki."""
    days = data.get("days", [])
    all_items = []
    for day in days:
        all_items.extend(day.get("items", []))

    attractions = [i for i in all_items if i.get("type") == "attraction"]
    restaurants = [i for i in all_items if i.get("type") in ("restaurant", "lunch_break", "dinner_break")]
    hotels = [i for i in all_items if i.get("type") == "hotel"]

    # Unikalne POI
    poi_ids = [i.get("poi", {}).get("id") or i.get("poi", {}).get("name") for i in attractions if i.get("poi")]
    unique_ratio = len(set(poi_ids)) / len(poi_ids) if poi_ids else 1.0

    # Cities covered
    cities = set()
    for item in attractions:
        # city is at item level (not nested under poi)
        city = item.get("city") or item.get("City", "")
        if not city:
            poi = item.get("poi", {})
            city = poi.get("city") or poi.get("City", "")
        if city:
            cities.add(city)

    # Porki czasu dla każdego dnia
    day_summaries = []
    for i, day in enumerate(days):
        items = day.get("items", [])
        attr_count = sum(1 for x in items if x.get("type") == "attraction")
        day_summaries.append(f"Day {i+1}: {attr_count} attractions")

    return {
        "test": test_name,
        "days": len(days),
        "total_attractions": len(attractions),
        "total_restaurants": len(restaurants),
        "unique_ratio": unique_ratio,
        "cities": sorted(cities),
        "day_summaries": day_summaries,
        "warnings": data.get("warnings", []),
        "quality_score": data.get("quality_score"),
    }

def run_test(test_name: str, payload: dict, checks: list = None) -> bool:
    """Uruchamia test i raportuje wyniki."""
    print(f"\n{'─'*70}")
    print(f"TEST: {test_name}")
    print(f"{'─'*70}")
    
    t0 = time.time()
    r = post(payload)
    elapsed = time.time() - t0

    if r is None:
        print(f"{FAIL} TIMEOUT / CONNECTION ERROR")
        results.append({"test": test_name, "status": "FAIL", "reason": "timeout/conn"})
        return False

    print(f"HTTP {r.status_code} | {elapsed:.1f}s")

    if r.status_code != 200:
        try:
            err = r.json()
            print(f"{FAIL} Error: {json.dumps(err, ensure_ascii=False)[:500]}")
        except:
            print(f"{FAIL} Raw: {r.text[:300]}")
        results.append({"test": test_name, "status": "FAIL", "reason": f"HTTP {r.status_code}"})
        return False

    try:
        data = r.json()
    except:
        print(f"{FAIL} Invalid JSON response")
        results.append({"test": test_name, "status": "FAIL", "reason": "invalid json"})
        return False

    metrics = analyze_plan(data, test_name)

    print(f"  Dni: {metrics['days']}  |  Atrakcje łącznie: {metrics['total_attractions']}  |  Restauracje: {metrics['total_restaurants']}")
    print(f"  Unique ratio: {metrics['unique_ratio']:.0%}")
    print(f"  Miasta: {metrics['cities']}")
    for ds in metrics['day_summaries']:
        print(f"    {ds}")
    if metrics['warnings']:
        for w in metrics['warnings'][:5]:
            print(f"  {WARN} {w}")
    if metrics['quality_score']:
        print(f"  Quality score: {metrics['quality_score']}")

    # Wbudowane asercje
    failed_checks = []
    if checks:
        for check_name, check_fn in checks:
            try:
                ok = check_fn(data, metrics)
                icon = PASS if ok else FAIL
                print(f"  {icon} CHECK: {check_name}")
                if not ok:
                    failed_checks.append(check_name)
            except Exception as e:
                print(f"  {FAIL} CHECK: {check_name} → EXCEPTION: {e}")
                failed_checks.append(check_name)

    status = "PASS" if not failed_checks else "PARTIAL"
    results.append({
        "test": test_name,
        "status": status,
        "elapsed": elapsed,
        "days": metrics['days'],
        "attractions": metrics['total_attractions'],
        "unique_ratio": metrics['unique_ratio'],
        "failed_checks": failed_checks,
    })
    return len(failed_checks) == 0


# ─────────────────────────────────────────────────────────────────
# TESTY
# ─────────────────────────────────────────────────────────────────

START_DATE = "2026-07-15"   # Lato

print("=" * 70)
print("E2E TEST SUITE — Travel Planner Backend")
print(f"Server: {BASE}")
print("=" * 70)

# ── Health check ──────────────────────────────────────────────────
try:
    r = requests.get(f"{BASE}/health", timeout=5)
    print(f"\nHealth check: HTTP {r.status_code}")
except:
    print("\nHealth endpoint N/A — sprawdzam /docs")
    try:
        r = requests.get(f"{BASE}/docs", timeout=5)
        print(f"Docs: HTTP {r.status_code}")
    except:
        print(f"{FAIL} Serwer niedostępny na {BASE}!")
        exit(1)

# ─────────────────────────────────────────────────────────────────
# TEST 1: Zakopane — para, 2 dni, zrównoważony
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — para, 2 dni, balanced",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
        "trip_length": {"days": 2, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "balanced",
        "preferences": ["nature_landscapes", "museums_heritage"],
    },
    checks=[
        ("≥2 dni", lambda d, m: m['days'] >= 2),
        ("≥3 atrakcje łącznie", lambda d, m: m['total_attractions'] >= 3),
        ("Unique ratio ≥70%", lambda d, m: m['unique_ratio'] >= 0.70),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 2: Zakopane — rodzina z dziećmi, 3 dni, atrakcje dla dzieci
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — rodzina+dzieci, 3 dni, kids+active",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "family_kids", "size": 4, "children_age": 8, "crowd_tolerance": 2},
        "trip_length": {"days": 3, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "18:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "balanced",
        "preferences": ["attractions_for_kids", "active_sport"],
    },
    checks=[
        ("≥3 dni", lambda d, m: m['days'] >= 3),
        ("≥6 atrakcji łącznie", lambda d, m: m['total_attractions'] >= 6),
        ("Unique ratio ≥70%", lambda d, m: m['unique_ratio'] >= 0.70),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 3: Zakopane — solo, 1 dzień, relaks/wellness
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — solo, 1 dzień, relaks",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "solo", "size": 1, "crowd_tolerance": 1},
        "trip_length": {"days": 1, "start_date": START_DATE},
        "daily_time_window": {"start": "10:00", "end": "20:00"},
        "budget": {"level": 3},
        "transport_modes": ["car"],
        "travel_style": "relax",
        "preferences": ["relax_wellness"],
    },
    checks=[
        ("=1 dzień", lambda d, m: m['days'] == 1),
        ("≥2 atrakcje", lambda d, m: m['total_attractions'] >= 2),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 4: Zakopane — seniorzy, 2 dni, kultura+historia
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — seniorzy, 2 dni, kultura",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "seniors", "size": 2, "crowd_tolerance": 1},
        "trip_length": {"days": 2, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "17:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "cultural",
        "preferences": ["museums_heritage", "history_mystery"],
    },
    checks=[
        ("≥2 dni", lambda d, m: m['days'] >= 2),
        ("≥3 atrakcje", lambda d, m: m['total_attractions'] >= 3),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 5: Zakopane — adventure (aktywny sport)
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — przyjaciele, 2 dni, adventure",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "friends", "size": 3, "crowd_tolerance": 3},
        "trip_length": {"days": 2, "start_date": START_DATE},
        "daily_time_window": {"start": "08:00", "end": "20:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "adventure",
        "preferences": ["active_sport", "mountain_trails"],
    },
    checks=[
        ("≥2 dni", lambda d, m: m['days'] >= 2),
        ("≥4 atrakcje", lambda d, m: m['total_attractions'] >= 4),
        ("Unique ratio ≥70%", lambda d, m: m['unique_ratio'] >= 0.70),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 6: Zakopane — niski budżet (level=1)
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — budżet tani (level=1)",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "friends", "size": 2, "crowd_tolerance": 2},
        "trip_length": {"days": 2, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": 1},
        "transport_modes": ["car"],
        "travel_style": "balanced",
        "preferences": [],
    },
    checks=[
        ("≥1 dzień wygenerowany", lambda d, m: m['days'] >= 1),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 7: Zakopane — brak preferencji (backwards compat)
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — brak preferencji (compatibility)",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
        "trip_length": {"days": 2, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "balanced",
        "preferences": [],
    },
    checks=[
        ("≥2 dni", lambda d, m: m['days'] >= 2),
        ("≥3 atrakcje", lambda d, m: m['total_attractions'] >= 3),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 8: Cluster — Trójmiasto (Gdańsk+Gdynia+Sopot)
# ─────────────────────────────────────────────────────────────────
run_test(
    "CLUSTER: Trójmiasto — 3 dni, multi-city",
    {
        "location": {"city": "Trójmiasto", "country": "Poland", "is_cluster": True},
        "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
        "trip_length": {"days": 3, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "balanced",
        "preferences": ["museums_heritage", "nature_landscapes"],
    },
    checks=[
        ("≥3 dni", lambda d, m: m['days'] >= 3),
        ("≥6 atrakcji łącznie", lambda d, m: m['total_attractions'] >= 6),
        ("Unique ratio ≥70%", lambda d, m: m['unique_ratio'] >= 0.70),
        ("Więcej niż 1 miasto", lambda d, m: len(m['cities']) >= 2),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 9: Kraków solo (nie-cluster, ale multi_city data)
# ─────────────────────────────────────────────────────────────────
run_test(
    "Kraków — solo, 2 dni, kulturalne",
    {
        "location": {"city": "Kraków", "country": "Poland"},
        "group": {"type": "solo", "size": 1, "crowd_tolerance": 2},
        "trip_length": {"days": 2, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "20:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "cultural",
        "preferences": ["museums_heritage", "history_mystery"],
    },
    checks=[
        ("≥2 dni", lambda d, m: m['days'] >= 2),
        ("≥4 atrakcje", lambda d, m: m['total_attractions'] >= 4),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 10: Wrocław multi-day
# ─────────────────────────────────────────────────────────────────
run_test(
    "Wrocław — przyjaciele, 3 dni",
    {
        "location": {"city": "Wrocław", "country": "Poland"},
        "group": {"type": "friends", "size": 4, "crowd_tolerance": 3},
        "trip_length": {"days": 3, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "21:00"},
        "budget": {"level": 2},
        "transport_modes": ["car", "walk"],
        "travel_style": "balanced",
        "preferences": ["museums_heritage", "local_food_experience"],
    },
    checks=[
        ("≥3 dni", lambda d, m: m['days'] >= 3),
        ("≥6 atrakcji", lambda d, m: m['total_attractions'] >= 6),
        ("Unique ≥70%", lambda d, m: m['unique_ratio'] >= 0.70),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 11: Walidacja — nieprawidłowy travel_style → 422
# ─────────────────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print("TEST: Walidacja — nieprawidłowy travel_style")
print(f"{'─'*70}")
r = requests.post(f"{BASE}/plan/preview", json={
    "location": {"city": "Zakopane", "country": "Poland"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
    "trip_length": {"days": 2, "start_date": START_DATE},
    "daily_time_window": {"start": "09:00", "end": "19:00"},
    "budget": {"level": 2},
    "transport_modes": ["car"],
    "travel_style": "INVALID_STYLE",
}, headers=HEADERS, timeout=10)
expected_422 = r.status_code == 422
print(f"HTTP {r.status_code} (oczekiwano 422)")
icon = PASS if expected_422 else FAIL
print(f"{icon} Walidacja travel_style → {r.status_code}")
results.append({"test": "Walidacja travel_style=INVALID", "status": "PASS" if expected_422 else "FAIL"})

# ─────────────────────────────────────────────────────────────────
# TEST 12: Walidacja — za dużo dni → 422
# ─────────────────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print("TEST: Walidacja — 15 dni (max=14)")
print(f"{'─'*70}")
r = requests.post(f"{BASE}/plan/preview", json={
    "location": {"city": "Zakopane", "country": "Poland"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
    "trip_length": {"days": 15, "start_date": START_DATE},
    "daily_time_window": {"start": "09:00", "end": "19:00"},
    "budget": {"level": 2},
    "transport_modes": ["car"],
}, headers=HEADERS, timeout=10)
expected_422 = r.status_code == 422
print(f"HTTP {r.status_code} (oczekiwano 422)")
icon = PASS if expected_422 else FAIL
print(f"{icon} Walidacja days=15 → {r.status_code}")
results.append({"test": "Walidacja days=15 (max=14)", "status": "PASS" if expected_422 else "FAIL"})


# ─────────────────────────────────────────────────────────────────
# TEST 13: Zakopane — zima, 5 dni (stress test)
# ─────────────────────────────────────────────────────────────────
run_test(
    "Zakopane — ZIMA, 5 dni, stress test",
    {
        "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
        "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
        "trip_length": {"days": 5, "start_date": "2026-12-26"},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "balanced",
        "preferences": ["active_sport", "relax_wellness", "museums_heritage"],
    },
    checks=[
        ("=5 dni", lambda d, m: m['days'] == 5),
        ("≥10 atrakcji łącznie", lambda d, m: m['total_attractions'] >= 10),
        ("Unique ratio ≥70%", lambda d, m: m['unique_ratio'] >= 0.70),
    ]
)

# ─────────────────────────────────────────────────────────────────
# TEST 14: Kotlina Kłodzka cluster
# ─────────────────────────────────────────────────────────────────
run_test(
    "CLUSTER: Kotlina Kłodzka — 3 dni",
    {
        "location": {"city": "Kotlina Kłodzka", "country": "Poland", "is_cluster": True},
        "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
        "trip_length": {"days": 3, "start_date": START_DATE},
        "daily_time_window": {"start": "09:00", "end": "19:00"},
        "budget": {"level": 2},
        "transport_modes": ["car"],
        "travel_style": "balanced",
        "preferences": ["nature_landscapes", "castles_palaces"],
    },
    checks=[
        ("≥3 dni", lambda d, m: m['days'] >= 3),
        ("≥5 atrakcji", lambda d, m: m['total_attractions'] >= 5),
    ]
)

# ─────────────────────────────────────────────────────────────────
# PODSUMOWANIE
# ─────────────────────────────────────────────────────────────────
print("\n\n" + "=" * 70)
print("PODSUMOWANIE E2E TESTS")
print("=" * 70)

passed = sum(1 for r in results if r["status"] == "PASS")
partial = sum(1 for r in results if r["status"] == "PARTIAL")
failed = sum(1 for r in results if r["status"] == "FAIL")
total = len(results)

print(f"\n{PASS} PASS:    {passed}/{total}")
print(f"{WARN} PARTIAL: {partial}/{total}")
print(f"{FAIL} FAIL:    {failed}/{total}")
print()

for r in results:
    icon = PASS if r["status"] == "PASS" else (WARN if r["status"] == "PARTIAL" else FAIL)
    extra = ""
    if r.get("elapsed"):
        extra += f" [{r['elapsed']:.1f}s]"
    if r.get("days"):
        extra += f" {r['days']}d/{r.get('attractions','?')}attr unique={r.get('unique_ratio',0):.0%}"
    if r.get("failed_checks"):
        extra += f" FAILED: {r['failed_checks']}"
    print(f"  {icon} {r['test']}{extra}")

# ─────────────────────────────────────────────────────────────────
# Analiza jakości planów — wypisz atrakcje z jednego planu
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SZCZEGÓŁOWY PLAN: Zakopane, para, 2 dni, balanced")
print("=" * 70)
r = requests.post(f"{BASE}/plan/preview", json={
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
    "trip_length": {"days": 2, "start_date": START_DATE},
    "daily_time_window": {"start": "09:00", "end": "19:00"},
    "budget": {"level": 2},
    "transport_modes": ["car"],
    "travel_style": "balanced",
    "preferences": ["nature_landscapes", "museums_heritage"],
}, headers=HEADERS, timeout=60)

if r.status_code == 200:
    data = r.json()
    for i, day in enumerate(data.get("days", [])):
        print(f"\nDzień {i+1} ({day.get('date', '')})")
        print(f"  Tytuł: {day.get('title', '')}")
        for item in day.get("items", []):
            t = item.get("type", "")
            poi = item.get("poi", {})
            name = poi.get("name", poi.get("Name", item.get("name", "?")))
            time_s = item.get("start_time", "")
            time_e = item.get("end_time", "")
            why = item.get("why_selected", "")[:60] if item.get("why_selected") else ""
            print(f"  [{time_s}-{time_e}] {t.upper():12} {name}")
            if why:
                print(f"               why: {why}")
else:
    print(f"Błąd: HTTP {r.status_code}")
