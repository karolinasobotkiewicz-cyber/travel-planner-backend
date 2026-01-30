"""Debug Muzeum Oscypka scoring"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "")))

from app.infrastructure.repositories.poi_repository import POIRepository

# Load POI
excel_path = os.path.join(os.path.dirname(__file__), "data", "zakopane.xlsx")
poi_repo = POIRepository(excel_path)
all_pois_models = poi_repo.get_all()
all_pois = [poi.model_dump(by_alias=False) for poi in all_pois_models]

# Find Muzeum Oscypka
muzeum = next((p for p in all_pois if "Oscypka" in p.get("name", "")), None)

if muzeum:
    print("=" * 80)
    print("MUZEUM OSCYPKA DATA:")
    print("=" * 80)
    print(f"Name: {muzeum.get('name')}")
    print(f"Tags: {muzeum.get('tags')}")
    print(f"Type: {muzeum.get('type')}")
    print(f"Target groups: {muzeum.get('target_groups')}")
    print(f"POI category: {muzeum.get('poi_category')}")
    print(f"Activity style: {muzeum.get('activity_style')}")
    print(f"Opening hours: {muzeum.get('opening_hours')}")
    print(f"Recommended time: {muzeum.get('recommended_time_of_day')}")
    print(f"Must see: {muzeum.get('must_see')}")
    print(f"Popularity: {muzeum.get('popularity')}")
    print(f"WOW score: {muzeum.get('wow_score')}")
    print(f"Priority: {muzeum.get('priority')}")
    print(f"Kids only: {muzeum.get('kids_only')}")
    print(f"Children age: {muzeum.get('children_min')}-{muzeum.get('children_max')}")
    
    print("\n" + "=" * 80)
    print("ANALIZA DLACZEGO NIE JEST WYBIERANE:")
    print("=" * 80)
    
    # Check preferences match
    user_prefs = ["culture", "museums"]
    poi_tags = muzeum.get('tags', [])
    print(f"\nUser preferences: {user_prefs}")
    print(f"POI tags: {poi_tags}")
    print(f"Match: {any(pref in poi_tags for pref in user_prefs)}")
    
    # Check target group
    print(f"\nUser group: family_kids")
    print(f"POI target groups: {muzeum.get('target_groups')}")
    print(f"Match: {'family_kids' in muzeum.get('target_groups', [])}")
    
    # Check kids_only filter
    print(f"\nKids only: {muzeum.get('kids_only')}")
    print(f"Should be allowed for family_kids: {not muzeum.get('kids_only') or True}")
else:
    print("❌ Muzeum Oscypka not found!")
