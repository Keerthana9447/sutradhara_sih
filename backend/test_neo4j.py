import httpx, json

base = 'http://localhost:8000'

print('='*60)
print('3. NEO4J KNOWLEDGE GRAPH TESTS')
print('='*60)

# 3a. Graph structure
r = httpx.get(f'{base}/api/graph')
print(f'\n[GET /api/graph] Status: {r.status_code}')
graph_data = r.json()
print(f'  Nodes: {len(graph_data.get("nodes", []))}')
print(f'  Edges: {len(graph_data.get("edges", []))}')
print(json.dumps(graph_data, indent=2)[:300])

# 3b. Graph reasoning
r = httpx.post(f'{base}/api/graph/reason', json={
    'category': 'Ayurvedic formulations',
    'jurisdiction': 'India',
    'export_intent': True
})
print(f'\n[POST /api/graph/reason] Status: {r.status_code}')
print(json.dumps(r.json(), indent=2)[:800])
