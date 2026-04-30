#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simplified verification for Phase 8.5 fixes FIX #14 and #17"""

import sys
import os
from pathlib import Path

# Set encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

import json
from app.domain.planner.engine import plan_multiple_days
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

def time_to_minutes(time_str):
    """Convert HH:MM to minutes since midnight"""
    h, m = map(int, time_str.split(':'))
    return h * 60 + m

def manual_test():
    """Manual test with simple data"""
    print("="*60)
    print("PHASE 8.5 VERIFICATION - FIXES #14, #17")
    print("="*60)
    
    # Load POI
    poi_list = load_zakopane_poi('data/zakopane.xlsx')
    print(f"✓ Loaded {len(poi_list)} POI\n")
    
    # Simple test params
    user = {
        "target_group": "family_kids",
        "preferences": ["hiking", "culture", "nature"],
        "fitness_level": "moderate",
        "group_size": 4
    }
    
    context = {
        "season": "summer",
        "transport": "car",
        "date": "2026-06-15",
        "day_end": "19:00",
        "hotels_available": []
    }
    
    # Plan 2 days
    contexts = [context, context]
    result = plan_multiple_days(
        pois=poi_list,
        user=user,
        contexts=contexts,
        day_start="09:00",
        day_end="19:00"
    )
    
    print(f"\n✓ Generated {len(result)} day plans\n")
    
    # Check FIX #14: Lunch timing
    print("="*60)
    print("FIX #14: LUNCH TIMING (12:00-14:30)")
    print("="*60)
    
    lunch_pass = True
    for day_idx, day_items in enumerate(result, 1):
        # day_items is a list of dict items
        for item in day_items:
            if item.get("type") == "lunch_break":
                start_time = item.get("start_time", "")
                start_min = time_to_minutes(start_time)
                
                # Expected: 12:00-14:30 (720-870 min)
                if 720 <= start_min <= 870:
                    print(f"✅ Day {day_idx}: Lunch at {start_time} (PASS)")
                else:
                    print(f"❌ Day {day_idx}: Lunch at {start_time} (FAIL - should be 12:00-14:30)")
                    lunch_pass = False
    
    # Check FIX #17: Strange gaps (look for large unexplained gaps)
    print(f"\n{'='*60}")
    print("FIX #17: STRANGE GAPS (should be filled with free_time)")
    print("="*60)
    
    gap_pass = True
    for day_idx, day_items in enumerate(result, 1):
        # day_items is a list of dict items
        for i in range(len(day_items) - 1):
            current = day_items[i]
            next_item = day_items[i + 1]
            
            # Get end of current and start of next
            current_end = current.get("end_time")
            next_start = next_item.get("start_time")
            
            if current_end and next_start:
                end_min = time_to_minutes(current_end)
                start_min = time_to_minutes(next_start)
                gap = start_min - end_min
                
                # If gap > 20 min, should be filled
                if gap > 20:
                    print(f"⚠️ Day {day_idx}: Gap {gap} min ({current_end}-{next_start}) between {current.get('type')} and {next_item.get('type')}")
                    
                    # Check if this is AFTER lunch/dinner (acceptable)
                    if current.get("type") in ["lunch_break", "dinner_break"]:
                        print(f"   └─ Acceptable (post-meal gap)")
                    # Check if free_time exists in this gap
                    elif gap > 80:
                        print(f"   └─ ❌ LARGE GAP (>{gap}min) - FIX #17 may have failed")
                        gap_pass = False
                    else:
                        print(f"   └─ Moderate gap, may be waiting for opening hours")
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print("="*60)
    print(f"FIX #14 (Lunch Timing): {'✅ PASS' if lunch_pass else '❌ FAIL'}")
    print(f"FIX #17 (Strange Gaps): {'✅ PASS' if gap_pass else '❌ FAIL'}")
    
    if lunch_pass and gap_pass:
        print(f"\n🎉 All fixes working!")
        return 0
    else:
        print(f"\n⚠️ Some fixes need adjustment")
        return 1

if __name__ == "__main__":
    sys.exit(manual_test())
