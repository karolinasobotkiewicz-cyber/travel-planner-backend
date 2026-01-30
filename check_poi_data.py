from app.infrastructure.repositories.load_zakopane import load_zakopane_poi

pois = load_zakopane_poi('data/zakopane.xlsx')

print("Checking problematic POIs:\n")

for p in pois:
    name = p.get('name', '')
    if 'Podwodny' in name or 'Oscypka' in name or 'ulig' in name.lower():
        print(f"POI: {name}")
        print(f"  opening_hours: {p.get('opening_hours')}")
        print(f"  opening_hours_seasonal: {p.get('opening_hours_seasonal')}")
        print(f"  recommended_time_of_day: {p.get('recommended_time_of_day')}")
        print(f"  time_min: {p.get('time_min')}, time_max: {p.get('time_max')}")
        print()
