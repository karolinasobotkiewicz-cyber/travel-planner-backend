import sys, os, json, io
from contextlib import redirect_stdout
sys.path.insert(0, '.')
from app.infrastructure.repositories.trail_repository import TrailRepository
from app.domain.planner.opening_hours_parser import find_current_season
from app.domain.filters.seasonality import filter_by_season
from datetime import datetime

trail_repo = TrailRepository()
# Try "Tatry" instead of "zakopane"
region = "Tatry"
trails_db = trail_repo.get_by_region(region)
trails_raw = [trail_repo.to_dict(t) for t in trails_db]

print(f"Total trails in TrailDB for '{region}': {len(trails_raw)}")

if not trails_raw:
    # Try getting all trails if Tatry is empty
    from app.infrastructure.database import TrailDB
    trails_db = trail_repo.session.query(TrailDB).all()
    trails_raw = [trail_repo.to_dict(t) for t in trails_db]
    print(f"Total trails in TrailDB (all): {len(trails_raw)}")

# Check seasonality filter
trails_after_season = filter_by_season(trails_raw, datetime(2026, 2, 20))
print(f"After filter_by_season (Feb): {len(trails_after_season)}")

# Check in-loop opening_hours_seasonal for February
feb_date = (2026, 2, 20)
available_feb = []
blocked_feb = []

for t in trails_raw:
    oh_seasonal = t.get("opening_hours_seasonal")
    if oh_seasonal:
        season = find_current_season(feb_date, oh_seasonal)
        if season is None:
            blocked_feb.append(t.get("name", "UNKNOWN"))
        else:
            available_feb.append(t.get("name", "UNKNOWN"))
    else:
        available_feb.append(t.get("name", "UNKNOWN"))

print(f"\nAvailable in Feb ({len(available_feb)}):")
for n in available_feb:
    print(f"  - {n}")
    
print(f"\nBlocked in Feb ({len(blocked_feb)}):")
for n in blocked_feb:
    print(f"  - {n}")

# Also check seasonality field
print("\n\nSeasonality field check:")
for t in trails_raw:
    s = t.get("seasonality", [])
    print(f"  {t.get('name','?')[:40]}: seasonality={s}, oh_seasonal={'yes' if t.get('opening_hours_seasonal') else 'no'}")
