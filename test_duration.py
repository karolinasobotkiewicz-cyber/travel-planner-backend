import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')

# Find Morskie Oko
morskie_idx = df[df[0]=='Morskie Oko'].index[0]
dolina_idx = df[df[0]=='Dolina Kościeliska'].index[0]

print('Morskie Oko (poi_36):')
print(f'  time_min: {df.loc[morskie_idx, "time_min"]} min')
print(f'  time_max: {df.loc[morskie_idx, "time_max"]} min')

print('\nDolina Kościeliska (poi_34):')
print(f'  time_min: {df.loc[dolina_idx, "time_min"]} min')
print(f'  time_max: {df.loc[dolina_idx, "time_max"]} min')
