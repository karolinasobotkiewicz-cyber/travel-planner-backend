"""
Sprawdź dane DINO PARK w zakopane.xlsx - czy ma ticket_normal/ticket_reduced
"""
from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')

print("Szukam DINO PARK:\n")

for p in pois:
    name = p.get('name', '')
    if 'DINO' in name.upper():
        print(f"POI: {name}")
        print(f"  ticket_normal: {p.get('ticket_normal')}")
        print(f"  ticket_reduced: {p.get('ticket_reduced')}")
        print(f"  free_entry: {p.get('free_entry')}")
        print(f"  Price: {p.get('Price')}")
        print()
