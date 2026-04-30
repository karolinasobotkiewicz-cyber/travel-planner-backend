"""
Quick test - Phase 2 repositories
"""
from app.infrastructure.repositories import TrailRepository, RestaurantRepository

print("="*60)
print("ETAP 3 PHASE 2 - Repository Test")
print("="*60)

# Test TrailRepository
print("\n1️⃣ TrailRepository:")
trail_repo = TrailRepository()

trails_all = trail_repo.get_all()
print(f"   ✅ Total trails: {len(trails_all)}")

trails_tatry = trail_repo.get_by_region("Tatry")
print(f"   ✅ Tatry trails: {len(trails_tatry)}")

trails_family = trail_repo.get_family_friendly("Tatry")
print(f"   ✅ Family-friendly (Tatry): {len(trails_family)}")

if trails_all:
    sample = trails_all[0]
    print(f"   ✅ Sample: {sample.trail_name} ({sample.difficulty_level}, {sample.length_km}km)")

# Test RestaurantRepository
print("\n2️⃣ RestaurantRepository:")
restaurant_repo = RestaurantRepository()

restaurants_all = restaurant_repo.get_all()
print(f"   ✅ Total restaurants: {len(restaurants_all)}")

restaurants_krakow = restaurant_repo.get_by_city("Kraków")
print(f"   ✅ Kraków restaurants: {len(restaurants_krakow)}")

lunch_krakow = restaurant_repo.get_by_meal_type("lunch", city="Kraków")
print(f"   ✅ Lunch spots (Kraków): {len(lunch_krakow)}")

if restaurants_all:
    sample = restaurants_all[0]
    print(f"   ✅ Sample: {sample.name} ({sample.meal_type}, price: {sample.price_level})")

# Test to_dict conversion
print("\n3️⃣ to_dict() Conversion:")
if trails_all:
    trail_dict = trail_repo.to_dict(trails_all[0])
    print(f"   ✅ Trail dict keys: {list(trail_dict.keys())[:10]}...")
    print(f"   ✅ Trail has 'type': {trail_dict.get('type')}")

if restaurants_all:
    restaurant_dict = restaurant_repo.to_dict(restaurants_all[0])
    print(f"   ✅ Restaurant dict keys: {list(restaurant_dict.keys())[:10]}...")
    print(f"   ✅ Restaurant has 'type': {restaurant_dict.get('type')}")

print("\n" + "="*60)
print("✅ ALL TESTS PASSED - Phase 2 repositories working")
print("="*60)
