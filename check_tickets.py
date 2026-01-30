import openpyxl

wb = openpyxl.load_workbook('data/zakopane.xlsx')
sheet = wb.active
rows = list(sheet.rows)
headers = [c.value for c in rows[0]]

ticket_normal_idx = headers.index('ticket_normal')
ticket_reduced_idx = headers.index('ticket_reduced')

print('=== Ticket prices in Excel ===\n')
for i in [1, 2, 3, 4, 5]:
    row = rows[i]
    print(f'{row[1].value}:')
    print(f'  ticket_normal: {row[ticket_normal_idx].value}')
    print(f'  ticket_reduced: {row[ticket_reduced_idx].value}')
    print()
