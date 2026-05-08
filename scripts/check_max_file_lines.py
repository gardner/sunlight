from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".py",
    ".scss",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when source files exceed a configured line count.",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        required=True,
        help="Maximum allowed lines per checked file.",
    )
    parser.add_argument("files", nargs="*", help="Files to check.")
    return parser.parse_args()


def should_check(path: Path) -> bool:
    return path.is_file() and path.suffix in DEFAULT_EXTENSIONS


def count_lines(path: Path) -> int:
    with path.open("rb") as file:
        return sum(1 for _ in file)


def main() -> int:
    args = parse_args()
    failures = []

    for filename in args.files:
        path = Path(filename)
        if not should_check(path):
            continue

        line_count = count_lines(path)
        if line_count > args.max_lines:
            failures.append((path, line_count))

    if failures:
        print(f"Files exceed max line count ({args.max_lines}):")
        for path, line_count in failures:
            print(f"  {path}: {line_count} lines")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
