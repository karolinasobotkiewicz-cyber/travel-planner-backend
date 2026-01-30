"""
Verification script for client issues reported on 30.01.2026

ISSUES TO VERIFY:
1. Podwodny Świat scheduled at 9:17 - opens at 10:00
2. Muzeum Oscypka on Sunday (15.02) - only open Saturday
3. KULIGI at 14:24 - starts at 15:00
4. Travel time 5 min should be ~20 min between distant POI
5. recommended_time_of_day penalty weak
"""
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "")))

from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.planner.engine import build_day
from app.domain.planner.opening_hours_parser import is_poi_open_at_time

# Load POI data
excel_path = os.path.join(os.path.dirname(__file__), "data", "zakopane.xlsx")
poi_repo = POIRepository(excel_path)
all_pois_models = poi_repo.get_all()
all_pois = [poi.model_dump(by_alias=False) for poi in all_pois_models]

print(f"✅ Loaded {len(all_pois)} POI from zakopane.xlsx\n")

# Find specific POI
podwodny_swiat = next((p for p in all_pois if "Podwodny" in p.get("name", "")), None)
muzeum_oscypka = next((p for p in all_pois if "Oscypka" in p.get("name", "")), None)
kuligi = next((p for p in all_pois if "KULIGI" in p.get("name", "")), None)

print("=" * 80)
print("ISSUE #1: Podwodny Świat at 9:17 (opens 10:00)")
print("=" * 80)
if podwodny_swiat:
    oh = podwodny_swiat.get("opening_hours")
    oh_seasonal = podwodny_swiat.get("opening_hours_seasonal")
    print(f"POI: {podwodny_swiat['name']}")
    print(f"Opening hours: {oh}")
    print(f"Seasonal: {oh_seasonal}")
    
    # Test 9:17 (557 minutes) on arbitrary weekday
    current_date = (2026, 2, 15)  # Sunday
    weekday = 6  # Sunday = 6
    result = is_poi_open_at_time(oh, oh_seasonal, current_date, weekday, 557, 60)
    print(f"\n🧪 Test: Can visit at 9:17 (557 min) for 60 min?")
    print(f"   Result: {result}")
    print(f"   Expected: False (opens at 10:00 = 600 min)")
    print(f"   Status: {'✅ PASS' if not result else '❌ FAIL'}")
    
    # Test 10:00 (should work)
    result_10 = is_poi_open_at_time(oh, oh_seasonal, current_date, weekday, 600, 60)
    print(f"\n🧪 Test: Can visit at 10:00 (600 min) for 60 min?")
    print(f"   Result: {result_10}")
    print(f"   Expected: True")
    print(f"   Status: {'✅ PASS' if result_10 else '❌ FAIL'}")
else:
    print("❌ Podwodny Świat not found!")

print("\n" + "=" * 80)
print("ISSUE #2: Muzeum Oscypka on Sunday (opens only Saturday)")
print("=" * 80)
if muzeum_oscypka:
    oh = muzeum_oscypka.get("opening_hours")
    oh_seasonal = muzeum_oscypka.get("opening_hours_seasonal")
    print(f"POI: {muzeum_oscypka['name']}")
    print(f"Opening hours: {oh}")
    print(f"Seasonal: {oh_seasonal}")
    
    # Test Sunday 15.02.2026
    current_date = (2026, 2, 15)  # Sunday
    weekday = 6  # Sunday = 6
    result = is_poi_open_at_time(oh, oh_seasonal, current_date, weekday, 780, 60)
    print(f"\n🧪 Test: Can visit on Sunday at 13:00 (780 min) for 60 min?")
    print(f"   Result: {result}")
    print(f"   Expected: False (only open Saturday)")
    print(f"   Status: {'✅ PASS' if not result else '❌ FAIL'}")
    
    # Test Saturday 14.02.2026
    current_date_sat = (2026, 2, 14)  # Saturday
    weekday_sat = 5  # Saturday = 5
    result_sat = is_poi_open_at_time(oh, oh_seasonal, current_date_sat, weekday_sat, 930, 60)
    print(f"\n🧪 Test: Can visit on Saturday at 15:30 (930 min) for 60 min?")
    print(f"   Result: {result_sat}")
    print(f"   Expected: True")
    print(f"   Status: {'✅ PASS' if result_sat else '❌ FAIL'}")
else:
    print("❌ Muzeum Oscypka not found!")

