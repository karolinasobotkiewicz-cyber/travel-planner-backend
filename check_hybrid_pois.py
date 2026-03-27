"""Check POI details for HYBRID test verification"""
import sys
sys.path.insert(0, '.')

from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

# Load POIs
pois = load_zakopane_poi('data/zakopane.xlsx')

# Find problematic POIs from HYBRID response
target_pois = {
    'poi_2': 'Tatrzańskie Mini Zoo',
    'poi_5': 'Papugarnia',
    'poi_6': 'Podwodny Świat',
    'poi_20': 'Wielka Krokiew',
    'poi_24': 'Muzeum Tatrzańskie',
    'poi_26': 'Muzeum Stylu',
    'poi_27': 'Galeria Oksza',
    'poi_28': 'Muzeum Szymanowskiego',
    'poi_30': 'Kaplica',
    'poi_33': 'Dolina Kościeliska'
}

print("=" * 80)
print("POI DETAILS FOR HYBRID TEST VERIFICATION")
print("=" * 80)

found_pois = {}

for poi in pois:
    poi_id = poi.get('id', '')
    if poi_id in target_pois:
        found_pois[poi_id] = poi

# Print in order
for poi_id in ['poi_33', 'poi_24', 'poi_26', 'poi_2', 'poi_20', 'poi_6', 'poi_27', 'poi_28', 'poi_5', 'poi_30']:
    if poi_id in found_pois:
        poi = found_pois[poi_id]
        print(f"\n{poi_id}: {poi.get('name')}")
        print(f"  Target groups: {poi.get('target_groups', 'N/A')}")
        print(f"  Kids only: {poi.get('kids_only', 'N/A')}")
        print(f"  Tags: {poi.get('tags', [])}")
        print(f"  Type: {poi.get('type', 'N/A')}")
        print(f"  Priority: {poi.get('priority_level', 'N/A')}")
        print(f"  Must see: {poi.get('must_see', 'N/A')}")
        
        # Check if it's kids POI
        tags = poi.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',')]
        
        is_kids = (
            poi.get('kids_only') == 'true' or
            'kids' in str(tags).lower() or
            'family' in str(tags).lower() or
            'zoo' in poi.get('name', '').lower() or
            'papugarnia' in poi.get('name', '').lower() or
            'aquarium' in poi.get('type', '').lower()
        )
        
        print(f"  🚨 IS KIDS POI: {is_kids}")
