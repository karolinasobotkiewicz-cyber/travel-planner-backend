import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')
df.columns = df.columns.str.strip()

rows = df[df['Name'].str.contains('Morskie', case=False, na=False)]
for _, r in rows.iterrows():
    print(dict(r))
