import json
with open('test_results_uat_round2/test-08-response.json', encoding='utf-8') as f:
    data = json.load(f)
day4 = data['days'][3]
print('Day 4:', day4.get('date', 'N/A'))
for item in day4['items']:
    name = item.get('name', '') or (item.get('poi', {}) or {}).get('name', '')
    t = item.get('type','')
    s = item.get('start_time','')
    e = item.get('end_time','')
    print(f'  {t:<20} {s:<8} {e:<8} {str(name)[:50]}')
