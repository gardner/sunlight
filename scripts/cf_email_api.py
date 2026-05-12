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
    token = env.get('TOKEN_TOKEN') or env.get('CLOUDFLARE_API_TOKEN')
    
    if not token:
        print("No token found")
        return
        
    print("Fetching zones...")
    zones = req('GET', 'https://api.cloudflare.com/client/v4/zones?name=sunlight.nz', token)
    if not zones or not zones.get('success') or not zones['result']:
        print("Failed to fetch zone sunlight.nz.")
        return
        
    zone_id = zones['result'][0]['id']
    print(f"Zone ID: {zone_id}")
    
    # Try to add requests@sunlight.nz as a sender address? Wait, what's the API for that?
    # It's likely under /client/v4/accounts/{account_identifier}/email/routing/addresses
    account_id = zones['result'][0]['account']['id']
    print(f"Account ID: {account_id}")

if __name__ == "__main__":
    main()
