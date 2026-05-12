import os, json, urllib.request, urllib.error
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
token = env.get('CLOUDFLARE_API_TOKEN') or env.get('TOKEN_TOKEN')
account_id = "a2a513cb6ee0cafcd9acb0e866421912"

url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/qwen/qwen3-embedding-0.6b"
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
data = {"text": "This is a test of the emergency broadcasting system."}

try:
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    res = urllib.request.urlopen(req)
    result = json.loads(res.read().decode('utf-8'))
    print("Success. Dimensions:", len(result['result']['data'][0]))
    print("First 5 values:", result['result']['data'][0][:5])
except Exception as e:
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
    else:
        print(e)
