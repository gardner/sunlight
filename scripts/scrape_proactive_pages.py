import argparse
import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

class Authority(NamedTuple):
    id: str
    name: str
    primary_request_email: str | None

def get_brave_key() -> str | None:
    key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if key:
        return key
    if Path(".env").exists():
        with open(".env") as f:
            for line in f:
                if line.startswith("BRAVE_SEARCH_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"\'')
    return None

def fetch_authorities(database: str, limit: int, offset: int, retry_attempted: bool, remote: bool) -> list[Authority]:
    query = """
        SELECT
            a.id,
            a.name,
            a.primary_request_email
        FROM sunlight_authorities a
    """
    if not retry_attempted:
        query += """
            LEFT JOIN sunlight_authority_proactive_scrape_attempts s
              ON s.authority_id = a.id
        """
    query += """
        WHERE a.status = 'active'
          AND a.proactive_release_url IS NULL
    """
    if not retry_attempted:
        query += " AND s.authority_id IS NULL"

    query += f" ORDER BY a.name LIMIT {limit} OFFSET {offset}"

    command = ["pnpm", "dlx", "wrangler@latest", "d1", "execute", database, "--json", "--command", query]
    if remote:
        command.append("--remote")

    print(f"Fetching authorities with query:\\n{query}")
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    results = wrangler_results(json.loads(completed.stdout))
    return [Authority(**row) for row in results]

def wrangler_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            rows.extend(wrangler_results(item))
        return rows
    if isinstance(payload, dict):
        if "results" in payload:
            return payload["results"]
        if isinstance(payload.get("result"), list):
            return wrangler_results(payload["result"])
    return []

async def brave_search(
    session: AsyncSession,
    api_key: str,
    query: str,
    *,
    count: int = 3,
) -> list[str]:
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    params = {"q": query, "count": str(count)}
    
    response = await session.get(BRAVE_SEARCH_URL, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    urls = []
    if "web" in data and "results" in data["web"]:
        for result in data["web"]["results"]:
            urls.append(result["url"])
    return urls

def extract_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    domain = email.split("@")[-1].strip().lower()
    # Basic filters
    if domain in ("gmail.com", "xtra.co.nz", "xtra.com", "outlook.com", "yahoo.co.nz", "yahoo.com"):
        return None
    return domain

async def find_proactive_page(authority: Authority, session: AsyncSession, brave_key: str | None, brave_semaphore: asyncio.Semaphore) -> tuple[str | None, str | None]:
    domain = extract_domain(authority.primary_request_email)
    
    if not domain or not brave_key:
        return None, "No valid domain or brave key"

    query = f'site:{domain} "proactive release" OR "OIA responses" OR "official information responses" OR "LGOIMA responses"'
    
    try:
        async with brave_semaphore:
            urls = await brave_search(session, brave_key, query, count=3)
    except Exception as e:
        return None, f"Brave search failed: {e}"

    if not urls:
        return None, "No results found"

    # Filter out common false positives (like pdfs or docs)
    good_urls = [u for u in urls if not u.lower().endswith(('.pdf', '.docx', '.doc'))]
    
    if good_urls:
        return good_urls[0], None
    return urls[0], None

async def process_authority(
    authority: Authority,
    session: AsyncSession,
    brave_key: str | None,
    brave_semaphore: asyncio.Semaphore,
) -> tuple[str, str | None, str | None]:
    url, error = await find_proactive_page(authority, session, brave_key, brave_semaphore)
    if url:
        print(f"[{authority.name}] Found proactive release page: {url}")
    else:
        print(f"[{authority.name}] No proactive release page found. ({error})")
    return authority.id, url, error

def generate_sql(results: list[tuple[str, str | None, str | None]]) -> str:
    sql = ""
    for auth_id, url, error in results:
        if url:
            sql += f"UPDATE sunlight_authorities SET proactive_release_url = '{url}', updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = '{auth_id}';\n"
        
        err_val = f"'{error.replace(chr(39), chr(39)+chr(39))}'" if error else "NULL"
        sql += f"INSERT OR REPLACE INTO sunlight_authority_proactive_scrape_attempts (authority_id, attempted_at, error_message) VALUES ('{auth_id}', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), {err_val});\n"
    return sql

def apply_sql(database: str, generated_sql: str, *, remote: bool) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as file:
        file.write(generated_sql)
        sql_path = Path(file.name)

    command = ["pnpm", "dlx", "wrangler@latest", "d1", "execute", database, "--file", str(sql_path), "-y"]
    if remote:
        command.append("--remote")

    try:
        subprocess.run(command, check=True)
    finally:
        sql_path.unlink(missing_ok=True)

async def async_main(args: argparse.Namespace) -> None:
    brave_key = get_brave_key()
    if not brave_key:
        print("Warning: BRAVE_SEARCH_API_KEY not found. Search will fail.")

    authorities = fetch_authorities(
        database=args.database,
        limit=args.limit,
        offset=args.offset,
        retry_attempted=args.retry_attempted,
        remote=args.remote,
    )

    if not authorities:
        print("No authorities to process.")
        return

    print(f"Loaded {len(authorities)} authorities.")

    brave_semaphore = asyncio.Semaphore(args.brave_concurrency)

    async with AsyncSession(timeout=args.timeout) as session:
        tasks = [
            process_authority(
                authority,
                session,
                brave_key,
                brave_semaphore,
            )
            for authority in authorities
        ]
        results = await asyncio.gather(*tasks)

    sql = generate_sql(results)
    
    if args.dry_run:
        print("\\n--- DRY RUN SQL ---")
        print(sql)
    else:
        print("\nApplying SQL to D1...")
        apply_sql(args.database, sql, remote=args.remote)
        print("Done.")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="sunlight-requests")
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--retry-attempted", action="store_true")
    parser.add_argument("--brave-concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    asyncio.run(async_main(args))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
