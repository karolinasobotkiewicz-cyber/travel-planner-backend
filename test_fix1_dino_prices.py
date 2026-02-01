"""
Test cost estimation dla DINO PARK (brak cen → fallback 50 PLN)
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.application.services.plan_service import PlanService

pois = load_zakopane_poi('data/zakopane.xlsx')

dino = next((p for p in pois if 'DINO' in p['name'].upper()), None)

if not dino:
    print("❌ DINO PARK not found!")
    exit(1)

print(f"DINO PARK data:")
print(f"  ticket_normal: {dino.get('ticket_normal')}")
print(f"  ticket_reduced: {dino.get('ticket_reduced')}")
print(f"  free_entry: {dino.get('free_entry')}")
print()

# Test _estimate_cost() manually
plan_service = PlanService(None)

cost_family = plan_service._estimate_cost(dino, "family_kids")
cost_couple = plan_service._estimate_cost(dino, "couples")

print(f"Estimated costs:")
print(f"  family_kids: {cost_family} PLN (expected: 200 PLN = 4×50)")
print(f"  couples: {cost_couple} PLN (expected: 50 PLN)")
print()

if cost_family == 200 and cost_couple == 50:
    print("✅ FIX #1 SUCCESS - Fallback prices work!")
else:
    print(f"❌ FIX #1 FAILED - Expected 200/50, got {cost_family}/{cost_couple}")
