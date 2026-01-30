"""
Live API test for bugfixes verification
Tests Fix #1 (day_start) and Fix #3 (gaps)
"""

import requests
import json
from datetime import datetime

API_URL = "https://travel-planner-backend-xbsp.onrender.com"

def test_health():
    """Test if API is alive"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=10)
        print(f"✅ Health check: {response.status_code}")
        print(f"   Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_day_start_fix():
    """
    Test Fix #1: day_start should be respected
    Input: start_time = 11:00
    Expected: First POI scheduled >= 11:00 (not 09:xx)
    """
    print("\n" + "="*60)
    print("TEST FIX #1: Day Start Respected")
    print("="*60)
    
    payload = {
        "location": {
            "city": "zakopane",
            "country": "Poland"
        },
        "group": {
            "type": "couples",
            "size": 2,
            "crowd_tolerance": 1
        },
        "trip_length": {
            "days": 1,
            "start_date": "2026-02-15"
        },
        "daily_time_window": {
            "start": "11:00",
            "end": "18:00"
        },
        "budget": {
            "total_budget": 500,
            "currency": "PLN",
            "budget_level": "medium"
        }
    }
    
    try:
        response = requests.post(
            f"{API_URL}/plan/preview",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n📦 Response Structure:")
            print(f"   Keys: {list(data.keys())}")
            
            # PlanResponse structure: plan_id, version, days (list of DayPlan)
            days = data.get("days", [])
            print(f"   Days: {len(days)}")
            
            plan = []
            if days:
                day_data = days[0]
                print(f"   Day 0 Keys: {list(day_data.keys())}")
                # DayPlan has 'items' not 'activities'
                plan = day_data.get("items", [])
            
            print(f"\n📋 Generated Plan ({len(plan)} activities):")
            
            first_poi = None
            for activity in plan:
                time = activity.get("start_time", "N/A")
                name = activity.get("name", "N/A")
                type_ = activity.get("type", "N/A")
                
                print(f"   {time}: {name} ({type_})")
                
                # Check for both 'poi' and 'attraction' types
                if type_ in ["poi", "attraction"] and first_poi is None:
                    first_poi = (time, name)
            
            if first_poi:
                time_str, name = first_poi
                print(f"\n🎯 First POI: {time_str} - {name}")
                
                # Parse time
                hour = int(time_str.split(":")[0])
                if hour >= 11:
                    print(f"✅ FIX #1 WORKS: First POI at {time_str} (>= 11:00)")
                    return True
                else:
                    print(f"❌ FIX #1 FAILED: First POI at {time_str} (< 11:00)")
                    return False
            else:
                print("⚠️ No POI found in plan")
                return False
        else:
            print(f"❌ Request failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_gaps_fix():
    """
    Test Fix #3: No 30-45 min gaps between POI
    Expected: Gaps should be minimal (5-15 min for transit)
    """
    print("\n" + "="*60)
    print("TEST FIX #3: No Scheduling Gaps")
    print("="*60)
    
    payload = {
        "location": {
            "city": "zakopane",
            "country": "Poland"
        },
        "group": {
            "type": "couples",
            "size": 2,
            "crowd_tolerance": 1
        },
        "trip_length": {
            "days": 1,
            "start_date": "2026-02-15"
        },
        "daily_time_window": {
            "start": "09:00",
            "end": "18:00"
        },
        "budget": {
            "total_budget": 500,
            "currency": "PLN",
            "budget_level": "medium"
        }
    }
    
    try:
        response = requests.post(
            f"{API_URL}/plan/preview",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Same structure fix for test_gaps_fix - use 'items' not 'activities'
            days = data.get("days", [])
            plan = days[0].get("items", []) if days else []
            
            print(f"\n📋 Timeline Analysis ({len(plan)} activities):")
            
            max_gap = 0
            problematic_gaps = []
            
            for i in range(len(plan) - 1):
                current = plan[i]
                next_act = plan[i + 1]
                
                # Skip lunch_break gaps - those are intentional
                if current.get("type") == "lunch_break" or next_act.get("type") == "lunch_break":
                    continue
                
                end_time = current.get("end_time", "N/A")
                next_start = next_act.get("start_time", "N/A")
                
                # Calculate gap
                if end_time != "N/A" and next_start != "N/A":
                    end_h, end_m = map(int, end_time.split(":"))
                    start_h, start_m = map(int, next_start.split(":"))
                    
                    end_minutes = end_h * 60 + end_m
                    start_minutes = start_h * 60 + start_m
                    gap = start_minutes - end_minutes
                    
                    print(f"   {end_time} → {next_start}: GAP = {gap} min ({current.get('type', 'N/A')} → {next_act.get('type', 'N/A')})")
                    
                    if gap > max_gap:
                        max_gap = gap
                    
                    if gap > 25:  # More than 25 min is suspicious (normal transit 5-15 min)
                        problematic_gaps.append({
                            "from": current.get("name"),
                            "to": next_act.get("name"),
                            "gap": gap,
                            "time": f"{end_time} → {next_start}"
                        })
            
            print(f"\n📊 Max gap: {max_gap} min")
            
            if problematic_gaps:
                print(f"\n⚠️ Found {len(problematic_gaps)} problematic gaps (>25 min):")
                for g in problematic_gaps:
                    print(f"   {g['time']}: {g['from']} → {g['to']} ({g['gap']} min)")
                print(f"\n❌ FIX #3 FAILED: Still has {max_gap} min gaps")
                return False
            else:
                print(f"\n✅ FIX #3 WORKS: All gaps <= 25 min (max: {max_gap} min)")
                return True
        else:
            print(f"❌ Request failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 LIVE BUGFIX VERIFICATION")
    print("API:", API_URL)
    print("="*60)
    
    # Step 1: Health check
    if not test_health():
        print("\n❌ API not responding - deployment may still be in progress")
        print("   Wait 2-3 minutes and try again")
        exit(1)
    
    # Step 2: Test fixes
    results = []
    results.append(("Fix #1: day_start", test_day_start_fix()))
    results.append(("Fix #3: gaps", test_gaps_fix()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n🎉 ALL BUGFIXES VERIFIED ON LIVE API")
    else:
        print("\n⚠️ SOME TESTS FAILED - Check logs above")
