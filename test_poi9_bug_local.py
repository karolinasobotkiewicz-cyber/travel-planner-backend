"""
Local test to reproduce poi_9 bug with friends group.
Shows ALL debug logs to identify where filter fails.
"""
import sys
import io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.engine import build_day
from datetime import datetime

print("=" * 80)
print("LOCAL TEST: poi_9 Bug Reproduction - Friends Group")
print("=" * 80)

# Load POI
all_pois = load_zakopane_poi('data/zakopane.xlsx')
print(f"\n✅ Loaded {len(all_pois)} POI from data/zakopane.xlsx")

# Check poi_9 data
poi_9 = [p for p in all_pois if p.get('id') == 'poi_9'][0]
print(f"\n📋 POI_9 Data:")
print(f"   Name: {poi_9.get('name')}")
print(f"   Target groups: {poi_9.get('target_groups')}")
print(f"   kids_only: {poi_9.get('kids_only')}")
print(f"   priority_level: {poi_9.get('priority_level')}")

# User preferences - FRIENDS group
user = {
    "target_group": "friends",
    "intensity": "moderate",
    "budget": "standard",
    "travel_style": "balanced",
    "type_of_attraction": ["adventure", "culture"],
}

# Context
context = {
    "season": "winter",
    "date": datetime(2026, 2, 5),
    "transport": "car",
    "has_car": True,
    "weather": {
        "condition": "sunny",
        "temp": 5,
    },
}

print(f"\n👥 User: target_group={user['target_group']}")
print(f"📅 Context: season={context['season']}, date={context['date']}")

print("\n" + "=" * 80)
print("🔍 RUNNING ENGINE.BUILD_DAY() - WATCH FOR poi_9 LOGS")
print("=" * 80)
print()

# RUN ENGINE
result = build_day(
    pois=all_pois,
    user=user,
    context=context,
    day_start="09:00",
    day_end="19:00"
)

print("\n" + "=" * 80)
print("📊 ENGINE RESULT")
print("=" * 80)

attractions = [item for item in result if item.get('type') == 'attraction']
print(f"\nTotal attractions: {len(attractions)}")
print("\nSelected POI:")
for i, item in enumerate(attractions, 1):
    poi = item.get('poi', {})
    poi_id = poi.get('id', 'UNKNOWN')
    poi_name = poi.get('name', 'UNKNOWN')
    start_time = item.get('start_time', 'UNKNOWN')
    print(f"  {i}. {poi_id:10} | {poi_name:50} | {start_time}")

# CHECK IF poi_9 IS IN RESULT
poi_9_in_result = any(
    item.get('poi', {}).get('id') == 'poi_9' 
    for item in result 
    if item.get('type') == 'attraction'
)

print("\n" + "=" * 80)
if poi_9_in_result:
    print("❌ BUG CONFIRMED: poi_9 'Park Harnasia' IS in result!")
    print("   Expected: EXCLUDED (user=friends, target_groups=['family_kids'])")
else:
    print("✅ poi_9 correctly EXCLUDED from result")
print("=" * 80)
