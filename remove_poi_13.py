import pandas as pd

# Load Excel file
df = pd.read_excel('data/zakopane.xlsx')

print(f"Before removal: {len(df)} POI")
print(f"\nRow 13 (index 12) data:")
print(f"  Name (column 0): {df.iloc[12, 0]}")
print(f"  lat: {df.iloc[12, df.columns.get_loc('lat')] if 'lat' in df.columns else 'N/A'}")
print(f"  lng: {df.iloc[12, df.columns.get_loc('lng')] if 'lng' in df.columns else 'N/A'}")

# Remove row with index 12 (poi_13 - 13th POI)
df = df.drop(df.index[12])

# Reset index to maintain continuity
df = df.reset_index(drop=True)

# Save updated Excel
df.to_excel('data/zakopane.xlsx', index=False)

print(f"\nAfter removal: {len(df)} POI")
print("✓ poi_13 removed from zakopane.xlsx!")
