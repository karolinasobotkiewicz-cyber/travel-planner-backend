import json,sys,os
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
for i in range(1,11):
    fname=f"test_results_uat_round2/test-0{i}-response.json"
    if not os.path.exists(fname):
        print(f"JSON{i}: NOT FOUND"); continue
    data=json.load(open(fname,encoding="utf-8"))
    days=data.get("days",[])
    print(f"\n===== JSON{i}: {len(days)} days =====")
    for di,d in enumerate(days):
        items=d.get("items",[])
        A=[x for x in items if x.get("type")=="attraction"]
        L=[x for x in items if x.get("type")=="lunch_break"]
        FT=[x for x in items if x.get("type")=="free_time"]
        T=[x for x in items if x.get("type")=="transit"]
        an=[x.get("name","?") for x in A]
        fmin=sum(x.get("duration_min",0) for x in FT)
        ds=next((x.get("time") for x in items if x.get("type")=="day_start"),"?")
        de=next((x.get("time") for x in items if x.get("type")=="day_end"),"?")
        print(f"  Day{di+1}[{ds}-{de}] A({len(A)}):{an}")
        print(f"         FT:{len(FT)}x={fmin}min T:{len(T)} L:{len(L)}")
        for ft in FT: print(f"         FT {ft.get(\"start_time\")}-{ft.get(\"end_time\")} {ft.get(\"duration_min\")}min [{ft.get(\"label\",\"\")}]")
        for lx in L: print(f"         LUNCH {lx.get(\"start_time\")}-{lx.get(\"end_time\")} {lx.get(\"duration_min\")}min")
        tl=[f"{tx.get(\"from\",\"?\")}->{tx.get(\"to\",\"?\")}" for tx in T]
        for tx in T: print(f"         TR {tx.get(\"start_time\")}: {tx.get(\"from\")}->{tx.get(\"to\")} {tx.get(\"duration_min\")}min")
        dp={k:v for k,v in Counter(tl).items() if v>1}
        if dp: print(f"         !! DUP TRANSIT: {dp}")

