"""
Manual test: Verify Muzeum Oscypka Saturday-only opening hours work correctly
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.opening_hours_parser import is_poi_open_at_time

pois = load_zakopane_poi("data/zakopane.xlsx")

# Find Muzeum Oscypka
muzeum = None
for poi in pois:
    if "Oscypka" in poi.get('name', ''):
        muzeum = poi
        break

if not muzeum:
    print("ERROR: Muzeum Oscypka not found!")
    exit(1)

print(f"POI: {muzeum.get('name')}")
print(f"opening_hours: {muzeum.get('opening_hours')}")
print(f"opening_hours_seasonal: {muzeum.get('opening_hours_seasonal')}")
print()

# Test different days of week
# 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
test_cases = [
    (2026, 2, 9, 0, "Monday"),     # Monday Feb 9
    (2026, 2, 13, 4, "Friday"),    # Friday Feb 13
    (2026, 2, 14, 5, "Saturday"),  # Saturday Feb 14 - SHOULD BE OPEN
    (2026, 2, 15, 6, "Sunday"),    # Sunday Feb 15
]

for year, month, day, weekday, day_name in test_cases:
    # Test 16:00-17:00 visit (60 min)
    start_time = 16 * 60  # 16:00
    duration = 60
    
    is_open = is_poi_open_at_time(
        opening_hours=muzeum.get('opening_hours'),
        opening_hours_seasonal=muzeum.get('opening_hours_seasonal'),
        current_date=(year, month, day),
        weekday=weekday,
        start_time_minutes=start_time,
        duration_minutes=duration
    )
    
    expected = "✅ OPEN" if weekday == 5 else "❌ CLOSED"
    result = "✅ OPEN" if is_open else "❌ CLOSED"
    status = "✅ PASS" if (is_open == (weekday == 5)) else "❌ FAIL"
    
    print(f"{day_name} {year}-{month:02d}-{day:02d}: {result} (expected: {expected}) {status}")

print("\n" + "="*60)
print("CONCLUSION:")
if all([
    is_poi_open_at_time(muzeum.get('opening_hours'), muzeum.get('opening_hours_seasonal'), (2026, 2, 14), 5, 16*60, 60),  # Saturday OPEN
    not is_poi_open_at_time(muzeum.get('opening_hours'), muzeum.get('opening_hours_seasonal'), (2026, 2, 15), 6, 16*60, 60),  # Sunday CLOSED
    not is_poi_open_at_time(muzeum.get('opening_hours'), muzeum.get('opening_hours_seasonal'), (2026, 2, 9), 0, 16*60, 60),  # Monday CLOSED
]):
    print("✅ SUCCESS: Muzeum Oscypka correctly validates Saturday-only opening hours!")
else:
    print("❌ FAILURE: Opening hours validation not working correctly")
