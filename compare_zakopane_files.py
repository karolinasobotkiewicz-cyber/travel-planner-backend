import pandas as pd

# Check both files
file1 = 'data/zakopane.xlsx'
file2 = '../zakopane.xlsx'
file3 = '../zakopane1.xlsx'

print("=" * 80)
print("COMPARING zakopane*.xlsx FILES - POI_9 DATA")
print("=" * 80)

for fpath in [file1, file2, file3]:
    try:
        df = pd.read_excel(fpath)
        poi9 = df.iloc[9]
        
        print(f"\n📄 FILE: {fpath}")
        print(f"  Name: {poi9['Name']}")
        print(f"  Target group: {poi9['Target group']}")
        print(f"  kids_only: {poi9.get('kids_only', 'N/A')}")
        print(f"  priority_level: {poi9.get('priority_level', 'N/A')}")
        print(f"  Total POI count: {len(df)}")
    except Exception as e:
        print(f"\n❌ FILE: {fpath} - ERROR: {e}")

print("\n" + "=" * 80)
