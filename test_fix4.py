"""
Quick test script for FIX #4 - Gap Filling Enhancement.
Runs plan_service directly and analyzes gap distribution.
"""

import json
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.application.services.plan_service import PlanService
from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.models.trip_input import TripInput


def analyze_gaps(day_items):
    """Analyze gaps between items."""
    from app.domain.planner.time_utils import time_to_minutes
    
    gaps = []
    for i in range(len(day_items) - 1):
        current = day_items[i]
        next_item = day_items[i + 1]
        
        current_dict = current.dict() if hasattr(current, 'dict') else current
        next_dict = next_item.dict() if hasattr(next_item, 'dict') else next_item
        
        # Get end/start times
        current_end = current_dict.get('end_time')
        next_start = next_dict.get('start_time')
        
        if current_end and next_start:
            current_end_min = time_to_minutes(current_end)
            next_start_min = time_to_minutes(next_start)
            gap = next_start_min - current_end_min
            
            if gap > 0:
                gaps.append({
                    'from': f"{current_dict['type']} ends {current_end}",
                    'to': f"{next_dict['type']} starts {next_start}",
                    'gap_min': gap
                })
    
    return gaps


def main():
    # Load test-01.json
    test_file = Path(__file__).parent.parent / "Testy_Klientki" / "test-01.json"
    
    print(f"\n{'='*80}")
    print(f"FIX #4 TEST - Gap Filling Enhancement")
    print(f"{'='*80}\n")
    
    print(f"[*] Loading: {test_file}")
    
    with open(test_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    # Parse TripInput
    trip_input = TripInput(**test_data)
    
    # Create plan service
    poi_repo = POIRepository(excel_path="data/zakopane.xlsx")
    plan_service = PlanService(poi_repository=poi_repo)
    
    # Generate plan
    print("\n[*] Generating plan with FIX #4...\n")
    plan_response = plan_service.generate_plan(trip_input)
    
    print(f"[OK] Plan generated: {len(plan_response.days)} days\n")
    
    # Analyze each day
    for day in plan_response.days:
        print(f"\n{'─'*80}")
        print(f"[DAY] Day {day.day}")
        print(f"{'─'*80}")
        
        print(f"\n[ITEMS] {len(day.items)} total")
        
        # Count by type
        type_counts = {}
        free_time_items = []
        
        for item in day.items:
            item_dict = item.dict()
            item_type = item_dict['type']
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
            
            # Track free_time items
            if item_type == 'free_time':
                free_time_items.append(item_dict)
        
        print(f"   Types: {dict(sorted(type_counts.items()))}")
        
        # Analyze gaps
        gaps = analyze_gaps(day.items)
        
        if gaps:
            print(f"\n[WARNING] Gaps between items: {len(gaps)}")
            for g in gaps:
                print(f"   • {g['gap_min']:>3} min: {g['from']} → {g['to']}")
        else:
            print(f"\n[OK] No gaps >0 min between items (perfect timeline)")
        
        # Show free_time items
        if free_time_items:
            print(f"\n[FREE_TIME] Free time items: {len(free_time_items)}")
            for ft in free_time_items:
                label = ft.get('label', 'Czas wolny')
                duration = ft.get('duration_min', 0)
                start = ft.get('start_time')
                end = ft.get('end_time')
                print(f"   • {start}-{end} ({duration} min): {label}")
        
        # Check for end-of-day free time
        last_item = day.items[-1].dict()
        if last_item['type'] == 'free_time' and 'koniec' in last_item.get('label', '').lower():
            print(f"\n[OK] End-of-day free_time detected!")
        elif last_item['type'] == 'day_end':
            prev_item = day.items[-2].dict() if len(day.items) >= 2 else None
            if prev_item:
                from app.domain.planner.time_utils import time_to_minutes
                prev_end = time_to_minutes(prev_item.get('end_time', '00:00'))
                day_end_time = time_to_minutes(last_item.get('time', '19:00'))
                gap_to_end = day_end_time - prev_end
                
                if gap_to_end > 30:
                    print(f"\n[WARNING] Large gap to day_end: {gap_to_end} min (should add free_time!)")
                else:
                    print(f"\n[OK] Small gap to day_end: {gap_to_end} min (OK)")
    
    print(f"\n{'='*80}")
    print(f"FIX #4 TEST COMPLETE")
    print(f"{'='*80}\n")
    
    # Summary
    total_free_time = sum(
        1 for day in plan_response.days 
        for item in day.items 
        if item.dict()['type'] == 'free_time'
    )
    
    print(f"[SUMMARY]:")
    print(f"   • Total days: {len(plan_response.days)}")
    print(f"   • Total free_time items: {total_free_time}")
    print(f"   • Threshold: >15 min (was >20 min)")
    print(f"   • Lunch skip: <50 min (was <60 min)")
    print(f"   • End-of-day logic: active (>30 min gap)")


if __name__ == "__main__":
    main()
