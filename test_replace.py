"""Test replace_item functionality"""
from app.infrastructure.repositories.poi_repository import POIRepository
from app.application.services.plan_editor import PlanEditor
from app.domain.models.plan import DayPlan, AttractionItem, DayStartItem, DayEndItem, TicketInfo, ParkingInfo

# Initialize
excel_path = 'data/zakopane.xlsx'
poi_repo = POIRepository(excel_path)
editor = PlanEditor(poi_repo)

# Load POIs
pois = poi_repo.get_all()
all_pois = [poi.model_dump(by_alias=True) for poi in pois]
print(f'Loaded {len(all_pois)} POIs')

# Find Morskie Oko (POI ID is poi_35)
morskie = next((p for p in all_pois if p.get('ID') == 'poi_35'), None)
print(f'\nMorskie Oko: Type={morskie.get("type")}, Groups={morskie.get("target_groups")}')

# Find similar POIs
poi_type = morskie.get('type')
same_type = [p for p in all_pois if p.get('type') == poi_type and p.get('ID') != 'poi_35']
print(f'\nPOIs with same type ("{poi_type}"): {len(same_type)}')
for poi in same_type[:5]:
    print(f'  - {poi.get("Name")} (ID: {poi.get("ID")})')

# Test replace
test_items = [
    DayStartItem(time='09:00'),
    AttractionItem(
        poi_id='poi_35',
        name='Morskie Oko',
        start_time='09:30',
        end_time='13:30',
        duration_min=240,
        description_short='Must-see alpine lake',
        lat=49.201,
        lng=20.071,
        address='Zakopane',
        cost_estimate=15,
        ticket_info=TicketInfo(ticket_normal=0, ticket_reduced=0, free_entry=True),
        parking=ParkingInfo(name='Parking', walk_time_min=5),
        pro_tip='Start early',
        why_selected=['Must-see'],
        quality_badges=['must_see']
    ),
    DayEndItem(time='20:00')
]

original_plan = DayPlan(day=1, items=test_items, quality_badges=['has_must_see'])

print('\n=== TEST: Replace Morskie Oko with similar POI ===')
context = {'season': 'zima', 'weather': 'clear', 'transport': 'car', 'date': '2026-02-17'}
user = {'group_type': 'couples', 'budget': 2, 'preferences': ['hiking', 'nature']}

replaced_plan = editor.replace_item(
    day_plan=original_plan,
    item_id='poi_35',
    all_pois=all_pois,
    context=context,
    user=user,
    strategy='SMART_REPLACE'
)

attractions = [item for item in replaced_plan.items if item.type == 'attraction']
print(f'\nResult: {len(attractions)} attractions')
for item in attractions:
    print(f'  - {item.name} (ID: {item.poi_id})')

# Verify replacement
morskie_gone = not any(item.poi_id == 'poi_35' for item in attractions)
print(f'\nMorskie Oko replaced: {morskie_gone}')
