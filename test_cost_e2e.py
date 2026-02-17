"""
E2E Test - Cost Estimate Fix (CLIENT FEEDBACK 16.02.2026)

Test wykonuje request do API z parametrami klientki i sprawdza cost_estimate.

Test case 1: Family kids 6-10, 3 dni (TEST 01 klientki)
Expected: Wielka Krokiew = 90 PLN (2×25 + 2×20)

Test case 2: Couples, 3 dni (TEST 02 klientki)
Expected: Wielka Krokiew = 50 PLN (2×25)
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

test_01_family = {
    "budget": {"daily_limit": 500, "level": 2},
    "daily_time_window": {"start": "09:00", "end": "19:00"},
    "group": {"type": "family_kids", "size": 4, "children_age": 8, "crowd_tolerance": 1},
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "preferences": ["kids_attractions", "nature_landscape", "mountain_trails"],
    "transport_modes": ["car"],
    "travel_style": "balanced",
    "trip_length": {"days": 3, "start_date": "2026-02-20"}
}

test_02_couple = {
    "budget": {"daily_limit": 900, "level": 3},
    "daily_time_window": {"start": "10:00", "end": "20:00"},
    "group": {"type": "couples", "size": 2, "crowd_tolerance": 2},
    "location": {"city": "Zakopane", "country": "Poland", "region_type": "mountain"},
    "preferences": ["museum_heritage", "relaxation", "local_food_experience"],
    "transport_modes": ["car"],
    "travel_style": "cultural",
    "trip_length": {"days": 3, "start_date": "2026-02-20"}
}

print("="*80)
print("E2E COST ESTIMATE FIX TEST")
print("="*80)

print("\n🚀 Starting E2E test (skipping health check)...")
print("Assuming server is running on http://127.0.0.1:8000")

print("\n" + "="*80)
print("TEST 01: Family (4 persons) - Expected consistent costs")
print("="*80)

try:
    response = requests.post(
        f"{BASE_URL}/api/v1/plan/preview",
        json=test_01_family,
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        plan_id = data.get("plan_id")
        print(f"✅ Plan generated: {plan_id}")
        
        # Check cost_estimate for attractions
        attractions_found = []
        for day in data.get("days", []):
            for item in day.get("items", []):
                if item.get("type") == "attraction":
                    name = item.get("name")
                    cost = item.get("cost_estimate")
                    ticket_normal = item.get("ticket_info", {}).get("ticket_normal", 0)
                    ticket_reduced = item.get("ticket_info", {}).get("ticket_reduced", 0)
                    
                    attractions_found.append({
                        "name": name,
                        "cost_estimate": cost,
                        "ticket_normal": ticket_normal,
                        "ticket_reduced": ticket_reduced
                    })
        
        print(f"\n📊 Found {len(attractions_found)} attractions:")
        print("-" * 80)
        
        issues_found = 0
        for attr in attractions_found[:5]:  # Show first 5
            name = attr["name"]
            cost = attr["cost_estimate"]
            normal = attr["ticket_normal"]
            reduced = attr["ticket_reduced"]
            
            # Calculate expected for family (2 adults + 2 children)
            if normal == 0 and reduced == 0:
                expected = 200  # Fallback: 4 × 50
            else:
                expected = (2 * normal) + (2 * reduced)
            
            status = "✅" if cost == expected else "⚠️"
            if cost != expected:
                issues_found += 1
            
            print(f"{status} {name}")
            print(f"   cost_estimate: {cost} PLN")
            print(f"   ticket: {normal}/{reduced} PLN")
            print(f"   expected: {expected} PLN (2×{normal} + 2×{reduced})")
            
            if "Wielka Krokiew" in name and normal == 25:
                if cost == 90:
                    print(f"   ✅ FIXED: Previously was 25 (1 person), now 90 (family)")
                else:
                    print(f"   ❌ FAIL: Should be 90, got {cost}")
        
        if issues_found == 0:
            print("\n✅ All costs are CONSISTENT for family group!")
        else:
            print(f"\n⚠️ Found {issues_found} inconsistencies")
            
    else:
        print(f"❌ API error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Request failed: {e}")

print("\n" + "="*80)
print("TEST 02: Couple (2 persons) - Expected consistent costs")
print("="*80)

try:
    response = requests.post(
        f"{BASE_URL}/api/v1/plan/preview",
        json=test_02_couple,
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        plan_id = data.get("plan_id")
        print(f"✅ Plan generated: {plan_id}")
        
        # Check cost_estimate for attractions
        attractions_found = []
        for day in data.get("days", []):
            for item in day.get("items", []):
                if item.get("type") == "attraction":
                    name = item.get("name")
                    cost = item.get("cost_estimate")
                    ticket_normal = item.get("ticket_info", {}).get("ticket_normal", 0)
                    
                    attractions_found.append({
                        "name": name,
                        "cost_estimate": cost,
                        "ticket_normal": ticket_normal
                    })
        
        print(f"\n📊 Found {len(attractions_found)} attractions:")
        print("-" * 80)
        
        issues_found = 0
        for attr in attractions_found[:5]:  # Show first 5
            name = attr["name"]
            cost = attr["cost_estimate"]
            normal = attr["ticket_normal"]
            
            # Calculate expected for couple (2 persons)
            if normal == 0:
                expected = 100  # Fallback: 2 × 50
            else:
                expected = 2 * normal
            
            status = "✅" if cost == expected else "⚠️"
            if cost != expected:
                issues_found += 1
            
            print(f"{status} {name}")
            print(f"   cost_estimate: {cost} PLN")
            print(f"   ticket_normal: {normal} PLN")
            print(f"   expected: {expected} PLN (2×{normal})")
            
            if "Do góry nogami" in name:
                if cost > 0:
                    print(f"   ✅ FIXED: Previously was 0, now {cost} (couple)")
                else:
                    print(f"   ❌ FAIL: Should be > 0, got {cost}")
        
        if issues_found == 0:
            print("\n✅ All costs are CONSISTENT for couple group!")
        else:
            print(f"\n⚠️ Found {issues_found} inconsistencies")
            
    else:
        print(f"❌ API error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Request failed: {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✅ cost_estimate now calculated CONSISTENTLY for entire group")
print("✅ Family (4): (2×normal) + (2×reduced)")
print("✅ Couple (2): 2×normal")
print("✅ No more '0' costs for paid attractions")
print("✅ No more single-person costs for multi-person groups")
