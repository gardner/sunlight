import json
import subprocess
import re

def normalize(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

def main():
    # Load MoJ data
    with open('moj_authorities.json', 'r') as f:
        moj_data = json.load(f)

    moj_dict = {}
    for item in moj_data:
        name = item.get('Name')
        if not name:
            continue
        norm_name = normalize(name)
        email = item.get('ContactEmail')
        if not email:
            email = ''
        email = email.strip()
        if norm_name and email and '@' in email:
            # Pick first email if multiple
            email = email.split()[0]
            # remove mailto: if exists
            email = email.replace('mailto:', '')
            moj_dict[norm_name] = email
            
    print(f"Loaded {len(moj_dict)} MoJ authorities with emails")

    # Fetch D1 data
    print("Fetching D1 authorities...")
    result = subprocess.run([
        'pnpm', 'dlx', 'wrangler@latest', 'd1', 'execute', 'sunlight-requests',
        '--remote', '--json', '--command', 
        "SELECT id, name, primary_request_email, contact_status FROM sunlight_authorities;"
    ], capture_output=True, text=True, check=True)
    
    d1_payload = json.loads(result.stdout)
    # The wrangler output format is typically a list of result objects
    rows = d1_payload[0]['results']
    print(f"Fetched {len(rows)} D1 authorities")

    updates = []
    for row in rows:
        d1_norm = normalize(row['name'])
        if d1_norm in moj_dict:
            moj_email = moj_dict[d1_norm]
            # Update if it's missing, or if it's not verified
            if row['contact_status'] != 'verified' or row['primary_request_email'] != moj_email:
                updates.append((row['id'], moj_email))

    print(f"Found {len(updates)} authorities to update.")
    
    if not updates:
        return

    sql_statements = []
    for auth_id, email in updates:
        sql = f"UPDATE sunlight_authorities SET primary_request_email = '{email}', contact_status = 'verified', updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = '{auth_id}';"
        sql_statements.append(sql)

    sql_content = "\n".join(sql_statements)
    with open('update_moj.sql', 'w') as f:
        f.write(sql_content)
        
    print("Wrote update_moj.sql. Running wrangler...")
    subprocess.run([
        'pnpm', 'dlx', 'wrangler@latest', 'd1', 'execute', 'sunlight-requests',
        '--remote', '--file', 'update_moj.sql', '-y'
    ], check=True)
    print("Updates applied.")

if __name__ == '__main__':
    main()
