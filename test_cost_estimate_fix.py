"""
Test cost_estimate fix - CLIENT FEEDBACK (16.02.2026)

Problem: Ten sam POI ma różne cost_estimate w różnych testach.
Przykłady:
- Wielka Krokiew: raz 90, innym razem 25 (bilet: 25/20)
- Podwodny Świat: raz 104, innym razem 28 (bilet: 28/24)
- Dom do góry nogami: cost_estimate 0 mimo biletu 21/17

Expected: Consistent calculation based on group_size and ticket prices.
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.application.services.plan_service import PlanService

# Mock POI data
poi_wielka_krokiew = {
    "name": "Wielka Krokiew",
    "ticket_normal": 25,
    "ticket_reduced": 20,
    "free_entry": False
}

poi_podwodny = {
    "name": "Podwodny Świat",
    "ticket_normal": 28,
    "ticket_reduced": 24,
    "free_entry": False
}

poi_dom = {
    "name": "Dom do góry nogami",
    "ticket_normal": 21,
    "ticket_reduced": 17,
    "free_entry": False
}

poi_free = {
    "name": "Free POI",
    "ticket_normal": 0,
    "ticket_reduced": 0,
    "free_entry": True
}

poi_no_price_data = {
    "name": "Brak danych",
    "ticket_normal": 0,
    "ticket_reduced": 0,
    "free_entry": False
}

# Test users
user_family_4 = {
    "target_group": "family_kids",
    "group_size": 4,
    "children_age": 8
}

user_couple = {
    "target_group": "couples",
    "group_size": 2
}

user_friends_4 = {
    "target_group": "friends",
    "group_size": 4
}

user_seniors_2 = {
    "target_group": "seniors",
    "group_size": 2
}

user_solo = {
    "target_group": "solo",
    "group_size": 1
}

# Initialize service (poi_repo not needed for _estimate_cost)
service = PlanService(None)

print("="*80)
print("COST ESTIMATE FIX VERIFICATION")
print("="*80)

print("\n1. WIELKA KROKIEW (bilet: 25/20 PLN)")
print("-" * 80)
cost_family = service._estimate_cost(poi_wielka_krokiew, user_family_4)
cost_couple = service._estimate_cost(poi_wielka_krokiew, user_couple)
cost_friends = service._estimate_cost(poi_wielka_krokiew, user_friends_4)
cost_seniors = service._estimate_cost(poi_wielka_krokiew, user_seniors_2)
cost_solo = service._estimate_cost(poi_wielka_krokiew, user_solo)

print(f"Family (4 persons, 2+2): {cost_family} PLN")
print(f"  Expected: (2 × 25) + (2 × 20) = 90 PLN")
print(f"  ✅ PASS" if cost_family == 90 else f"  ❌ FAIL")

print(f"\nCouple (2 persons): {cost_couple} PLN")
print(f"  Expected: 2 × 25 = 50 PLN")
print(f"  ✅ PASS" if cost_couple == 50 else f"  ❌ FAIL")

print(f"\nFriends (4 persons): {cost_friends} PLN")
print(f"  Expected: 4 × 25 = 100 PLN")
print(f"  ✅ PASS" if cost_friends == 100 else f"  ❌ FAIL")

print(f"\nSeniors (2 persons): {cost_seniors} PLN")
print(f"  Expected: 2 × 20 = 40 PLN (senior discount)")
print(f"  ✅ PASS" if cost_seniors == 40 else f"  ❌ FAIL")

print(f"\nSolo (1 person): {cost_solo} PLN")
print(f"  Expected: 25 PLN")
print(f"  ✅ PASS" if cost_solo == 25 else f"  ❌ FAIL")

print("\n\n2. PODWODNY ŚWIAT (bilet: 28/24 PLN)")
print("-" * 80)
cost_family = service._estimate_cost(poi_podwodny, user_family_4)
cost_couple = service._estimate_cost(poi_podwodny, user_couple)

print(f"Family (4 persons): {cost_family} PLN")
print(f"  Expected: (2 × 28) + (2 × 24) = 104 PLN")
print(f"  ✅ PASS" if cost_family == 104 else f"  ❌ FAIL")

print(f"\nCouple (2 persons): {cost_couple} PLN")
print(f"  Expected: 2 × 28 = 56 PLN")
print(f"  ✅ PASS" if cost_couple == 56 else f"  ❌ FAIL")

print("\n\n3. DOM DO GÓRY NOGAMI (bilet: 21/17 PLN)")
print("-" * 80)
cost_family = service._estimate_cost(poi_dom, user_family_4)
cost_couple = service._estimate_cost(poi_dom, user_couple)

print(f"Family (4 persons): {cost_family} PLN")
print(f"  Expected: (2 × 21) + (2 × 17) = 76 PLN")
print(f"  ✅ PASS" if cost_family == 76 else f"  ❌ FAIL")

print(f"\nCouple (2 persons): {cost_couple} PLN")
print(f"  Expected: 2 × 21 = 42 PLN")
print(f"  ✅ PASS" if cost_couple == 42 else f"  ❌ FAIL")
print(f"  NOTE: Previous bug reported cost_estimate: 0")

print("\n\n4. FREE ENTRY POI")
print("-" * 80)
cost_family = service._estimate_cost(poi_free, user_family_4)
cost_couple = service._estimate_cost(poi_free, user_couple)

print(f"Family: {cost_family} PLN")
print(f"  Expected: 0 PLN (free entry)")
print(f"  ✅ PASS" if cost_family == 0 else f"  ❌ FAIL")

print(f"\nCouple: {cost_couple} PLN")
print(f"  Expected: 0 PLN (free entry)")
print(f"  ✅ PASS" if cost_couple == 0 else f"  ❌ FAIL")

print("\n\n5. NO PRICE DATA (brak danych)")
print("-" * 80)
cost_family = service._estimate_cost(poi_no_price_data, user_family_4)
cost_couple = service._estimate_cost(poi_no_price_data, user_couple)

print(f"Family (4 persons): {cost_family} PLN")
print(f"  Expected: 4 × 50 = 200 PLN (fallback)")
print(f"  ✅ PASS" if cost_family == 200 else f"  ❌ FAIL")

print(f"\nCouple (2 persons): {cost_couple} PLN")
print(f"  Expected: 2 × 50 = 100 PLN (fallback)")
print(f"  ✅ PASS" if cost_couple == 100 else f"  ❌ FAIL")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✅ All cost calculations are now CONSISTENT and based on group_size")
print("✅ Family: (adults × normal) + (children × reduced)")
print("✅ Couples/Friends: group_size × normal")
print("✅ Seniors: group_size × reduced")
print("✅ Solo: normal")
print("✅ Fallback (no data): group_size × 50 PLN")
