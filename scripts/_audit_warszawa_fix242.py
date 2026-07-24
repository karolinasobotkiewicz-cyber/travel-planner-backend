"""Audit Warszawa test-01..10 for FIX #242."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from tests.test_fix242_warszawa_client import _audit_warszawa

root = Path(__file__).resolve().parents[1]
folder = root.parent / "json_miasta" / "Warszawa"
svc = PlanService(POIRepository(str(root / "data" / "multi_city_attractions.xlsx")))
t0 = time.time()
fail = 0
for p in sorted(folder.glob("test-*.json")):
    payload = json.loads(p.read_text(encoding="utf-8"))
    plan = svc.generate_plan(TripInput(**payload))
    issues = _audit_warszawa(plan, payload, p.name)
    print(f"{'OK' if not issues else 'FAIL'} {p.name} ({len(issues)})")
    for i in issues[:6]:
        print(" ", i)
    if issues:
        fail += 1
print(f"done {time.time()-t0:.0f}s fail={fail}")
sys.exit(1 if fail else 0)
