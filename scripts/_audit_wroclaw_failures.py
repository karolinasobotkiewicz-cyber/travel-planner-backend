"""Quick audit for failing Wrocław JSONs only."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from tests.test_fix240_wroclaw_client import _audit_wroclaw

root = Path(__file__).resolve().parents[1]
folder = root.parent / "json_miasta" / "Wrocław"
svc = PlanService(POIRepository(str(root / "data" / "multi_city_attractions.xlsx")))
t0 = time.time()
fail = 0
for name in ("test-02.json", "test-08.json", "test-09.json"):
    p = folder / name
    payload = json.loads(p.read_text(encoding="utf-8"))
    plan = svc.generate_plan(TripInput(**payload))
    issues = _audit_wroclaw(plan, payload, p.name)
    print(f"{'OK' if not issues else 'FAIL'} {p.name} ({len(issues)})")
    for i in issues[:8]:
        print(" ", i)
    if issues:
        fail += 1
print(f"done {time.time()-t0:.0f}s fail={fail}")
sys.exit(1 if fail else 0)
