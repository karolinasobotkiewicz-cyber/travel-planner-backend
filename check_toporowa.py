import pandas as pd

print("=== multi_city_attractions.xlsx ===")
df = pd.read_excel('data/multi_city_attractions.xlsx', sheet_name=None)
found_multi = False
for sheet, frame in df.items():
    if 'Name' in frame.columns:
        matches = frame[frame['Name'].str.contains('Toporowa', case=False, na=False)]
        if len(matches):
            print(f"Sheet '{sheet}': {list(matches['Name'])}")
            found_multi = True
if not found_multi:
    print("Not found in multi_city_attractions.xlsx")

print("\n=== zakopane.xlsx ===")
df2 = pd.read_excel('data/zakopane.xlsx')
if 'Name' in df2.columns:
    matches2 = df2[df2['Name'].str.contains('Toporowa', case=False, na=False)]
    if len(matches2):
        print(list(matches2['Name']))
    else:
        print("Not found in zakopane.xlsx")
