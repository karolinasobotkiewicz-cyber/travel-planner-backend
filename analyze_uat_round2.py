import json, sys, os
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

for i in range(1, 11):
    fname = f'test_results_uat_round2/test-0{i}-response.json' if i < 10 else f'test_results_uat_round2/test-{i}-response.json'
    if not os.path.exists(fname):
        print(f'JSON{i}: FILE NOT FOUND')
        continue
    try:
        with open(fname, encoding='utf-8') as f:
            data = json.load(f)
        days = data.get('days', data.get('itinerary', []))
        profile = data.get('profile', data.get('user', {}).get('target_group', '?'))
        prefs = data.get('preferences', [])
        print(f'\n=== JSON{i}: {len(days)} days | profile={profile} | prefs={prefs} ===')
        for d in days:
            items = d.get('items', [])
            poi_names = [x.get('name','?') for x in items if x.get('type') in ['poi','trail']]
            ft_mins = sum(x.get('duration_min',0) for x in items if x.get('type') == 'free_time')
            ft_count = sum(1 for x in items if x.get('type') == 'free_time')
            lunch_items = [x for x in items if x.get('type') == 'lunch']
            transit_items = [x for x in items if x.get('type') == 'transfer']
            total_min = sum(x.get('duration_min',0) for x in items)
            day_n = d.get('day_number','?')
            print(f'  Day {day_n} — POI: {poi_names}')
            print(f'         free_time: {ft_count}x = {ft_mins}min | transits: {len(transit_items)} | lunch: {len(lunch_items)}')
            # Show lunch location_context
            for lx in lunch_items:
                lc = lx.get('location_context','')
                lt = lx.get('start_time','?')
                print(f'         -> lunch@{lt} location_context={lc}')
            # Show duplicate transits
            transit_names = [f"{x.get('from_name','?')}→{x.get('to_name','?')}" for x in transit_items]
            from collections import Counter
            dup = {k:v for k,v in Counter(transit_names).items() if v > 1}
            if dup:
                print(f'         !! DUPLICATE TRANSITS: {dup}')
    except Exception as e:
        import traceback
        print(f'JSON{i}: ERROR {e}')
        traceback.print_exc()
