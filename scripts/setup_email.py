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
    token = env.get('CLOUDFLARE_API_TOKEN')
    
    if not token:
        print("No CLOUDFLARE_API_TOKEN found")
        return
        
    print("Fetching zones...")
    zones = req('GET', 'https://api.cloudflare.com/client/v4/zones?name=sunlight.nz', token)
    if not zones or not zones.get('success') or not zones['result']:
        print("Failed to fetch zone sunlight.nz.")
        return
        
    zone_id = zones['result'][0]['id']
    account_id = zones['result'][0]['account']['id']
    print(f"Zone ID: {zone_id}")
    print(f"Account ID: {account_id}")

    print("\n--- Listing Destination Addresses ---")
    dest_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/email/routing/addresses"
    destinations = req('GET', dest_url, token)
    if destinations and destinations.get('success'):
        for dest in destinations['result']:
            print(f"Destination: {dest['email']} - Verified: {dest['verified']}")
            
    print("\n--- Adding Destination Address gbickford@gmail.com ---")
    add_dest = req('POST', dest_url, token, {"email": "gbickford@gmail.com"})
    if add_dest and add_dest.get('success'):
        print("Successfully requested destination verification. User must check email and click link.")
    else:
        print("Destination might already exist or request failed.")

    print("\n--- Listing Routing Rules ---")
    rules_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/email/routing/rules"
    rules = req('GET', rules_url, token)
    if rules and rules.get('success'):
        for rule in rules['result']:
            print(f"Rule: {rule['name']} - Enabled: {rule['enabled']}")
            
    print("\n--- Adding Routing Rule for requests@sunlight.nz ---")
    rule_payload = {
        "name": "Sunlight Requests Sender",
        "enabled": True,
        "matchers": [{"type": "literal", "field": "to", "value": "requests@sunlight.nz"}],
        "actions": [{"type": "worker", "value": ["sunlight-inbound-email"]}]
    }
    add_rule = req('POST', rules_url, token, rule_payload)
    if add_rule and add_rule.get('success'):
        print("Successfully added rule for requests@sunlight.nz to route to worker!")
    else:
        print("Failed to add rule.")

if __name__ == "__main__":
    main()
