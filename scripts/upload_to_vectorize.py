"""POSTs prepared Vectorize NDJSON shards to a V2 insert endpoint.

Each successfully-accepted shard is marked with a `.uploaded` sidecar
containing the Cloudflare mutationId, so reruns skip what already
landed. Vectorize V2 inserts are asynchronous; the mutationId is the
handle for tracking eventual consistency."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib import request


DEFAULT_INPUT_DIR = Path("./storage/vectorize_export_v2")
DEFAULT_INDEX_NAME = "fyi-v2"
DEFAULT_SLEEP_BETWEEN = 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--index-name", default=DEFAULT_INDEX_NAME)
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_BETWEEN,
        help="Seconds to sleep between requests (helps stay under rate limits).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip shards that already have a .uploaded sidecar.",
    )
    return parser


def insert_url(account_id: str, index_name: str) -> str:
    return (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/vectorize/v2/indexes/{index_name}/insert"
    )


def post_ndjson(url: str, token: str, body: bytes) -> dict:
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-ndjson",
        },
    )
    with request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def upload_shard(url: str, token: str, shard: Path) -> tuple[bool, str]:
    body = shard.read_bytes()
    try:
        result = post_ndjson(url, token, body)
    except Exception as exc:  # urllib HTTPError or network error
        return False, f"transport error: {exc}"
    if not result.get("success"):
        return False, f"api error: {result.get('errors')}"
    mutation = (result.get("result") or {}).get("mutationId", "")
    sidecar = shard.with_suffix(shard.suffix + ".uploaded")
    sidecar.write_text(json.dumps({"mutationId": mutation, "size": shard.stat().st_size}))
    return True, mutation


def main() -> None:
    args = build_parser().parse_args()
    token = os.environ.get("CLOUDFLARE_VECTORIZE_TOKEN")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account_id:
        raise SystemExit("CLOUDFLARE_VECTORIZE_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set")
    shards = sorted(args.input_dir.glob("fyi_vectors_*.ndjson"))
    if not shards:
        raise SystemExit(f"No shards found in {args.input_dir}")
    url = insert_url(account_id, args.index_name)
    uploaded = failed = skipped = 0
    for shard in shards:
        sidecar = shard.with_suffix(shard.suffix + ".uploaded")
        if args.resume and sidecar.exists():
            skipped += 1
            continue
        ok, info = upload_shard(url, token, shard)
        if ok:
            uploaded += 1
            print(f"[{uploaded}/{len(shards) - skipped}] {shard.name} -> {info}", flush=True)
        else:
            failed += 1
            print(f"FAILED {shard.name}: {info}", file=sys.stderr, flush=True)
        if args.sleep:
            time.sleep(args.sleep)
    print(f"\nUploaded: {uploaded}  Skipped: {skipped}  Failed: {failed}", flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
