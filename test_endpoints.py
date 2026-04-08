import requests, time, json

# wait briefly for server readiness
r = None
for i in range(20):
    try:
        r = requests.get('http://127.0.0.1:8001/health', timeout=1)
        if r.status_code == 200:
            break
    except Exception:
        time.sleep(0.3)

if r is None:
    print('Health check failed: no response')
else:
    print('Health:', getattr(r, 'status_code', None), getattr(r, 'text', '')[:200])

r = requests.post('http://127.0.0.1:8001/reset', json={})
print('\n/reset status:', r.status_code)
try:
    j = r.json()
    print('Top keys:', list(j.keys()))
    obs = j.get('data', {}).get('observation', j.get('observation', {}))
    print('observation keys sample:', list(obs.keys())[:8])
except Exception as e:
    print('reset json error', e, r.text[:1000])

action = {"response":"I can help","action_type":"clarify","amount":0.0,"reason":"test"}
r2 = requests.post('http://127.0.0.1:8001/step', json=action)
print('\n/step status:', r2.status_code)
try:
    j2 = r2.json()
    print('step keys:', list(j2.keys()))
    print('reward:', j2.get('reward'), 'done:', j2.get('done'))
    print('obs keys sample:', list(j2.get('data', {}).get('observation', {}).keys())[:8])
    print('\n/step full json (truncated):')
    print(json.dumps(j2, indent=2)[:1200])
except Exception as e:
    print('step json error', e, r2.text[:1000])
