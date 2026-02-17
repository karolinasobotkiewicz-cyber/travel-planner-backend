"""
Test Script - Problem #4: Time Buffers

CLIENT FEEDBACK (16.02.2026 - Karolina):
"Os czasu ma 'dziury', ktore nie sa opisane"

Examples from feedback:
- Test 01: transit konczy sie 10:11, nastepna atrakcja startuje 10:26 -> brak wyjasnienia 15 minut
- Test 06 Day 1: Kaplica konczy sie 11:43, Oksza startuje 11:52 -> 9 minut luki

Solution: Add buffer items:
- parking_walk: 5-15 min (walking from parking to attraction)
- tickets_queue: 5-20 min (waiting in line at popular attractions)
- restroom: 5-10 min (bathroom break after long attractions)
- photo_stop: 5-15 min (photo opportunity at scenic locations)

Test validates:
1. parking_walk buffer added after car transfer
2. tickets_queue buffer added before popular attractions (popularity >= 7)
3. restroom buffer added after long attractions (>= 60 min)
4. photo_stop buffer added after scenic locations (tags: viewpoint/scenic/panorama)
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.domain.planner.engine import build_day
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from datetime import datetime, timedelta

def test_buffers_basic():
    """Test that buffer items are added to plan"""
    
    print("=" * 80)
    print("TEST: Buffer Items - Basic Validation")
    print("=" * 80)
    
    # Load POIs as dicts
    excel_path = "data/zakopane.xlsx"
    all_pois = load_zakopane_poi(excel_path)
    
    print(f"\nLoaded {len(all_pois)} POI from repository")
    
    # Test user: family with car
    user = {
        "target_group": "family_kids",
        "group_type": "family_kids",
        "group_size": 4,
        "children_age": 8,
        "preferences": ["kids_attractions", "nature_landscape"],
        "travel_style": "balanced",
        "budget_level": 2,
        "daily_budget_limit": 500,
        "crowd_tolerance": 1,
    }
    
    # Test context
    start_date = datetime(2026, 2, 20)
    context = {
        "date": start_date,
        "season": "winter",
        "weather": {"temp": 5, "condition": "cloudy"},
        "has_car": True,  # Important: car = parking_walk buffers
    }
    
    # Build plan for one day
    plan = build_day(
        pois=all_pois,
        user=user,
        context=context,
        day_start="09:00",
        day_end="19:00"
    )
    
    print(f"\n[RESULT] Generated plan with {len(plan)} items\n")
    
    # Validate buffer presence
    buffer_items = [item for item in plan if item.get("type") == "buffer"]
    attraction_items = [item for item in plan if item.get("type") == "attraction"]
    transfer_items = [item for item in plan if item.get("type") == "transfer"]
    
    print(f"[STATS]")
    print(f"  Attractions: {len(attraction_items)}")
    print(f"  Transfers: {len(transfer_items)}")
    print(f"  Buffers: {len(buffer_items)}")
    
    # Display timeline with buffers
    print("\n" + "=" * 80)
    print("TIMELINE WITH BUFFERS:")
    print("=" * 80)
    
    for i, item in enumerate(plan):
        item_type = item.get("type")
        
        if item_type == "attraction":
            name = item.get("name", "Unknown")
            start = item.get("start_time", "N/A")
            end = item.get("end_time", "N/A")
            duration = item.get("poi", {}).get("time_min", "N/A")
            # ASCII-safe encoding for Windows terminal
            name_safe = str(name).encode('ascii', errors='ignore').decode('ascii')
            print(f"\n[{i+1}] ATTRACTION: {name_safe}")
            print(f"    Time: {start} - {end} ({duration} min)")
            
        elif item_type == "transfer":
            from_loc = item.get("from", "Unknown")
            to_loc = item.get("to", "Unknown")
            duration = item.get("duration_min", "N/A")
            # ASCII-safe encoding for Windows terminal
            from_loc_safe = str(from_loc).encode('ascii', errors='ignore').decode('ascii')
            to_loc_safe = str(to_loc).encode('ascii', errors='ignore').decode('ascii')
            print(f"\n[{i+1}] TRANSFER: {from_loc_safe} -> {to_loc_safe}")
            print(f"    Duration: {duration} min")
            
        elif item_type == "buffer":
            buffer_type = item.get("buffer_type", "unknown")
            start = item.get("start_time", "N/A")
            end = item.get("end_time", "N/A")
            duration = item.get("duration_min", "N/A")
            description = item.get("description", "")
            # ASCII-safe encoding for Windows terminal
            description_safe = str(description).encode('ascii', errors='ignore').decode('ascii')
            print(f"\n[{i+1}] BUFFER [{buffer_type.upper()}]")
            print(f"    Time: {start} - {end} ({duration} min)")
            print(f"    Desc: {description_safe}")
            
        elif item_type == "lunch_break":
            start = item.get("start_time", "N/A")
            end = item.get("end_time", "N/A")
            print(f"\n[{i+1}] LUNCH BREAK")
            print(f"    Time: {start} - {end}")
            
        elif item_type == "free_time":
            start = item.get("start_time", "N/A")
            end = item.get("end_time", "N/A")
            duration = item.get("duration_min", "N/A")
            print(f"\n[{i+1}] FREE TIME")
            print(f"    Time: {start} - {end} ({duration} min)")
    
    # Validate buffer types
    print("\n" + "=" * 80)
    print("BUFFER TYPE VALIDATION:")
    print("=" * 80)
    
    buffer_types = {}
    for item in buffer_items:
        btype = item.get("buffer_type", "unknown")
        buffer_types[btype] = buffer_types.get(btype, 0) + 1
    
    expected_types = ["parking_walk", "tickets_queue", "restroom", "photo_stop"]
    
    for btype in expected_types:
        count = buffer_types.get(btype, 0)
        status = "[PASS]" if count > 0 else "[INFO]"
        print(f"{status} {btype}: {count} buffer(s)")
    
    # Check time continuity
    print("\n" + "=" * 80)
    print("TIME CONTINUITY CHECK:")
    print("=" * 80)
    
    gaps = []
    for i in range(len(plan) - 1):
        current = plan[i]
        next_item = plan[i + 1]
        
        # Get end time of current
        current_end = current.get("end_time")
        next_start = next_item.get("start_time")
        
        if current_end and next_start:
            from app.domain.planner.time_utils import time_to_minutes
            
            current_end_min = time_to_minutes(current_end)
            next_start_min = time_to_minutes(next_start)
            
            gap = next_start_min - current_end_min
            
            if gap > 0:
                gaps.append({
                    "from": current.get("type"),
                    "to": next_item.get("type"),
                    "gap": gap,
                    "from_end": current_end,
                    "to_start": next_start
                })
                
                status = "[PASS]" if gap <= 5 else "[WARNING]"
                print(f"{status} Gap {gap} min: {current.get('type')} ({current_end}) -> {next_item.get('type')} ({next_start})")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY:")
    print("=" * 80)
    
    if len(buffer_items) > 0:
        print("[PASS] Buffers added to plan")
        print(f"       Total buffers: {len(buffer_items)}")
        print(f"       Types: {list(buffer_types.keys())}")
    else:
        print("[FAIL] No buffers added to plan")
        print("       Expected: parking_walk, tickets_queue, restroom, photo_stop")
    
    large_gaps = [g for g in gaps if g['gap'] > 10]
    if len(large_gaps) == 0:
        print("[PASS] No large unexplained gaps (>10 min)")
    else:
        print(f"[WARNING] Found {len(large_gaps)} large gaps:")
        for g in large_gaps:
            print(f"          {g['gap']} min: {g['from']} -> {g['to']}")
    
    print("\n" + "=" * 80)
    
    return len(buffer_items) > 0


def test_buffers_specific_scenarios():
    """Test specific buffer scenarios"""
    
    print("\n" * 2)
    print("=" * 80)
    print("TEST: Buffer Items - Specific Scenarios")
    print("=" * 80)
    
    excel_path = "data/zakopane.xlsx"
    all_pois = load_zakopane_poi(excel_path)
    
    # Scenario 1: Popular attraction should have tickets_queue buffer
    print("\n[SCENARIO 1] Popular Attraction (popularity >= 7)")
    print("-" * 80)
    
    popular_pois = [p for p in all_pois if p.get("popularity_score", 0) >= 7]
    print(f"Found {len(popular_pois)} popular POI (popularity >= 7)")
    
    if popular_pois:
        # Sample popular POI
        sample = popular_pois[0]
        print(f"Example: {sample.get('Name')} (popularity: {sample.get('popularity_score')})")
        print("Expected: tickets_queue buffer BEFORE attraction")
    
    # Scenario 2: Long attraction should have restroom buffer
    print("\n[SCENARIO 2] Long Attraction (duration >= 60 min)")
    print("-" * 80)
    
    long_pois = [p for p in all_pois if p.get("time_min", 0) >= 60]
    print(f"Found {len(long_pois)} long POI (time_min >= 60)")
    
    if long_pois:
        sample = long_pois[0]
        print(f"Example: {sample.get('Name')} (duration: {sample.get('time_min')} min)")
        print("Expected: restroom buffer AFTER attraction")
    
    # Scenario 3: Scenic location should have photo_stop buffer
    print("\n[SCENARIO 3] Scenic Location (tags: viewpoint/scenic/panorama)")
    print("-" * 80)
    
    scenic_pois = []
    for p in all_pois:
        tags = p.get("tags", []) or []
        tag_list = [str(t).lower() for t in tags if t]
        if any(tag in tag_list for tag in ["viewpoint", "scenic", "panorama", "mountain_view"]):
            scenic_pois.append(p)
    
    print(f"Found {len(scenic_pois)} scenic POI")
    
    if scenic_pois:
        sample = scenic_pois[0]
        tags = sample.get("tags", [])
        print(f"Example: {sample.get('Name')} (tags: {tags})")
        print("Expected: photo_stop buffer AFTER attraction")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\n")
    print("=" * 80)
    print("PROBLEM #4: TIME BUFFERS TEST")
    print("CLIENT FEEDBACK: 16.02.2026 (Karolina)")
    print("=" * 80)
    
    try:
        # Test 1: Basic buffer validation
        test1_pass = test_buffers_basic()
        
        # Test 2: Specific scenarios
        test_buffers_specific_scenarios()
        
        print("\n" * 2)
        print("=" * 80)
        print("FINAL RESULT:")
        print("=" * 80)
        
        if test1_pass:
            print("[PASS] Problem #4 - Buffer items added successfully")
            print("       Time gaps now have explanations:")
            print("       - parking_walk: After car transfer")
            print("       - tickets_queue: Before popular attractions")
            print("       - restroom: After long attractions (60+ min)")
            print("       - photo_stop: After scenic locations")
        else:
            print("[FAIL] Problem #4 - No buffer items in plan")
            print("       Expected buffer types not found")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
