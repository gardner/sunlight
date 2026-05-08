from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import tempfile
from pathlib import Path


LGOIMA_TAGS = {
    "city_council",
    "district_council",
    "law:lgoima",
    "regional_council",
}

OIA_TAGS = {
    "crown_research_institute",
    "departmental_agency",
    "dhb",
    "law:OIA",
    "minister",
    "ministry",
    "university",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import FYI authorities into D1.")
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to FYI all-authorities.csv.",
    )
    parser.add_argument(
        "--database",
        default="sunlight-requests",
        help="D1 database name.",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Apply to the remote D1 database instead of local D1.",
    )
    parser.add_argument(
        "--write-sql",
        type=Path,
        help="Write generated SQL to this path instead of applying it.",
    )
    parser.add_argument(
        "--transaction",
        action="store_true",
        help="Wrap generated SQL in BEGIN/COMMIT. Do not use with remote D1.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_rows(args.csv_path)
    sql = build_import_sql(rows, transaction=args.transaction)

    if args.write_sql:
        args.write_sql.write_text(sql)
        return 0

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as file:
        file.write(sql)
        sql_path = Path(file.name)

    command = [
        "pnpm",
        "dlx",
        "wrangler@latest",
        "d1",
        "execute",
        args.database,
        "--file",
        str(sql_path),
    ]
    if args.remote:
        command.append("--remote")

    try:
        subprocess.run(command, check=True)
    finally:
        sql_path.unlink(missing_ok=True)

    return 0


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def build_import_sql(rows: list[dict[str, str]], *, transaction: bool = False) -> str:
    statements = ["BEGIN TRANSACTION;"] if transaction else []
    for row in rows:
        statements.append(upsert_statement(row))
    if transaction:
        statements.append("COMMIT;")
    return "\n".join(statements) + "\n"


def upsert_statement(row: dict[str, str]) -> str:
    slug = row["URL name"].strip()
    tags = tags_for(row)
    status = "inactive" if "defunct" in tags else "active"
    metadata = {
        "disclosure_log": empty_to_none(row["Disclosure log"]),
        "home_page": empty_to_none(row["Home page"]),
        "publication_scheme": empty_to_none(row["Publication scheme"]),
        "short_name": empty_to_none(row["Short name"]),
        "tags": sorted(tags),
        "version": empty_to_none(row["Version"]),
    }
    values = {
        "id": f"agy_fyi_{safe_identifier(slug)}",
        "name": row["Name"].strip(),
        "slug": slug,
        "legal_regime": infer_legal_regime(tags),
        "source": "fyi",
        "source_id": slug,
        "source_url": f"https://fyi.org.nz/body/{slug}",
        "source_updated_at": empty_to_none(row["Updated at"]),
        "source_metadata_json": json.dumps(metadata, sort_keys=True),
        "notes": row["Notes"].strip() or None,
        "status": status,
    }

    return f"""
INSERT INTO sunlight_agencies (
  id,
  name,
  slug,
  legal_regime,
  primary_request_email,
  secondary_request_emails_json,
  contact_status,
  status,
  source,
  source_id,
  source_url,
  source_updated_at,
  source_metadata_json,
  notes
) VALUES (
  {sql(values["id"])},
  {sql(values["name"])},
  {sql(values["slug"])},
  {sql(values["legal_regime"])},
  NULL,
  '[]',
  'missing',
  {sql(values["status"])},
  {sql(values["source"])},
  {sql(values["source_id"])},
  {sql(values["source_url"])},
  {sql(values["source_updated_at"])},
  {sql(values["source_metadata_json"])},
  {sql(values["notes"])}
)
ON CONFLICT(source, source_id) DO UPDATE SET
  name = excluded.name,
  slug = excluded.slug,
  legal_regime = excluded.legal_regime,
  status = excluded.status,
  source_url = excluded.source_url,
  source_updated_at = excluded.source_updated_at,
  source_metadata_json = excluded.source_metadata_json,
  notes = excluded.notes,
  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE sunlight_agencies.contact_status != 'verified';
""".strip()


def infer_legal_regime(tags: set[str]) -> str:
    if tags & LGOIMA_TAGS:
        return "LGOIMA"
    if tags & OIA_TAGS:
        return "OIA"
    return "other"


def tags_for(row: dict[str, str]) -> set[str]:
    return {tag for tag in re.split(r"\s+", row["Tags"].strip()) if tag}


def empty_to_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def safe_identifier(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return safe or "authority"


def sql(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
