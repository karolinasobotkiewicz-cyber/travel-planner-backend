"""
Final test: Call production endpoint locally to verify gap filling works
"""
import requests
import json

# Production-like request
request_data = {
    "trip_start_date": "2026-02-16",
    "trip_length": {
        "start_date": "2026-02-16",
        "end_date": "2026-02-16",
        "days": 1
    },
    "destination": {
        "city": "Zakopane",
        "country": "Poland"
    },
    "group": {
        "type": "family_kids",
        "size": 4,
        "children_ages": [5, 8]
    },
    "interests": ["zoo", "dinozaury", "rodzina"],
    "budget_level": "medium",
    "transport_modes": ["car"],
    "intensity": "normal"
}

print("=" * 80)
print("TESTING GAP FILLING - LOCAL SERVER")
print("=" * 80)
print("\nSending request to http://localhost:8000/api/v1/plan/generate")
print(f"With interests: {request_data['interests']}")
print(f"Transport: {request_data['transport_modes']} (includes parking!)\n")

try:
    response = requests.post(
        "http://localhost:8000/api/v1/plan/generate",
        json=request_data,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print("✓ Plan generated successfully!\n")
        print("=" * 80)
        print("CHECKING FOR GAPS:")
        print("=" * 80)
        
        from app.domain.planner.time_utils import time_to_minutes
        
        items = data['days'][0]['items']
        last_end = None
        gaps_found = []
        free_times = 0
        
        for i, item in enumerate(items):
            item_type = item['type']
            
            # Count free_time items
            if item_type == 'free_time':
                free_times += 1
                print(f"\n✓ FREE_TIME: {item['start_time']}-{item['end_time']} (FILLED GAP!)")
            
            # Get end time
            current_end = None
            if item_type in ['attraction', 'transit', 'lunch_break', 'parking']:
                if 'end_time' in item:
                    current_end = time_to_minutes(item['end_time'])
                    if item_type == 'parking' and 'walk_time_min' in item:
                        current_end += item['walk_time_min']
            elif item_type == 'day_start':
                if 'time' in item:
                    current_end = time_to_minutes(item['time'])
            
            if current_end is None:
                continue
            
            # Check gap to next
            if i < len(items) - 1:
                next_item = items[i + 1]
                next_type = next_item['type']
                
                if next_type in ['attraction', 'lunch_break']:
                    next_start = time_to_minutes(next_item['start_time'])
                    gap = next_start - current_end
                    
                    if gap > 20:
                        gaps_found.append({
                            'from': item_type,
                            'from_name': item.get('name', item.get('to_location', '')),
                            'to': next_type,
                            'to_name': next_item.get('name', ''),
                            'gap_min': gap,
                            'end': current_end,
                            'next_start': next_start
                        })
        
        print("\n" + "=" * 80)
        print("RESULTS:")
        print("=" * 80)
        
        print(f"\nTotal items: {len(items)}")
        print(f"Free time items: {free_times}")
        print(f"Unfilled gaps >20 min: {len(gaps_found)}")
        
        if gaps_found:
            print("\n❌ GAPS NOT FILLED:")
            for gap in gaps_found:
                print(f"  • {gap['from']} ({gap['from_name']}) → {gap['to']} ({gap['to_name']})")
                print(f"    Gap: {gap['gap_min']} min (should be filled!)")
        else:
            print("\n✅ SUCCESS! No unfilled gaps >20 min found!")
            if free_times > 0:
                print(f"   {free_times} gap(s) were filled with free_time items")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to server!")
    print("\nStart the server first:")
    print("  cd travel-planner-backend")
    print("  uvicorn app.api.main:app --reload")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
