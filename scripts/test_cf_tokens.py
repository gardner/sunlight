import os
import json
import urllib.request
import urllib.error

def get_env():
    env_vars = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env_vars[k.strip()] = v.strip().strip("'").strip('"')
    return env_vars

env = get_env()
account_id = "a2a513cb6ee0cafcd9acb0e866421912"
url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/qwen/qwen3-embedding-0.6b"
data = {"text": "This is a test of the emergency broadcasting system."}

for token_name in ['CLOUDFLARE_API_TOKEN', 'TOKEN_TOKEN']:
    token = env.get(token_name)
    if not token: continue
    print(f"Testing {token_name}...")
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        res = urllib.request.urlopen(req)
        result = json.loads(res.read().decode('utf-8'))
        print(f"Success with {token_name}. Dimensions:", len(result['result']['data'][0]))
        print("First 5 values:", result['result']['data'][0][:5])
        break
    except Exception as e:
        if hasattr(e, 'read'):
            print(f"Error with {token_name}: {e.read().decode('utf-8')}")
        else:
            print(f"Error with {token_name}: {e}")
