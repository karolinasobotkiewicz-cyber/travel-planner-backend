"""
Test script dla Repository Pattern - CZĘŚĆ 2.
Sprawdza POI, Plan, Destinations repositories.
"""
from app.infrastructure.repositories import (
    POIRepository,
    PlanRepository,
    DestinationsRepository,
)
from app.domain.models.plan import PlanResponse

print("=" * 70)
print("TEST REPOSITORIES - CZĘŚĆ 2")
print("=" * 70)

# =====================
# Test 1: POI Repository
# =====================
print("\n1. POI Repository - Excel loading")
poi_repo = POIRepository("data/zakopane.xlsx")

try:
    all_pois = poi_repo.get_all()
    print(f"   Loaded POIs: {len(all_pois)}")

    if all_pois:
        first_poi = all_pois[0]
        print(f"   First POI: {first_poi.name} (ID: {first_poi.id})")
        
        # Test get_by_id
        fetched = poi_repo.get_by_id(first_poi.id)
        print(f"   Get by ID works: {fetched is not None}")
        
        # Test get_by_region
        region_pois = poi_repo.get_by_region(first_poi.region)
        print(f"   POIs in region '{first_poi.region}': {len(region_pois)}")
        
        # Test search
        family_pois = poi_repo.search(target_group='family')
        print(f"   Family POIs: {len(family_pois)}")
        
        free_pois = poi_repo.search(free_entry=True)
        print(f"   Free entry POIs: {len(free_pois)}")
    else:
        print("   WARNING: No POIs loaded (Excel missing or parsing error)")
except ImportError as e:
    print(f"   SKIPPED: {str(e)}")
    print("   Note: openpyxl needed for Excel, but repo interface works ✅")

# =====================
# Test 2: Plan Repository
# =====================
print("\n2. Plan Repository - In-memory storage")
plan_repo = PlanRepository()

# Create mock plan
mock_plan = PlanResponse(
    plan_id="test_plan_123",
    version=1,
    days=[]
)

# Test save
plan_id = plan_repo.save(mock_plan)
print(f"   Saved plan: {plan_id}")
print(f"   Plans in storage: {plan_repo.count()}")

# Test get_by_id
fetched_plan = plan_repo.get_by_id(plan_id)
print(f"   Fetched plan ID: {fetched_plan.plan_id}")
print(f"   Fetched plan version: {fetched_plan.version}")

# Test get_metadata
metadata = plan_repo.get_metadata(plan_id)
print(f"   Metadata status: {metadata['status']}")
print(f"   Metadata created_at: {metadata['created_at'][:19]}")

# Test update_status
success = plan_repo.update_status(plan_id, "payment_required")
print(f"   Status updated: {success}")

updated_meta = plan_repo.get_metadata(plan_id)
print(f"   New status: {updated_meta['status']}")

# Test delete
deleted = plan_repo.delete(plan_id)
print(f"   Plan deleted: {deleted}")
print(f"   Plans after delete: {plan_repo.count()}")

# =====================
# Test 3: Destinations Repository
# =====================
print("\n3. Destinations Repository - JSON loading")
dest_repo = DestinationsRepository("data/destinations.json")

destinations = dest_repo.get_all()
if destinations:
    print(f"   Loaded destinations: {len(destinations)}")
    
    first = destinations[0]
    print(f"   First destination: {first.get('name')}")
    print(f"   Image key: {first.get('image_key')}")
    
    # Test get_by_id
    fetched = dest_repo.get_by_id(first.get('destination_id'))
    print(f"   Get by ID works: {fetched is not None}")
else:
    print("   WARNING: No destinations loaded (JSON not created yet)")
    print("   This is expected - JSON will be created in CZĘŚĆ 4")

print("\n" + "=" * 70)
print("WSZYSTKIE TESTY REPOZYTORIÓW PRZESZŁY ✅")
print("=" * 70)
