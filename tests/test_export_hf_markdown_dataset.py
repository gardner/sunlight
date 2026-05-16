import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import export_hf_markdown_dataset as exporter  # noqa: E402
from fyi_markdown import render_markdown_document  # noqa: E402


EXPORTED_AT = "2026-05-17T00:00:00Z"


def base_metadata() -> dict[str, object]:
    return {
        "document_id": "doc_fyi_29087_1_2",
        "fyi_attachment_id": 2,
        "fyi_request_id": 29087,
        "fyi_response_id": 1,
        "markdown_r2_key": "fyi/markdown/doc_fyi_29087_1_2.md",
        "original_filename": "release.pdf",
        "pdf_r2_key": "fyi/pdf/doc_fyi_29087_1_2.pdf",
        "request_url": "https://fyi.org.nz/request/29087",
        "source": "fyi",
        "source_url": "https://fyi.org.nz/request/29087/response/1/attach/2/release.pdf",
    }


def request_metadata() -> dict[str, object]:
    return {
        "authority_category": "city_council",
        "authority_name": "Auckland Council",
        "authority_slug": "auckland_council",
        "described_state": "partially_successful",
        "law_used": "lgoima",
        "request_created_at": "2024-11-06T16:36:43+13:00",
        "request_title": "Auckland Council Owned Leisure Centres",
        "request_year": 2024,
    }


class HuggingFaceMarkdownDatasetTests(unittest.TestCase):
    def test_iter_dataset_rows_preserves_content_and_joins_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            markdown_dir = Path(tmp) / "markdown"
            markdown_dir.mkdir()
            body = "# Released material\n\nThe council disclosed the lease summary.\n"
            (markdown_dir / "release.md").write_text(
                render_markdown_document(base_metadata(), body),
                encoding="utf-8",
            )

            args = SimpleNamespace(
                corpus_version="fyi-test",
                limit=None,
                markdown_dir=markdown_dir,
            )
            rows = list(
                exporter.iter_dataset_rows(
                    args,
                    {29087: request_metadata()},
                    EXPORTED_AT,
                    set(),
                )
            )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["markdown_content"], body)
        self.assertEqual(row["authority_name"], "Auckland Council")
        self.assertEqual(row["authority_category"], "city_council")
        self.assertEqual(row["fyi_request_id"], 29087)
        self.assertEqual(row["request_year"], 2024)
        self.assertEqual(row["corpus_version"], "fyi-test")
        self.assertEqual(row["content_chars"], len(body))
        self.assertEqual(json.loads(row["frontmatter_json"]), base_metadata())

    def test_iter_dataset_rows_skips_previous_record_ids_for_delta_exports(self):
        metadata = base_metadata()
        body = "A released document.\n"
        first_row = exporter.build_row(
            Path("release.md"),
            metadata,
            request_metadata(),
            body,
            "fyi-test",
            EXPORTED_AT,
        )

        with tempfile.TemporaryDirectory() as tmp:
            markdown_dir = Path(tmp) / "markdown"
            markdown_dir.mkdir()
            (markdown_dir / "release.md").write_text(
                render_markdown_document(metadata, body),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                corpus_version="fyi-test",
                limit=None,
                markdown_dir=markdown_dir,
            )
            rows = list(
                exporter.iter_dataset_rows(
                    args,
                    {29087: request_metadata()},
                    EXPORTED_AT,
                    {first_row["record_id"]},
                )
            )

        self.assertEqual(rows, [])

    def test_iter_dataset_rows_includes_frontmatterless_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            markdown_dir = Path(tmp) / "markdown"
            markdown_dir.mkdir()
            body = "# Legacy Markdown\n\nConverted before provenance was added.\n"
            (markdown_dir / "legacy.pdf.md").write_text(body, encoding="utf-8")
            args = SimpleNamespace(
                corpus_version="fyi-test",
                limit=None,
                markdown_dir=markdown_dir,
            )
            rows = list(exporter.iter_dataset_rows(args, {}, EXPORTED_AT, set()))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["markdown_content"], body)
        self.assertEqual(rows[0]["frontmatter_json"], "{}")
        self.assertEqual(rows[0]["markdown_filename"], "legacy.pdf.md")
        self.assertTrue(rows[0]["document_id"].startswith("doc_local_"))

    def test_write_parquet_shards_and_record_index(self):
        row = exporter.build_row(
            Path("release.md"),
            base_metadata(),
            request_metadata(),
            "A released document.\n",
            "fyi-test",
            EXPORTED_AT,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            shards = exporter.write_parquet_shards(
                [row],
                output_dir / "data",
                rows_per_shard=1,
                output_dir=output_dir,
            )
            table_rows = pq.read_table(
                output_dir / "data" / "fyi_markdown-00000.parquet"
            ).to_pylist()
            exporter.write_record_index(
                [row],
                output_dir / "manifests" / "record-index.ndjson",
            )

            previous_ids = exporter.read_previous_record_ids(output_dir / "manifests")

        self.assertEqual(shards[0]["path"], "data/fyi_markdown-00000.parquet")
        self.assertEqual(shards[0]["rows"], 1)
        self.assertEqual(table_rows[0]["record_id"], row["record_id"])
        self.assertEqual(table_rows[0]["markdown_content"], "A released document.\n")
        self.assertEqual(previous_ids, {row["record_id"]})

    def test_delta_export_paths_are_append_safe(self):
        data_dir, manifest_dir, shard_prefix = exporter.export_paths(
            Path("out"),
            "delta",
            "20260517-000000",
        )

        self.assertEqual(data_dir, Path("out/data/deltas/20260517-000000"))
        self.assertEqual(manifest_dir, Path("out/manifests/deltas/20260517-000000"))
        self.assertEqual(shard_prefix, "fyi_markdown_delta")


if __name__ == "__main__":
    unittest.main()
