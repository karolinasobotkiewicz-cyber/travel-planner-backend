import pandas as pd

# Load Excel file
df = pd.read_excel('data/zakopane.xlsx')

# Find Morskie Oko row
morskie_idx = df[df[0] == 'Morskie Oko'].index[0]

# Print current values
print(f"Before update:")
print(f"  time_min: {df.loc[morskie_idx, 'time_min']} min")
print(f"  time_max: {df.loc[morskie_idx, 'time_max']} min")

# Update duration to match Dolina Kościeliska (180-270 min)
df.loc[morskie_idx, 'time_min'] = 180.0
df.loc[morskie_idx, 'time_max'] = 270.0

# Save updated Excel
df.to_excel('data/zakopane.xlsx', index=False)

print(f"\nAfter update:")
print(f"  time_min: {df.loc[morskie_idx, 'time_min']} min")
print(f"  time_max: {df.loc[morskie_idx, 'time_max']} min")
print("\n✓ zakopane.xlsx updated successfully!")
