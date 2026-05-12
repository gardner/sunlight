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
    for key, token in env.items():
        if 'TOKEN' in key or 'KEY' in key:
            print(f"\n--- Checking token {key} ---")
            verify = req('GET', 'https://api.cloudflare.com/client/v4/user/tokens/verify', token)
            if verify and verify.get('success'):
                print(f"Status: {verify['result']['status']}")
            else:
                print("Verification failed or not a bearer token.")
                # Maybe it's a global API key? Global API keys require X-Auth-Key and X-Auth-Email.
                
            zones = req('GET', 'https://api.cloudflare.com/client/v4/zones', token)
            if zones and zones.get('success'):
                for zone in zones.get('result', []):
                    print(f"Zone: {zone['name']} - ID: {zone['id']}")
            else:
                print("Failed to list zones.")

if __name__ == "__main__":
    main()
