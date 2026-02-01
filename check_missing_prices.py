"""
Sprawdź które POI mają ticket_normal=0 (NaN w Excel)
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')

print("POI z ticket_normal=0 (brak cen w Excel):\n")

count = 0
for p in pois:
    ticket_normal = p.get('ticket_normal', 0)
    ticket_reduced = p.get('ticket_reduced', 0)
    free_entry = p.get('free_entry', False)
    
    if ticket_normal == 0 and ticket_reduced == 0 and not free_entry:
        count += 1
        print(f"{count}. {p.get('name')}")
        print(f"   free_entry: {free_entry}")
        print(f"   Price field: {p.get('Price')}")
        print()

print(f"\nTOTAL: {count} POI bez cen")
