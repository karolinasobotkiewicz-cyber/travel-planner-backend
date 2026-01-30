import openpyxl

wb = openpyxl.load_workbook('data/zakopane.xlsx')
sheet = wb.active
rows = list(sheet.rows)

print('=== Sample POI opening_hours data ===\n')

for i in [1, 2, 6, 7, 8]:
    row = rows[i]
    print(f'Row {i+1}: {row[1].value}')
    print(f'  Opening hours: "{row[5].value}"')
    print(f'  Opening hours seasonal: "{row[6].value}"')
    print()
