import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')

print('Total POIs:', len(df))
print('\nRow 13 (poi_12):')
row = df.iloc[12]
print(f'Name: {row["Name"]}')
print(f'Lat: {row["Lat"]}')
print(f'Lng: {row["Lng"]}')
print(f'Address: {row["Address"]}')
print(f'time_min: {row["time_min"]}')
print(f'Description_short: {row["Description_short"]}')
