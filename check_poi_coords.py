import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')
poi9 = df.iloc[9]
poi12 = df.iloc[12]

print(f"poi_9: {poi9['Name']} | lat={poi9['Lat']}, lng={poi9['Lng']}")
print(f"poi_12: {poi12['Name']} | lat={poi12['Lat']}, lng={poi12['Lng']}")
