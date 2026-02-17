"""
Find two most distant POI in zakopane.xlsx to test transit requirement.
"""
import sys
sys.path.append('c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend')

from app.domain.planner.engine import haversine_distance
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')

print(f"Analyzing {len(pois)} POIs for distances...\n")

max_distance = 0
poi_a = None
poi_b = None

# Find most distant pair
for i, p1 in enumerate(pois):
    for p2 in pois[i+1:]:
        lat1, lng1 = p1.get('lat'), p1.get('lng')
        lat2, lng2 = p2.get('lat'), p2.get('lng')
        
        if all([lat1, lng1, lat2, lng2]):
            dist = haversine_distance(lat1, lng1, lat2, lng2)
            if dist > max_distance:
                max_distance = dist
                poi_a = p1
                poi_b = p2

print(f"Most distant POI pair:")
print(f"  {poi_a.get('id')}: {poi_a.get('name')}")
print(f"  {poi_b.get('id')}: {poi_b.get('name')}")
print(f"  Distance: {max_distance:.2f} km")
print()

# Find pairs with distance > 2km but < 10km (realistic for one day)
print("Other POI pairs with distance > 2km:")
print("="*80)

pairs = []
for i, p1 in enumerate(pois):
    for p2 in pois[i+1:]:
        lat1, lng1 = p1.get('lat'), p1.get('lng')
        lat2, lng2 = p2.get('lat'), p2.get('lng')
        
        if all([lat1, lng1, lat2, lng2]):
            dist = haversine_distance(lat1, lng1, lat2, lng2)
            if 2 < dist < 10:  # Reasonable distance for one day
                pairs.append((dist, p1, p2))

# Sort by distance
pairs.sort(reverse=True)

# Show top 10
for dist, p1, p2 in pairs[:10]:
    print(f"{dist:5.2f} km: {p1.get('name'):40s} → {p2.get('name')}")
