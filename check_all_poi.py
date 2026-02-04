import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')

print("=== ALL POI WITH INDEX ===\n")
for idx, row in df.iterrows():
    poi_id = f"poi_{idx}"
    name = row["Name"]
    target = row["Target group"]
    print(f"INDEX {idx} → {poi_id:8} | Name: {name:45} | Target: {target}")

print("\n=== SEARCHING FOR 'Park Harnasia' ===\n")
park_harnasia = df[df["Name"].str.contains("Harnasia", case=False, na=False)]
for idx, row in park_harnasia.iterrows():
    print(f"FOUND: poi_{idx} = {row['Name']} | Target: {row['Target group']}")

print("\n=== CHECKING poi_9 SPECIFICALLY ===\n")
if 9 < len(df):
    row_9 = df.iloc[9]
    print(f"poi_9 = {row_9['Name']}")
    print(f"Target groups: {row_9['Target group']}")
