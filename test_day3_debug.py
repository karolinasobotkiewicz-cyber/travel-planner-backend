import sys, os, json, io
from contextlib import redirect_stdout
sys.path.insert(0, '.')
from app.domain.models.trip_input import TripInput
from app.infrastructure.repositories import POIRepository
from app.application.services.plan_service import PlanService

poi_repo = POIRepository('data/zakopane.xlsx')
service = PlanService(poi_repo)

with open('../Testy_Klientki/test-08.json', 'r', encoding='utf-8') as f:
    r8 = json.load(f)
trip8 = TripInput(**r8)

buf = io.StringIO()
with redirect_stdout(buf):
    result8 = service.generate_plan(trip8)

output = buf.getvalue()

# Find Day 3 debug output
lines = output.split('\n')
day3_start = None
day4_start = None
for i, line in enumerate(lines):
    if 'Building Day 3/' in line or '=== Building Day 3' in line or 'Day 3/' in line:
        day3_start = i
    if 'Building Day 4/' in line or '=== Building Day 4' in line or 'Day 4/' in line:
        day4_start = i
        break

if day3_start is not None and day4_start is not None:
    day3_lines = lines[day3_start:day4_start]
    for line in day3_lines:
        # Show trail-related lines and EXCLUDED/SKIP lines
        if any(x in line for x in ['TRAIL', 'trail', 'EXCLUDED', 'SKIP', 'termy', 'TERMY', 'selected', 'SELECTED', 'LIMITS', 'now=', 'Trail limit', 'Track', '[SCORE]']):
            print(line)
else:
    # Fall back to showing all lines with trail/termy/excluded mentions
    print("Day 3 section not found. Showing relevant lines from all output:")
    for line in lines:
        if any(x in line for x in ['TRAIL LIMIT', 'TRAIL TIMING', 'TRAIL FILTER', 'BOOSTED', 'Final trail']):
            print(line)
