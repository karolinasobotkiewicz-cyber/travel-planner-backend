import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')

# Lista POI z planu friends
plan_pois = ['poi_19', 'poi_5', 'poi_29', 'poi_26', 'poi_12', 'poi_9', 'poi_27', 'poi_15', 'poi_25']

print("=== POI w planie friends ===\n")
for poi_id in plan_pois:
    row = df[df['ID'] == poi_id]
    if not row.empty:
        name = row['Name'].values[0]
        target = row['Target group'].values[0]
        print(f"{poi_id}: {name}")
        print(f"  Target group: {target}")
        print()
