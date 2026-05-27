import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, '.')
from app.infrastructure.repositories.load_multi_city import load_multi_city_poi
from app.domain.planner.engine import is_open, is_core_poi
from datetime import datetime

pois = load_multi_city_poi('data/multi_city_attractions.xlsx', ['Krakow'])
print(f'Total: {len(pois)} POIs for Krakow (ASCII)')

pois2 = load_multi_city_poi('data/multi_city_attractions.xlsx', ['Kraków'])
print(f'Total: {len(pois2)} POIs for Kraków (Polish)')

# Use whichever has results
all_pois = pois if len(pois) > 0 else pois2

if not all_pois:
    print("NO POIS FOUND - check city name in Excel")
    import openpyxl
    wb = openpyxl.load_workbook('data/multi_city_attractions.xlsx')
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    print(f"Headers: {headers}")
    # print first few city values
    for row in ws.iter_rows(min_row=2, max_row=5, values_only=True):
        print(dict(zip(headers, row)))
    sys.exit()

print(f"\nSample POI keys: {list(all_pois[0].keys())}")
print(f"\nFirst 3 POIs:")
for p in all_pois[:3]:
    print(f"  name={p.get('name')}, priority_level={p.get('priority_level')}, duration_min={p.get('duration_min')}, time_min={p.get('time_min')}")
    oh = p.get('opening_hours')
    print(f"  opening_hours type={type(oh).__name__}, val={str(oh)[:100]}")

# Check is_core_poi for all
core_count = sum(1 for p in all_pois if is_core_poi(p))
print(f"\nCore POIs: {core_count}/{len(all_pois)}")

# Check is_open
context = {'date': datetime(2025, 6, 20)}
open_results = []
for p in all_pois:
    result = is_open(p, 600, 90, 'summer', context)
    open_results.append(result)
open_count = sum(1 for r in open_results if r)
print(f"\nOpen at 10:00: {open_count}/{len(all_pois)}")
if open_count < len(all_pois):
    # Show a closed POI
    for i, (p, r) in enumerate(zip(all_pois, open_results)):
        if not r:
            print(f"  CLOSED: {p.get('name')}, OH={p.get('opening_hours')}")
            if i > 5:
                break

# Check priority field
has_priority = sum(1 for p in all_pois if p.get('priority') is not None)
print(f"\nHas 'priority' field: {has_priority}/{len(all_pois)}")
has_type_of_attr = sum(1 for p in all_pois if p.get('type_of_attraction'))
print(f"Has 'type_of_attraction': {has_type_of_attr}/{len(all_pois)}")
has_time_min = sum(1 for p in all_pois if p.get('time_min'))
print(f"Has 'time_min': {has_time_min}/{len(all_pois)}")
has_Name = sum(1 for p in all_pois if p.get('Name'))
print(f"Has 'Name' (uppercase): {has_Name}/{len(all_pois)}")
