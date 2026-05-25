import pandas as pd

df = pd.read_excel('data/zakopane.xlsx')
df.columns = df.columns.str.strip()

# Check free POIs reported by client
names = ['Krupówki', 'Dolna Rówień Krupowa', 'Punkt widokowy', 'Kaplica', 'Sarni Wodospad', 'Morskie Oko', 'Dolina Strążyska']
print("=== FREE POI CHECK ===")
print(f"Columns: {list(df.columns)}\n")

for name_part in names:
    rows = df[df['Name'].str.contains(name_part, case=False, na=False)]
    for _, r in rows.iterrows():
        ticket = r.get('ticket_normal', 'N/A')
        ticket_red = r.get('ticket_reduced', 'N/A')
        free_entry = r.get('free_entry', 'N/A')
        tmin = r.get('time_min', 'N/A')
        tmax = r.get('time_max', 'N/A')
        print(f"  {r['Name']}")
        print(f"    ticket_normal={ticket!r}  ticket_reduced={ticket_red!r}  free_entry={free_entry!r}")
        print(f"    time_min={tmin}  time_max={tmax}")
        print()
