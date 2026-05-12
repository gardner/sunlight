import os
import urllib.request
import urllib.error
import json

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

def req(method, url, token, data=None):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    request = urllib.request.Request(url, data=json.dumps(data).encode('utf-8') if data else None, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request)
        return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        return None

def main():
    env = get_env()
    token = env.get('TOKEN_TOKEN')
    
    if not token:
        print("No TOKEN_TOKEN found")
        return
        
    zones = req('GET', 'https://api.cloudflare.com/client/v4/zones?name=sunlight.nz', token)
    zone_id = zones['result'][0]['id']

    print("\n--- Listing Routing Rules ---")
    rules_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    rules = req('GET', rules_url, token)
    if rules and rules.get('success'):
        for rule in rules['result']:
            print(f"Rule: {rule['name']} - ID: {rule['id']} - Matchers: {rule['matchers']}")
            
    print("\n--- Checking Catch-All Rule ---")
    catch_all_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/catch_all"
    catch_all = req('GET', catch_all_url, token)
    if catch_all and catch_all.get('success'):
        print(f"Catch-all: {catch_all['result']}")
    else:
        print("No Catch-All rule configured.")

if __name__ == "__main__":
    main()