print("\n" + "=" * 80)
print("ISSUE #3: KULIGI at 14:24 (starts at 15:00)")
print("=" * 80)
if kuligi:
    oh = kuligi.get("opening_hours")
    oh_seasonal = kuligi.get("opening_hours_seasonal")
    print(f"POI: {kuligi['name']}")
    print(f"Opening hours: {oh}")
    print(f"Seasonal: {oh_seasonal}")
    print(f"Recommended time: {kuligi.get('recommended_time_of_day')}")
    
    # Test 14:24 (864 minutes)
    current_date = (2026, 2, 15)
    weekday = 6
    result = is_poi_open_at_time(oh, oh_seasonal, current_date, weekday, 864, 120)
    print(f"\n🧪 Test: Can visit at 14:24 (864 min) for 120 min?")
    print(f"   Result: {result}")
    print(f"   Expected: False (opens at 15:00 = 900 min)")
    print(f"   Status: {'✅ PASS' if not result else '❌ FAIL'}")
    
    # Test 15:00 (should work)
    result_15 = is_poi_open_at_time(oh, oh_seasonal, current_date, weekday, 900, 120)
    print(f"\n🧪 Test: Can visit at 15:00 (900 min) for 120 min?")
    print(f"   Result: {result_15}")
    print(f"   Expected: True")
    print(f"   Status: {'✅ PASS' if result_15 else '❌ FAIL'}")
else:
    print("❌ KULIGI not found!")

print("\n" + "=" * 80)
print("ISSUE #4: Travel time calculation (driving distance)")
print("=" * 80)
from app.domain.planner.engine import haversine_distance, travel_time_minutes

# Test distance between Muzeum and Kulig (should be ~20 min)
if muzeum_oscypka and kuligi:
    lat1, lng1 = muzeum_oscypka.get("lat"), muzeum_oscypka.get("lng")
    lat2, lng2 = kuligi.get("lat"), kuligi.get("lng")
    
    print(f"From: {muzeum_oscypka['name']} ({lat1}, {lng1})")
    print(f"To: {kuligi['name']} ({lat2}, {lng2})")
    
    distance = haversine_distance(lat1, lng1, lat2, lng2)
    print(f"\n📏 Haversine distance: {distance:.2f} km")
    
    context = {"has_car": True}
    travel_time = travel_time_minutes(muzeum_oscypka, kuligi, context)
    print(f"⏱️  Travel time: {travel_time} minutes")
    print(f"   (45 km/h + 5 min parking)")
    print(f"   Expected: ~15-25 minutes")
    print(f"   Status: {'✅ PASS' if 15 <= travel_time <= 25 else '❌ FAIL'}")

print("\n" + "=" * 80)
print("ISSUE #5: time_of_day scoring (penalty increased to -45)")
print("=" * 80)
from app.domain.scoring.time_of_day_scoring import calculate_time_of_day_score

if kuligi:
    # Test KULIGI (afternoon) scheduled in morning (should have strong penalty)
    morning_time = 540  # 09:00
    score_morning = calculate_time_of_day_score(kuligi, {}, {}, morning_time)
    print(f"POI: {kuligi['name']}")
    print(f"Recommended: {kuligi.get('recommended_time_of_day')}")
    print(f"\n🧪 Test: Score when scheduled at 09:00 (morning)")
    print(f"   Result: {score_morning}")
    print(f"   Expected: -25 or worse (strong penalty)")
    print(f"   Status: {'✅ PASS' if score_morning <= -20 else '❌ FAIL'}")
    
    # Test afternoon time (should be positive)
    afternoon_time = 960  # 16:00
    score_afternoon = calculate_time_of_day_score(kuligi, {}, {}, afternoon_time)
    print(f"\n🧪 Test: Score when scheduled at 16:00 (afternoon)")
    print(f"   Result: {score_afternoon}")
    print(f"   Expected: +10 (exact match)")
    print(f"   Status: {'✅ PASS' if score_afternoon == 10 else '❌ FAIL'}")

print("\n" + "=" * 80)
print("ISSUE #6: description_short and address in response")
print("=" * 80)
if podwodny_swiat:
    desc = podwodny_swiat.get("description_short", "")
    addr = podwodny_swiat.get("address", "")
    print(f"POI: {podwodny_swiat['name']}")
    print(f"Description short: '{desc}'")
    print(f"Address: '{addr}'")
    print(f"\n✅ PASS: Fields present" if (desc or addr) else "❌ FAIL: Fields missing")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("All validation checks completed.")
print("Review results above to confirm fixes are working.")
print("\n✅ Tests should show:")
print("  1. Podwodny Świat NOT allowed before 10:00")
print("  2. Muzeum Oscypka NOT allowed on Sunday")
print("  3. KULIGI NOT allowed before 15:00")
print("  4. Travel time ~15-25 min between distant POI")
print("  5. Strong penalty (-25 to -45) for wrong time_of_day")
print("  6. description_short and address present")
