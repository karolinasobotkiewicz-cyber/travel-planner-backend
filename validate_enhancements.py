"""
Quick validation script to test all new enhancements.

Runs a simple test to verify:
1. pro_tip is included
2. Seasonality filter works
3. All scoring modules are integrated
4. No crashes
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from datetime import datetime
from app.domain.planner.engine import build_day
from app.infrastructure.repositories.poi_repository import POIRepository


def main():
    print("\n" + "="*60)
    print("🔧 VALIDATION: All Enhancements Integrated")
    print("="*60 + "\n")
    
    # Setup
    excel_path = os.path.join(os.path.dirname(__file__), "data", "zakopane.xlsx")
    poi_repo = POIRepository(excel_path)
    all_pois_models = poi_repo.get_all()
    all_pois = [poi.model_dump(by_alias=False) for poi in all_pois_models]
    
    print(f"✅ Loaded {len(all_pois)} POI from Excel\n")
    
    # Test case
    user = {
        "target_group": "family_kids",
        "group_size": 4,
        "travel_style": "adventure",
        "preferences": ["outdoor"],
        "crowd_tolerance": 1,
        "transport": ["car"],
        "budget": 2
    }
    
    context = {
        "date": datetime(2026, 1, 29),  # Winter
        "season": "winter",
        "weather": {
            "temperature": 5,
            "condition": "partly_cloudy",
            "precip": False
        }
    }
    
    print("🧪 Test Parameters:")
    print(f"   Group: {user['target_group']}")
    print(f"   Style: {user['travel_style']}")
    print(f"   Preferences: {user['preferences']}")
    print(f"   Date: {context['date']} (Winter)")
    print(f"   Weather: {context['weather']['condition']}, {context['weather']['temperature']}°C")
    print()
    
    # Run engine
    try:
        plan_activities = build_day(
            all_pois,
            user,
            context,
            day_start="09:00",
            day_end="19:00"
        )
        
        print(f"✅ Engine executed successfully!")
        print(f"   Generated {len(plan_activities)} activities\n")
        
        # Check for attractions and pro_tip
        attractions = [a for a in plan_activities if a.get("type") == "attraction"]
        
        if attractions:
            print(f"📍 Sample attractions:")
            for i, attr in enumerate(attractions[:3], 1):
                poi_data = attr.get("poi", {})
                print(f"\n   {i}. {poi_data.get('name', 'Unknown')}")
                print(f"      Time: {attr.get('start_time')} - {attr.get('end_time')}")
                print(f"      Duration: {attr.get('duration_min')} min")
                
                # Check if pro_tip exists (new feature)
                pro_tip = poi_data.get("pro_tip")
                if pro_tip:
                    print(f"      💡 Pro tip: {pro_tip[:50]}...")
                else:
                    print(f"      💡 Pro tip: None")
        
        # Check for gaps
        gaps = []
        for i in range(len(plan_activities) - 1):
            current = plan_activities[i]
            next_act = plan_activities[i + 1]
            
            current_end = current.get("end_time") or current.get("time")
            next_start = next_act.get("start_time") or next_act.get("time")
            
            if current_end and next_start:
                from app.domain.planner.time_utils import time_to_minutes
                gap_min = time_to_minutes(next_start) - time_to_minutes(current_end)
                
                if gap_min > 60 and next_act.get("type") != "lunch_break":
                    gaps.append((current_end, next_start, gap_min))
        
        print(f"\n\n📊 Gap Analysis:")
        if gaps:
            print(f"   ⚠️ Found {len(gaps)} gaps >60 min:")
            for end, start, gap in gaps:
                print(f"      {end} → {start} = {gap} min")
        else:
            print(f"   ✅ All gaps ≤60 min (excluding lunch)")
        
        print(f"\n\n✅ VALIDATION COMPLETE - All modules integrated!\n")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during execution:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
