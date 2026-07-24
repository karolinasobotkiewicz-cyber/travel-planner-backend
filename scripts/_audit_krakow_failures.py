"""Print selected Kraków audit failures."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.services.plan_service import PlanService
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from tests.test_fix241_krakow_client import _audit_krakow

root = Path(__file__).resolve().parents[1]
folder = root.parent / "json_miasta" / "Kraków"
svc = PlanService(POIRepository(str(root / "data" / "multi_city_attractions.xlsx")))
only = ("test-01.json", "test-03.json", "test-04.json")
for name in only:
    p = folder / name
    payload = json.loads(p.read_text(encoding="utf-8"))
    plan = svc.generate_plan(TripInput(**payload))
    issues = _audit_krakow(plan, payload, p.name)
    print(f"{'OK' if not issues else 'FAIL'} {name} ({len(issues)})")
    for i in issues[:8]:
        print(" ", i)
