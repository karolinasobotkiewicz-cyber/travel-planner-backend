import json, sys, os
sys.stdout.reconfigure(encoding="utf-8")

def print_day(di, day):
    print(f"  --- Day {di+1} ---")
    for x in day.get("items", []):
        t = x.get("type")
        if t in ("day_start", "day_end"):
            print(f"  {t}: {x.get('time')}")
        elif t == "attraction":
            print(f"  ATTRACTION: {x['name']} {x['start_time']}-{x['end_time']} ({x['duration_min']}min)")
        elif t == "free_time":
            print(f"  FREE_TIME: {x['start_time']}-{x['end_time']} ({x['duration_min']}min) [{x.get('label','')}]")
        elif t == "lunch_break":
            print(f"  LUNCH: {x['start_time']}-{x['end_time']} ({x['duration_min']}min)")
        elif t == "transit":
            print(f"  TRANSIT: {x['start_time']} {x.get('from')}->{x.get('to')} ({x['duration_min']}min)")
        elif t == "parking":
            pass  # skip parking for clarity

for i in range(1, 11):
    fname = f"test_results_uat_round2/test-0{i}-response.json"
    if not os.path.exists(fname):
        print(f"\nJSON{i}: NOT FOUND"); continue
    data = json.load(open(fname, encoding="utf-8"))
    days = data.get("days", [])
    print(f"\n{'='*60}")
    print(f"JSON{i}: {len(days)} days")
    for di, day in enumerate(days):
        print_day(di, day)
