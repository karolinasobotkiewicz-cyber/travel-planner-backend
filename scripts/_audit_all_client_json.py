"""Audit all client JSON fixtures — summary for FIX #239."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.services.plan_client_audit import audit_day
from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository

root = Path(__file__).resolve().parents[1]
json_root = root.parent / "json_miasta"
cities = ("Wrocław", "Warszawa", "Kraków", "Katowice", "Poznań")
excel = root / "data" / "multi_city_attractions.xlsx"
svc = PlanService(POIRepository(str(excel)))

failures = []
ok = 0
t0 = time.time()
for city in cities:
    folder = json_root / city
    if not folder.is_dir():
        continue
    for p in sorted(folder.glob("test-*.json")):
        payload = json.loads(p.read_text(encoding="utf-8"))
        plan = svc.generate_plan(TripInput(**payload))
        issues = []
        for day in plan.days:
            issues.extend(audit_day(day, day_label=f"{city}/{p.name} "))
        if issues:
            failures.append((f"{city}/{p.name}", issues))
        else:
            ok += 1
        print(f"{'OK' if not issues else 'FAIL'} {city}/{p.name} ({len(issues)} issues)")

print(f"\nDone in {time.time()-t0:.0f}s: ok={ok} fail={len(failures)}")
for name, iss in failures[:15]:
    print(f"  {name}: {iss[0]}")
sys.exit(1 if failures else 0)
