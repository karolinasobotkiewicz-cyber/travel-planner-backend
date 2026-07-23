"""Quick audit one client JSON (dev helper)."""
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
json_path = root.parent / "json_miasta" / "Wrocław" / "test-01.json"
if len(sys.argv) > 1:
    json_path = Path(sys.argv[1])

excel = root / "data" / "multi_city_attractions.xlsx"
svc = PlanService(POIRepository(str(excel)))
payload = json.loads(json_path.read_text(encoding="utf-8"))
t0 = time.time()
plan = svc.generate_plan(TripInput(**payload))
print(f"generated in {time.time()-t0:.1f}s")
issues = []
for day in plan.days:
    issues.extend(audit_day(day, day_label=f"{json_path.name} "))
print(f"issues: {len(issues)}")
for msg in issues[:20]:
    print(" -", msg)
