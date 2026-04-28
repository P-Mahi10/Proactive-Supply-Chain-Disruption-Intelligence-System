import requests, json
url = 'http://127.0.0.1:8000/run_pipeline'
payload = {
    "origin_port": "jnpt",
    "destination_port": "singapore",
    "cargo_type": "container",
    "cargo_volume_teu": 500
}
headers = {
    "Authorization": "Bearer mock-token"
}

print(f"Sending request to {url}...")
try:
    resp = requests.post(url, json=payload, headers=headers)
    print('Status:', resp.status_code)
    if resp.status_code == 200:
        print('Response:', json.dumps(resp.json(), indent=2))
    else:
        print('Error:', resp.text)
except Exception as e:
    print('Failed to connect:', e)
