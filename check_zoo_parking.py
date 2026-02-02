import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')

# Find Tatrzańskie Mini Zoo
zoo = df[df['Name'].str.contains('Zoo', na=False)].iloc[0]

col_name = 'parking_walk_time_min'
print(f'Tatrzańskie Mini Zoo:')
print(f'  {col_name}: {zoo[col_name]}')
print(f'  Type: {type(zoo[col_name])}')
print(f'  Is NaN: {pd.isna(zoo[col_name])}')
