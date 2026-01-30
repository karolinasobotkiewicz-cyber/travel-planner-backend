"""Test travel time with actually distant POI"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "")))

from app.infrastructure.repositories.poi_repository import POIRepository
from app.domain.planner.engine import haversine_distance, travel_time_minutes

# Load POI
excel_path = os.path.join(os.path.dirname(__file__), "data", "zakopane.xlsx")
poi_repo = POIRepository(excel_path)
all_pois_models = poi_repo.get_all()
all_pois = [poi.model_dump(by_alias=False) for poi in all_pois_models]

# Find some POI
kasprowy = next((p for p in all_pois if "Kasprowy" in p.get("name", "")), None)
morskie_oko = next((p for p in all_pois if "Morskie Oko" in p.get("name", "")), None)
gubalowka = next((p for p in all_pois if "Gubałówka" in p.get("name", "")), None)
centrum = next((p for p in all_pois if "Krupówki" in p.get("name", "")), None)

print("Testing travel times between distant POI:")
print("=" * 80)

test_pairs = [
    (kasprowy, morskie_oko, "Kasprowy Wierch → Morskie Oko"),
    (gubalowka, morskie_oko, "Gubałówka → Morskie Oko"),
    (centrum, kasprowy, "Krupówki → Kasprowy"),
    (centrum, morskie_oko, "Krupówki → Morskie Oko"),
]

context = {"has_car": True}

for poi_from, poi_to, label in test_pairs:
    if poi_from and poi_to:
        lat1, lng1 = poi_from.get("lat"), poi_from.get("lng")
        lat2, lng2 = poi_to.get("lat"), poi_to.get("lng")
        
        distance = haversine_distance(lat1, lng1, lat2, lng2)
        travel_time = travel_time_minutes(poi_from, poi_to, context)
        
        print(f"\n{label}")
        print(f"  Distance: {distance:.2f} km")
        print(f"  Travel time: {travel_time} min")
        print(f"  (45 km/h + 5 min parking, min 10 min)")
