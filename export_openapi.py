"""
Export OpenAPI specification from production API.
"""
import requests
import json

# Fetch OpenAPI spec from production
response = requests.get('https://travel-planner-backend-xbsp.onrender.com/openapi.json')
spec = response.json()

# Save to JSON file
with open('ETAP2_API_SPECIFICATION.json', 'w', encoding='utf-8') as f:
    json.dump(spec, f, indent=2, ensure_ascii=False)

print('✅ OpenAPI spec exported to ETAP2_API_SPECIFICATION.json')
print(f'API Version: {spec["info"]["version"]}')
print(f'Total endpoints: {len(spec["paths"])}')
print(f'Title: {spec["info"]["title"]}')
print('\nNew ETAP 2 endpoints:')
print('  POST /plan/claim-guest-plans - Transfer guest plans to authenticated user')
print('  GET  /plan/my-plans - Get all plans for authenticated user')
