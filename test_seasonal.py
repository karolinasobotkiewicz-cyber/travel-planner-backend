"""
Manual test: Verify seasonal POI (Zjazd pontonem) validation works correctly
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi
from app.domain.planner.opening_hours_parser import is_poi_open_at_time

pois = load_zakopane_poi("data/zakopane.xlsx")

# Find Zjazd pontonem (seasonal POI)
zjazd = None
for poi in pois:
    if "pontonem" in poi.get('name', '').lower():
        zjazd = poi
        break

if not zjazd:
    print("ERROR: Zjazd pontonem not found!")
    exit(1)

print(f"POI: {zjazd.get('name')}")
print(f"opening_hours: {zjazd.get('opening_hours')}")
print(f"opening_hours_seasonal: {zjazd.get('opening_hours_seasonal')}")
print()

# Test dates in and out of season
# Season: June 1 (06-01) to September 30 (09-30)
test_cases = [
    (2026, 2, 15, 6, "February 15, 2026", False),   # Outside season
    (2026, 5, 31, 6, "May 31, 2026", False),        # Day before season starts
    (2026, 6, 1, 0, "June 1, 2026", True),          # First day of season
    (2026, 7, 15, 2, "July 15, 2026", True),        # Mid-season
    (2026, 9, 30, 2, "September 30, 2026", True),   # Last day of season
    (2026, 10, 1, 3, "October 1, 2026", False),     # Day after season ends
    (2026, 12, 25, 4, "December 25, 2026", False),  # Outside season
]

print("Testing seasonal validation (June 1 - September 30):")
print("="*60)

for year, month, day, weekday, date_str, should_be_open in test_cases:
    # Test 10:00-11:00 visit (60 min)
    start_time = 10 * 60  # 10:00
    duration = 60
    
    is_open = is_poi_open_at_time(
        opening_hours=zjazd.get('opening_hours'),
        opening_hours_seasonal=zjazd.get('opening_hours_seasonal'),
        current_date=(year, month, day),
        weekday=weekday,
        start_time_minutes=start_time,
        duration_minutes=duration
    )
    
    expected = "✅ OPEN" if should_be_open else "❌ CLOSED"
    result = "✅ OPEN" if is_open else "❌ CLOSED"
    status = "✅ PASS" if (is_open == should_be_open) else "❌ FAIL"
    
    print(f"{date_str:25s}: {result} (expected: {expected}) {status}")

print("\n" + "="*60)
print("CONCLUSION:")

# Critical tests
february_closed = not is_poi_open_at_time(zjazd.get('opening_hours'), zjazd.get('opening_hours_seasonal'), (2026, 2, 15), 6, 10*60, 60)
june_open = is_poi_open_at_time(zjazd.get('opening_hours'), zjazd.get('opening_hours_seasonal'), (2026, 6, 15), 0, 10*60, 60)
september_open = is_poi_open_at_time(zjazd.get('opening_hours'), zjazd.get('opening_hours_seasonal'), (2026, 9, 15), 0, 10*60, 60)
october_closed = not is_poi_open_at_time(zjazd.get('opening_hours'), zjazd.get('opening_hours_seasonal'), (2026, 10, 15), 2, 10*60, 60)

if february_closed and june_open and september_open and october_closed:
    print("✅ SUCCESS: Seasonal POI correctly validates date ranges!")
    print("   ✅ Closed in February")
    print("   ✅ Open in June")
    print("   ✅ Open in September")
    print("   ✅ Closed in October")
else:
    print("❌ FAILURE: Seasonal validation not working correctly")
    print(f"   February closed: {february_closed}")
    print(f"   June open: {june_open}")
    print(f"   September open: {september_open}")
    print(f"   October closed: {october_closed}")
