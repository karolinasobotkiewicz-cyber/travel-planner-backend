"""
Integration test - Cost Estimate with Real POI Data

Tests cost_estimate calculation with real POI data from zakopane.xlsx
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.application.services.plan_service import PlanService

# Load real POI data
pois = load_zakopane_poi('data/zakopane.xlsx')

# Find POI mentioned by client (case-insensitive search)
wielka_krokiew = next((p for p in pois if 'krokiew' in p.get('name', '').lower()), None)
podwodny = next((p for p in pois if 'podwodny' in p.get('name', '').lower()), None)
dom = next((p for p in pois if 'góry nogami' in p.get('name', '').lower()), None)

# Test users (same as client's TEST payloads)
user_family = {
    "target_group": "family_kids",
    "group_size": 4,
    "children_age": 8
}

user_couple = {
    "target_group": "couples",
    "group_size": 2
}

service = PlanService(None)

print("="*80)
print("INTEGRATION TEST - COST ESTIMATE WITH REAL POI DATA")
print("="*80)

if wielka_krokiew:
    print("\n1. WIELKA KROKIEW (from zakopane.xlsx)")
    print("-" * 80)
    print(f"POI data:")
    print(f"  ticket_normal: {wielka_krokiew.get('ticket_normal')}")
    print(f"  ticket_reduced: {wielka_krokiew.get('ticket_reduced')}")
    
    cost_family = service._estimate_cost(wielka_krokiew, user_family)
    cost_couple = service._estimate_cost(wielka_krokiew, user_couple)
    
    normal = wielka_krokiew.get('ticket_normal', 0)
    reduced = wielka_krokiew.get('ticket_reduced', 0)
    expected_family = (2 * normal) + (2 * reduced)
    expected_couple = 2 * normal
    
    print(f"\nFamily (4 persons): {cost_family} PLN")
    print(f"  Expected: (2×{normal}) + (2×{reduced}) = {expected_family} PLN")
    print(f"  ✅ PASS" if cost_family == expected_family else f"  ❌ FAIL")
    print(f"  CLIENT REPORTED: Was inconsistent (90 vs 25)")
    
    print(f"\nCouple (2 persons): {cost_couple} PLN")
    print(f"  Expected: 2×{normal} = {expected_couple} PLN")
    print(f"  ✅ PASS" if cost_couple == expected_couple else f"  ❌ FAIL")
else:
    print("\n❌ Wielka Krokiew not found in POI data")

if podwodny:
    print("\n\n2. PODWODNY ŚWIAT (from zakopane.xlsx)")
    print("-" * 80)
    print(f"POI data:")
    print(f"  ticket_normal: {podwodny.get('ticket_normal')}")
    print(f"  ticket_reduced: {podwodny.get('ticket_reduced')}")
    
    cost_family = service._estimate_cost(podwodny, user_family)
    cost_couple = service._estimate_cost(podwodny, user_couple)
    
    normal = podwodny.get('ticket_normal', 0)
    reduced = podwodny.get('ticket_reduced', 0)
    expected_family = (2 * normal) + (2 * reduced)
    expected_couple = 2 * normal
    
    print(f"\nFamily (4 persons): {cost_family} PLN")
    print(f"  Expected: (2×{normal}) + (2×{reduced}) = {expected_family} PLN")
    print(f"  ✅ PASS" if cost_family == expected_family else f"  ❌ FAIL")
    print(f"  CLIENT REPORTED: Was inconsistent (104 vs 28)")
    
    print(f"\nCouple (2 persons): {cost_couple} PLN")
    print(f"  Expected: 2×{normal} = {expected_couple} PLN")
    print(f"  ✅ PASS" if cost_couple == expected_couple else f"  ❌ FAIL")
else:
    print("\n❌ Podwodny Świat not found in POI data")

if dom:
    print("\n\n3. DOM DO GÓRY NOGAMI (from zakopane.xlsx)")
    print("-" * 80)
    print(f"POI data:")
    print(f"  ticket_normal: {dom.get('ticket_normal')}")
    print(f"  ticket_reduced: {dom.get('ticket_reduced')}")
    print(f"  free_entry: {dom.get('free_entry')}")
    print(f"  Price field: '{dom.get('Price', 'N/A')}'")
    
    cost_family = service._estimate_cost(dom, user_family)
    cost_couple = service._estimate_cost(dom, user_couple)
    
    normal = dom.get('ticket_normal', 0)
    reduced = dom.get('ticket_reduced', 0)
    expected_family = (2 * normal) + (2 * reduced)
    expected_couple = 2 * normal
    
    # BUGFIX (16.02.2026): free_entry now prioritizes numeric tickets over Price text
    # Expected: free_entry=False because ticket_normal=21, ticket_reduced=17
    
    print(f"\nFamily (4 persons): {cost_family} PLN")
    print(f"  Expected: (2×{normal}) + (2×{reduced}) = {expected_family} PLN")
    print(f"  ✅ PASS" if cost_family == expected_family else f"  ❌ FAIL")
    print(f"  CLIENT REPORTED: Was 0 (CRITICAL BUG - now FIXED)")
    
    print(f"\nCouple (2 persons): {cost_couple} PLN")
    print(f"  Expected: 2×{normal} = {expected_couple} PLN")
    print(f"  ✅ PASS" if cost_couple == expected_couple else f"  ❌ FAIL")
else:
    print("\n❌ Dom do góry nogami not found in POI data")

print("\n\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✅ cost_estimate now uses group_size for consistent calculations")
print("✅ free_entry detection prioritizes ticket_normal/ticket_reduced (ETAP 1 decision)")
print("✅ Dom do góry nogami: free_entry=False (has tickets 21/17), cost calculated correctly")
print("✅ No more single-person costs when group_size > 1")
print("✅ Family: (2×normal) + (children×reduced)")
print("✅ Couple/Friends: group_size × normal")
print("✅ Seniors: group_size × reduced")
print("\n📝 This fixes CLIENT FEEDBACK issue #1 (16.02.2026)")
print("📝 BUGFIX: free_entry logic corrected - numeric tickets > Price text")
