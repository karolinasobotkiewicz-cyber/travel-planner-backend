# FIX #247 Warszawa audit
from tests.test_fix247_warszawa_client import _audit_warszawa_247, _paths
import json
from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from pathlib import Path

svc = PlanService(POIRepository("data/multi_city_attractions.xlsx"))
total = ok = 0
for p in _paths():
    payload = json.loads(p.read_text(encoding="utf-8"))
    plan = svc.generate_plan(TripInput(**payload))
    issues = _audit_warszawa_247(plan, payload, p.name)
    total += 1
    if issues:
        print(f"FAIL {p.name}: {'; '.join(issues)}")
    else:
        ok += 1
        print(f"OK   {p.name}")
print(f"\n{ok}/{total}")
