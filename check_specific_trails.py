"""Check if specific trails mentioned by klientka exist in TrailDB"""

from app.infrastructure.repositories.trail_repository import TrailRepository

# Initialize trail repository
trail_repo = TrailRepository()

# Get all trails in Tatry region (Zakopane)
trails = trail_repo.get_by_region("Tatry")

print(f"Total Tatry trails: {len(trails)}\n")

# Check for specific trails mentioned by klientka
search_names = ['Nosal', 'Wielki Kopieniec', 'Kopieniec', 'Sarnia Skała', 'Sarnia']

print("="*80)
print("Searching for trails mentioned by klientka:")
print("="*80)

for search in search_names:
    matches = [t for t in trails if search.lower() in t.trail_name.lower() or (t.peak_name and search.lower() in t.peak_name.lower())]
    if matches:
        print(f"\n✅ FOUND: {search}")
        for trail in matches:
            trail_dict = trail_repo.to_dict(trail)
            print(f"   - Name: {trail.trail_name}")
            print(f"     Peak: {trail.peak_name}")
            print(f"     Difficulty: {trail.difficulty_level}")
            print(f"     Duration: {trail.time_min} min")
            print(f"     Family-friendly: {trail.family_friendly}")
            print(f"     Type: {trail_dict.get('type', 'N/A')}")
    else:
        print(f"\n❌ NOT FOUND: {search}")

# Print all trail names for reference
print("\n" + "="*80)
print("ALL TATRY TRAILS (for reference):")
print("="*80)
for i, trail in enumerate(trails, 1):
    print(f"{i}. {trail.trail_name} ({trail.difficulty_level}, {trail.time_min}min)")
