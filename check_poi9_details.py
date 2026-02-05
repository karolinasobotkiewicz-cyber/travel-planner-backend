import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')
poi9 = df.iloc[9]

print("poi_9 ALL DATA:")
print(f"  Name: {poi9['Name']}")
print(f"  Target group: {poi9['Target group']}")
print(f"  kids_only: {poi9.get('kids_only', 'N/A')}")
print(f"  priority_level: {poi9.get('priority_level', 'N/A')}")
print(f"  Type of attraction: {poi9.get('Type of attraction', 'N/A')}")
