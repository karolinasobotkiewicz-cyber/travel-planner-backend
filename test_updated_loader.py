"""Test updated loader with new zakopane.xlsx"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

print("="*80)
print("TESTING UPDATED LOADER")
print("="*80)

pois = load_zakopane_poi('data/zakopane.xlsx')

print(f"\n✅ Total POI loaded: {len(pois)}")

# Check first POI
p1 = pois[0]
print(f"\n📍 SAMPLE POI #1:")
print(f"   ID: {p1.get('id')}")
print(f"   Name: {p1.get('name')}")
print(f"   Tags: {p1.get('tags')}")
print(f"   Tag count: {len(p1.get('tags', []))}")
print(f"   Price (normal): {p1.get('ticket_price')} PLN")
print(f"   Priority: {p1.get('priority_level')}")

# Count POI with tags
with_tags = sum(1 for p in pois if p.get('tags'))
print(f"\n📊 POI WITH TAGS: {with_tags}/{len(pois)}")

# Count POI with prices
with_prices = sum(1 for p in pois if p.get('ticket_price') and p.get('ticket_price') > 0)
print(f"📊 POI WITH PRICES: {with_prices}/{len(pois)}")

# Collect all unique tags
all_tags = set()
for p in pois:
    all_tags.update(p.get('tags', []))

print(f"📊 UNIQUE TAGS: {len(all_tags)}")

# Priority distribution
from collections import Counter
priority_counts = Counter(p.get('priority_level') for p in pois)
print(f"\n⭐ PRIORITY DISTRIBUTION:")
for level, count in priority_counts.items():
    print(f"   {level}: {count} POI")

# Sample tags from first 5 POI
print(f"\n🏷️  SAMPLE TAGS (first 5 POI):")
for i in range(min(5, len(pois))):
    p = pois[i]
    print(f"   {i+1}. {p.get('name')}")
    print(f"      Tags: {p.get('tags')}")

print("\n" + "="*80)
print("✅ LOADER TEST COMPLETE")
print("="*80)
