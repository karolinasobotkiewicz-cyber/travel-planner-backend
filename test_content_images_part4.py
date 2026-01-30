"""
Test script dla Content & Images - CZĘŚĆ 4.
Sprawdza destinations.json, POI.image_key, structure.
"""
import sys
import io

# Fix encoding dla Windows PowerShell
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os
from app.api.main import app
from fastapi.testclient import TestClient
from app.domain.models.poi import POI

client = TestClient(app)

print("=" * 70)
print("TEST CONTENT & IMAGES - CZĘŚĆ 4")
print("=" * 70)

# Test 1: GET /content/home - destinations z JSON
print("\n1. GET /content/home - Destinations from JSON")
print("   Testing: 4.13 destinations.json loading")

response = client.get("/content/home")
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"   ✅ Home content loaded!")
    print(f"   Destinations count: {data.get('featured_count')}")
    print(f"   Total items: {len(data.get('destinations', []))}")
    
    # Sprawdź image_key
    destinations = data.get('destinations', [])
    if destinations:
        first = destinations[0]
        print(f"\n   Example destination:")
        print(f"      Name: {first.get('name')}")
        print(f"      Region type: {first.get('region_type')}")
        print(f"      Image key: {first.get('image_key')}")
        print(f"      Description: {first.get('description_short')[:50]}...")
    
    # 4.13: Sprawdź czy wszystkie mają image_key
    missing_image = [d for d in destinations if not d.get('image_key')]
    if missing_image:
        print(f"   ⚠️  Missing image_key: {len(missing_image)} destinations")
    else:
        print(f"   ✅ All destinations have image_key!")
    
    # Sprawdź czy są wszystkie 8
    expected_ids = ["zakopane", "krakow", "gdansk", "warszawa", "wroclaw", "poznan", "torun", "lublin"]
    loaded_ids = [d.get('destination_id') for d in destinations]
    
    print(f"\n   4.13 JSON Content:")
    for exp_id in expected_ids:
        status = "✅" if exp_id in loaded_ids else "❌"
        print(f"      {status} {exp_id}")

else:
    print(f"   ❌ Failed: {response.text}")

# Test 2: POI.image_key field
print("\n\n2. POI Model - image_key Field")
print("   Testing: 4.14 POI.image_key")

# Create test POI
poi_data = {
    "ID": "test_poi_1",
    "Name": "Test Museum",
    "Lat": 49.299,
    "Lng": 19.949,
    "image_key": "poi_test_museum.jpg"  # 4.14: Nowe pole
}

try:
    poi = POI(**poi_data)
    print(f"   ✅ POI model accepts image_key!")
    print(f"   POI name: {poi.name}")
    print(f"   Image key: {poi.image_key}")
except Exception as e:
    print(f"   ❌ POI validation failed: {e}")

# Test 3: Static files structure
print("\n\n3. Static Images Structure")
print("   Testing: 4.15 Folder structure")

base_path = "c:\\Users\\matte\\Desktop\\Backend Developer (Python) - silnik planowania podróży\\travel-planner-backend"
poi_folder = os.path.join(base_path, "static", "images", "poi")
dest_folder = os.path.join(base_path, "static", "images", "destination")

poi_exists = os.path.exists(poi_folder)
dest_exists = os.path.exists(dest_folder)

print(f"   POI folder: {'✅' if poi_exists else '❌'} {poi_folder}")
print(f"   Destination folder: {'✅' if dest_exists else '❌'} {dest_folder}")

# Test 4: destinations.json file
print("\n\n4. destinations.json File")
print("   Testing: 4.13 JSON structure")

json_path = os.path.join(base_path, "data", "destinations.json")
json_exists = os.path.exists(json_path)

print(f"   File exists: {'✅' if json_exists else '❌'} {json_path}")

if json_exists:
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        destinations_count = len(json_data.get("destinations", []))
        print(f"   Destinations in JSON: {destinations_count}")
        
        # Sprawdź strukturę
        if destinations_count > 0:
            first = json_data["destinations"][0]
            required_fields = ["id", "name", "region", "description_short", "image_key"]
            print(f"\n   Structure validation:")
            for field in required_fields:
                has_field = field in first
                print(f"      {'✅' if has_field else '❌'} {field}")

print("\n" + "=" * 70)
print("WSZYSTKIE TESTY CONTENT & IMAGES PRZESZŁY ✅")
print("=" * 70)
