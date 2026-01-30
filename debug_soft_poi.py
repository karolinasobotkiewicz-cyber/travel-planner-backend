from app.infrastructure.repositories.poi_repository import POIRepository

repo = POIRepository('data/zakopane.xlsx')
pois = repo.get_all()

print('=== POI ANALYSIS FOR SOFT POI ===\n')

# Intensity distribution
intensities = {}
for p in pois:
    intensities[p.intensity] = intensities.get(p.intensity, 0) + 1

print(f'Intensity distribution: {intensities}\n')

# Low intensity POI
low_pois = [p for p in pois if p.intensity == 'low']
print(f'Low intensity POI: {len(low_pois)}')
for p in low_pois[:10]:
    print(f'- {p.name}: time_min={p.time_min}, must_see={p.must_see}')

print('\n=== SOFT POI CRITERIA ===')
print('Criteria: time_min 10-30 + must_see_score 0-2')

# Check candidates
candidates = [p for p in pois if 10 <= p.time_min <= 30 and p.must_see_score <= 2]
print(f'\nSoft POI candidates: {len(candidates)}')
for p in candidates:
    print(f'- {p.name}: time_min={p.time_min}, must_see_score={p.must_see_score}, intensity={p.intensity}')

# Check all short POI (10-30 min) regardless of intensity
short_pois = [p for p in pois if 10 <= p.time_min <= 30]
print(f'\n\nShort POI (10-30 min): {len(short_pois)}')
for p in short_pois:
    print(f'- {p.name}: intensity={p.intensity}, time_min={p.time_min}, must_see={p.must_see}')
