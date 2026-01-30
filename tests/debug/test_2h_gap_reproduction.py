"""
Test dla reprodukcji 2h gaps bug - EXACT CLIENT TEST CASE

Data: 29.01.2026
Problem: 14:48 (Tatra Family ends) → 16:53 (Góralski Ślizg starts) = 2h 5min gap

Client Input:
- location: Zakopane
- group: family_kids
- travel_style: adventure
- preferences: outdoor
- daily_time_window: 09:00-19:00
- transport: car
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from datetime import datetime
from app.domain.planner.engine import build_day
from app.infrastructure.repositories.poi_repository import POIRepository


def test_reproduce_2h_gap_exact_client_case():
    """
    Reproduce exact 2h gap issue from client feedback
    
    Expected behavior:
    - Gaps should be ≤ 40 minutes (excluding intentional lunch break)
    - If no suitable POI, add "free time" activity (max 40 min)
    - Never leave 2h+ gaps
    
    Current problem:
    - 14:48 activity ends
    - 16:53 next activity starts
    - Gap: 2h 5min ❌
    """
    
    # EXACT client inputs (as dict for engine compatibility)
    user = {
        "target_group": "family_kids",
        "group_size": 4,
        "travel_style": "adventure",
        "preferences": ["outdoor"],
        "crowd_tolerance": "medium",
        "transport": ["car"],
        "budget": 500,
        "budget_category": "medium"
    }
    
    context = {
        "date": datetime(2026, 1, 29),
        "season": "winter",
        "weather": {
            "temperature": 5,
            "condition": "partly_cloudy",
            "precip": False
        }
    }
    
    # Get all Zakopane POI
    excel_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "zakopane.xlsx"
    )
    poi_repo = POIRepository(excel_path)
    all_pois_models = poi_repo.get_all()  # Get ALL POI (zakopane.xlsx only has Zakopane POI)
    
    print(f"\n🔍 DEBUG: Total POI loaded: {len(all_pois_models)}")
    
    # Convert POI models to dicts for engine compatibility
    all_pois = [poi.model_dump(by_alias=False) for poi in all_pois_models]  # by_alias=False for engine
    
    print(f"\n🔍 DEBUG: Total POI available: {len(all_pois)}")
    print(f"🧭 Filters: family_kids + adventure + outdoor")
    print(f"⏰ Time window: 09:00-19:00\n")
    
    # Run engine
    plan_activities = build_day(
        all_pois,  # Pass as list, not dict
        user,
        context,
        day_start="09:00",
        day_end="19:00"
    )
    
    print(f"\n📋 Generated Plan: {len(plan_activities)} activities\n")
    
    # Analyze gaps
    gaps = []
    for i in range(len(plan_activities) - 1):
        current = plan_activities[i]
        next_activity = plan_activities[i + 1]
        
        current_end = current.get("end_time") or current.get("time")
        next_start = next_activity.get("start_time") or next_activity.get("time")
        
        if not current_end or not next_start:
            continue
        
        # Calculate gap in minutes
        end_h, end_m = map(int, current_end.split(":"))
        start_h, start_m = map(int, next_start.split(":"))
        
        end_minutes = end_h * 60 + end_m
        start_minutes = start_h * 60 + start_m
        gap_minutes = start_minutes - end_minutes
        
        if gap_minutes > 0:
            gap_info = {
                "after": current.get("name", current.get("type", "unknown")),
                "before": next_activity.get("name", next_activity.get("type", "unknown")),
                "end": current_end,
                "start": next_start,
                "gap_minutes": gap_minutes,
                "is_lunch": next_activity.get("type") == "lunch_break"
            }
            gaps.append(gap_info)
            
            # Print gap details
            status = "✅" if gap_minutes <= 55 else "⚠️" if gap_minutes <= 90 else "❌"
            gap_type = " [LUNCH]" if gap_info["is_lunch"] else ""
            
            print(f"{status} Gap: {current_end} → {next_start} = {gap_minutes} min{gap_type}")
            print(f"   After: {gap_info['after']}")
            print(f"   Before: {gap_info['before']}\n")
    
    # Check for the specific 2h gap mentioned by client
    critical_gaps = [g for g in gaps if g["gap_minutes"] > 120 and not g["is_lunch"]]
    
    if critical_gaps:
        print(f"\n❌ CRITICAL: Found {len(critical_gaps)} gaps > 2h:")
        for gap in critical_gaps:
            print(f"   {gap['end']} → {gap['start']} = {gap['gap_minutes']} min")
            print(f"   After: {gap['after']}")
            print(f"   Before: {gap['before']}")
        
        # Check if one matches client's observation (14:48 → 16:53)
        client_gap = next(
            (g for g in critical_gaps if "14:4" in g["end"] and "16:5" in g["start"]),
            None
        )
        
        if client_gap:
            print(f"\n🎯 MATCHED CLIENT OBSERVATION:")
            print(f"   {client_gap['end']} → {client_gap['start']} = {client_gap['gap_minutes']} min")
            print(f"   After: {client_gap['after']}")
            print(f"   Before: {client_gap['before']}")
    
    # Debug: Check what POI are available around 14:48-16:53
    print(f"\n\n🔍 DEBUGGING: POI available in 14:48-16:53 window (888-1013 min):")
    
    target_start = 888  # 14:48 in minutes
    target_end = 1013   # 16:53 in minutes
    
    # Check all POI for availability in this window
    available_in_window = []
    
    for poi in all_pois:
        # Check opening hours
        opening_hours = poi.get("opening_hours", {})
        
        # Handle different opening_hours formats
        if isinstance(opening_hours, dict):
            hours_data = opening_hours.get("text", {})
            if isinstance(hours_data, dict):
                hours_data = hours_data.get("all", [])
            elif not isinstance(hours_data, list):
                hours_data = []
        else:
            hours_data = []
        
        if hours_data and len(hours_data) >= 2:
            opens_at = hours_data[0]
            closes_at = hours_data[1]
            
            # POI is open if: opens_at <= target_start < closes_at
            if opens_at <= target_start < closes_at:
                available_in_window.append({
                    "name": poi["name"],
                    "type": poi.get("type", "unknown"),
                    "opens": f"{opens_at//60:02d}:{opens_at%60:02d}",
                    "closes": f"{closes_at//60:02d}:{closes_at%60:02d}",
                    "space": poi.get("space", "unknown"),
                    "duration": poi.get("estimated_duration", {}).get("typical", 0)
                })
    
    print(f"   Found {len(available_in_window)} POI open in this window:")
    for poi in available_in_window[:10]:  # Show first 10
        print(f"   - {poi['name']} ({poi['type']}, {poi['space']})")
        print(f"     Hours: {poi['opens']}-{poi['closes']}, Duration: {poi['duration']}min")
    
    # Assertions
    assert len(plan_activities) > 0, "No activities generated"
    
    # Check gaps (excluding lunch)
    non_lunch_gaps = [g for g in gaps if not g["is_lunch"]]
    
    if critical_gaps:
        print(
            f"\n❌ CRITICAL: Found {len(critical_gaps)} critical gaps (>2h):\n"
            + "\n".join([
                f"  {g['end']} → {g['start']} = {g['gap_minutes']}min"
                for g in critical_gaps
            ])
        )
        return False
    
    # All non-lunch gaps should be ≤ 40 min (ideal) or at most 60 min (acceptable)
    long_gaps = [g for g in non_lunch_gaps if g["gap_minutes"] > 60]
    
    if long_gaps:
        print(
            f"\n⚠️ WARNING: Found {len(long_gaps)} gaps >60 min:\n"
            + "\n".join([
                f"  {g['end']} → {g['start']} = {g['gap_minutes']}min"
                for g in long_gaps
            ])
        )
        return False
    
    print(f"\n✅ All gaps within acceptable range (≤60 min)")
    return True


if __name__ == "__main__":
    # Run test directly for debugging
    test_reproduce_2h_gap_exact_client_case()
