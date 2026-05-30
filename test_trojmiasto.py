import requests

headers = {'X-Guest-ID': '00000000-0000-4000-8000-000000000002', 'Content-Type': 'application/json'}
payload = {
    'location': {'city': 'Trójmiasto', 'country': 'Poland', 'is_cluster': True},
    'group': {'type': 'friends', 'size': 4},
    'trip_length': {'days': 3, 'start_date': '2025-07-15'},
    'daily_time_window': {'start': '09:00', 'end': '21:00'},
    'budget': {'level': 2},
    'transport_modes': ['car', 'public_transport'],
    'travel_style': 'balanced',
    'preferences': ['museums_heritage', 'nature_landscapes']
}
r = requests.post('http://localhost:8001/plan/preview', headers=headers, json=payload, timeout=30)
data = r.json()
print('Status:', r.status_code)
print('Days:', len(data.get('days', [])))
for i, day in enumerate(data.get('days', [])):
    attrs = day.get('attractions', [])
    print(f'  Day {i+1}: {len(attrs)} attractions')
    for a in attrs[:3]:
        print(f'    - {a.get("name", "?")}')
print('Warnings:', len(data.get('warnings', [])))
for w in data.get('warnings', [])[:5]:
    print(' ', w)
