from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CLOUDFLARE_TOMARKDOWN_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/tomarkdown"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare Cloudflare Workers AI Markdown Conversion against Docling."
    )
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("storage/evals/markdown_conversion"),
    )
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    parser.add_argument(
        "--cloudflare-url",
        help="Optional Worker endpoint that proxies env.AI.toMarkdown.",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--include-pdf-metadata", action="store_true")
    return parser


def load_dotenv_file(path: Path, env: dict[str, str]) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env.setdefault(key.strip(), value.strip().strip("\"'"))


def markdown_metrics(markdown: str) -> dict[str, Any]:
    lines = markdown.splitlines()
    return {
        "chars": len(markdown),
        "lines": len(lines),
        "headings": sum(1 for line in lines if re.match(r"^#{1,6}\s+\S", line)),
        "tables": count_markdown_tables(lines),
        "money_amounts": len(re.findall(r"\$\s*[0-9][0-9,]*(?:\.[0-9]{2})?", markdown)),
        "nztt_citations": sorted(set(extract_nztt_citations(markdown))),
        "decision_dates": sorted(set(extract_long_dates(markdown))),
        "has_boilerplate": "please read carefully" in markdown.lower(),
    }


def count_markdown_tables(lines: list[str]) -> int:
    tables = 0
    in_table = False
    for line in lines:
        is_table_line = "|" in line and bool(re.search(r"\S\s*\|\s*\S", line))
        if is_table_line and not in_table:
            tables += 1
        in_table = is_table_line
    return tables


def extract_nztt_citations(text: str) -> list[str]:
    matches = re.finditer(
        r"\[\d{4}\][^\S\r\n]+NZTT(?:[^\S\r\n]+[A-Za-z][A-Za-z /'-]+)?[^\S\r\n]+\d[\d, ]*",
        text,
        flags=re.IGNORECASE,
    )
    return [" ".join(match.group(0).replace("nztt", "NZTT").split()) for match in matches]


def extract_long_dates(text: str) -> list[str]:
    month_names = (
        "January|February|March|April|May|June|July|August|"
        "September|October|November|December"
    )
    dates: list[str] = []
    for match in re.finditer(rf"\b([0-3]?\d\s+(?:{month_names})\s+20\d{{2}})\b", text):
        dates.append(normalize_long_date(match.group(1)))
    return [date for date in dates if date]


def normalize_long_date(value: str) -> str | None:
    try:
        return datetime.strptime(" ".join(value.split()), "%d %B %Y").date().isoformat()
    except ValueError:
        return None


def compare_metrics(docling: dict[str, Any], cloudflare: dict[str, Any]) -> dict[str, Any]:
    docling_chars = int(docling["chars"])
    cloudflare_chars = int(cloudflare["chars"])
    return {
        "cloudflare_to_docling_char_ratio": round(
            cloudflare_chars / docling_chars, 3
        )
        if docling_chars
        else None,
        "table_delta": int(cloudflare["tables"]) - int(docling["tables"]),
        "heading_delta": int(cloudflare["headings"]) - int(docling["headings"]),
        "money_amount_delta": int(cloudflare["money_amounts"]) - int(docling["money_amounts"]),
        "missing_cloudflare_citations": sorted(
            set(docling["nztt_citations"]) - set(cloudflare["nztt_citations"])
        ),
        "missing_cloudflare_dates": sorted(
            set(docling["decision_dates"]) - set(cloudflare["decision_dates"])
        ),
    }


def convert_with_docling(pdf_path: Path) -> str:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    return result.document.export_to_markdown()


def convert_with_cloudflare(
    pdf_path: Path,
    *,
    account_id: str | None,
    api_token: str | None,
    cloudflare_url: str | None,
    include_pdf_metadata: bool,
    timeout: int,
) -> str:
    body, content_type = multipart_body(
        pdf_path,
        conversion_options={"pdf": {"metadata": include_pdf_metadata}},
    )
    endpoint = cloudflare_url or CLOUDFLARE_TOMARKDOWN_URL.format(account_id=account_id)
    headers = {
        "Content-Type": content_type,
        "User-Agent": "sunlight-markdown-comparison/1.0",
    }
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Cloudflare conversion failed: HTTP {exc.code}: {details}") from exc

    return markdown_from_cloudflare_payload(payload)


def multipart_body(pdf_path: Path, conversion_options: dict[str, object]) -> tuple[bytes, str]:
    boundary = f"----sunlight-{secrets.token_hex(16)}"
    mime_type = mimetypes.guess_type(pdf_path.name)[0] or "application/pdf"
    parts = [
        multipart_file_part(boundary, "files", pdf_path, mime_type),
        multipart_field_part(boundary, "conversionOptions", json.dumps(conversion_options)),
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def multipart_file_part(boundary: str, field: str, path: Path, mime_type: str) -> bytes:
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    return header + path.read_bytes() + b"\r\n"


def multipart_field_part(boundary: str, field: str, value: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def markdown_from_cloudflare_payload(payload: dict[str, Any] | list[Any]) -> str:
    if isinstance(payload, list):
        results = payload
    elif payload.get("success"):
        results = payload.get("result")
    else:
        raise RuntimeError(f"Cloudflare conversion failed: {payload}")

    if not isinstance(results, list) or not results:
        raise RuntimeError(f"Cloudflare conversion returned no results: {payload}")
    result = results[0]
    if result.get("format") != "markdown":
        raise RuntimeError(f"Cloudflare conversion returned error: {result}")
    data = result.get("data")
    if not isinstance(data, str):
        raise RuntimeError(f"Cloudflare conversion returned non-text data: {result}")
    return data


def compare_pdf(
    pdf_path: Path,
    *,
    output_dir: Path,
    account_id: str | None,
    api_token: str | None,
    cloudflare_url: str | None,
    include_pdf_metadata: bool,
    timeout: int,
) -> dict[str, Any]:
    docling_started = time.monotonic()
    docling_markdown = convert_with_docling(pdf_path)
    docling_seconds = time.monotonic() - docling_started

    cloudflare_started = time.monotonic()
    cloudflare_markdown = convert_with_cloudflare(
        pdf_path,
        account_id=account_id,
        api_token=api_token,
        cloudflare_url=cloudflare_url,
        include_pdf_metadata=include_pdf_metadata,
        timeout=timeout,
    )
    cloudflare_seconds = time.monotonic() - cloudflare_started

    stem_dir = output_dir / pdf_path.stem
    stem_dir.mkdir(parents=True, exist_ok=True)
    (stem_dir / "docling.md").write_text(docling_markdown, encoding="utf-8")
    (stem_dir / "cloudflare.md").write_text(cloudflare_markdown, encoding="utf-8")

    docling_metrics = markdown_metrics(docling_markdown)
    cloudflare_metrics = markdown_metrics(cloudflare_markdown)
    row = {
        "pdf": str(pdf_path),
        "docling_seconds": round(docling_seconds, 3),
        "cloudflare_seconds": round(cloudflare_seconds, 3),
        "docling": docling_metrics,
        "cloudflare": cloudflare_metrics,
        "comparison": compare_metrics(docling_metrics, cloudflare_metrics),
    }
    (stem_dir / "metrics.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def write_report(rows: list[dict[str, Any]], output_dir: Path) -> None:
    lines = [
        "# Markdown Conversion Comparison",
        "",
        "| PDF | Docling s | Cloudflare s | Char ratio | Tables | Missing citations | Missing dates |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        comparison = row["comparison"]
        lines.append(
            "| {pdf} | {docling_seconds} | {cloudflare_seconds} | {ratio} | {tables} | {citations} | {dates} |".format(
                pdf=Path(row["pdf"]).name,
                docling_seconds=row["docling_seconds"],
                cloudflare_seconds=row["cloudflare_seconds"],
                ratio=comparison["cloudflare_to_docling_char_ratio"],
                tables=comparison["table_delta"],
                citations=", ".join(comparison["missing_cloudflare_citations"]) or "-",
                dates=", ".join(comparison["missing_cloudflare_dates"]) or "-",
            )
        )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    load_dotenv_file(args.dotenv, os.environ)
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not args.cloudflare_url and (not account_id or not api_token):
        raise SystemExit("CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required")

    run_dir = args.output_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        compare_pdf(
            pdf_path,
            output_dir=run_dir,
            account_id=account_id,
            api_token=api_token,
            cloudflare_url=args.cloudflare_url,
            include_pdf_metadata=args.include_pdf_metadata,
            timeout=args.timeout,
        )
        for pdf_path in args.pdfs
    ]
    write_report(rows, run_dir)
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
