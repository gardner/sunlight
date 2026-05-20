import importlib.util
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ingest_tenancy.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("ingest_tenancy", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class IngestTenancyTests(unittest.TestCase):
    def test_defaults_target_docling_tenancy_storage(self):
        module = load_module()

        args = module.build_parser().parse_args([])

        self.assertEqual(args.pdf_dir, Path("justice/data/tenancy/pdfs"))
        self.assertEqual(args.markdown_dir, Path("storage/justice/tenancy/markdown_docling"))
        self.assertEqual(args.persist_dir, Path("storage/justice/tenancy/lancedb"))
        self.assertEqual(args.convert_gpu, "0")
        self.assertEqual(args.embed_gpu, "0")
        self.assertEqual(args.llm_model, "nvidia/regular")
        self.assertEqual(args.llm_rpm, 40)
        self.assertEqual(args.llm_timeout, 120)
        self.assertEqual(args.llm_max_tokens, 4096)

    def test_embedded_marker_path_is_pipeline_specific(self):
        module = load_module()

        marker = module.embedded_marker_path(Path("/tmp/doc.md"))

        self.assertEqual(marker.name, f"doc.md.embedded.{module.EMBED_PIPELINE_VERSION}")

    def test_pending_markdown_paths_skip_non_docling_and_embedded_files(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_dir = Path(tmp_dir)
            ready = markdown_dir / "ready.md"
            ready.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_1"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\n---\n\nbody',
                encoding="utf-8",
            )
            markitdown = markdown_dir / "scratch.md"
            markitdown.write_text(
                '---\ndocument_id: "doc_justice_tenancy_2"\nsource: "justice_tenancy"\nparser: "markitdown"\n---\n\nbody',
                encoding="utf-8",
            )
            embedded = markdown_dir / "embedded.md"
            embedded.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_3"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\n---\n\nbody',
                encoding="utf-8",
            )
            module.embedded_marker_path(embedded).touch()

            paths = module.pending_embedding_markdown_paths(markdown_dir)

        self.assertEqual(paths, [ready])

    def test_apply_generated_enrichment_rewrites_frontmatter_and_preserves_body(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "doc.md"
            markdown_path.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_1"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\nlegal_issue_tags: ["rent_arrears"]\n---\n\nOriginal body.',
                encoding="utf-8",
            )

            module.apply_generated_enrichment(
                markdown_path,
                {
                    "case_summary": "The landlord obtained a rent arrears order.",
                    "catchwords": ["Rent arrears"],
                    "questions_answered": ["What did the Tribunal order?"],
                    "legal_principles": [
                        {
                            "principle": "Rent arrears can justify an order for payment.",
                            "confidence": "medium",
                            "source_section": "reasons",
                        }
                    ],
                },
                model="nvidia/regular",
                now="2026-05-20T00:00:00Z",
            )

            metadata, body = module.parse_tenancy_markdown(
                markdown_path.read_text(encoding="utf-8")
            )

        self.assertEqual(body, "Original body.")
        self.assertEqual(metadata["legal_issue_tags"], ["rent_arrears"])
        self.assertEqual(metadata["case_summary"], "The landlord obtained a rent arrears order.")
        self.assertEqual(metadata["llm_enrichment_model"], "nvidia/regular")
        self.assertEqual(metadata["llm_enrichment_version"], module.LLM_ENRICHMENT_VERSION)
        self.assertEqual(metadata["llm_enriched_at"], "2026-05-20T00:00:00Z")

    def test_pending_llm_paths_require_current_docling_pipeline(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_dir = Path(tmp_dir)
            ready = markdown_dir / "ready.md"
            ready.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_1"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\n---\n\nbody',
                encoding="utf-8",
            )
            old = markdown_dir / "old.md"
            old.write_text(
                '---\ndocument_id: "doc_justice_tenancy_2"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "old"\n---\n\nbody',
                encoding="utf-8",
            )
            complete = markdown_dir / "complete.md"
            complete.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_3"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\nllm_enrichment_version: "{module.LLM_ENRICHMENT_VERSION}"\n---\n\nbody',
                encoding="utf-8",
            )

            paths = module.pending_llm_markdown_paths(markdown_dir)
            forced = module.pending_llm_markdown_paths(markdown_dir, force=True)

        self.assertEqual(paths, [ready])
        self.assertEqual(forced, [complete, ready])

    def test_build_llm_input_limits_excerpt_and_preserves_ids(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "doc.md"
            markdown_path.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_1"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\nrequest_title: "Title"\nlegal_issue_tags: ["rent_arrears"]\n---\n\nabcdef',
                encoding="utf-8",
            )

            [item] = module.build_llm_input([markdown_path], max_chars=3)

        self.assertEqual(item["document_id"], "doc_justice_tenancy_1")
        self.assertEqual(item["title"], "Title")
        self.assertEqual(item["legal_issue_tags"], ["rent_arrears"])
        self.assertEqual(item["excerpt"], "abc")

    def test_request_generated_enrichment_retries_transient_failures(self):
        module = load_module()
        tenancy_llm = sys.modules["tenancy_llm"]
        calls = {"count": 0}
        original = tenancy_llm.request_generated_enrichment

        def flaky(*_args, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary")
            return module.GeneratedEnrichmentBatch(
                items=[
                    module.GeneratedEnrichment(
                        document_id="doc_justice_tenancy_1",
                        case_summary="Recovered.",
                    )
                ]
            )

        tenancy_llm.request_generated_enrichment = flaky
        try:
            result = module.request_generated_enrichment_with_retries(
                object(), [], "nvidia/regular", 5000, 4096
            )
        finally:
            tenancy_llm.request_generated_enrichment = original

        self.assertEqual(calls["count"], 2)
        self.assertEqual(result.items[0].case_summary, "Recovered.")

    def test_parse_enrichment_content_accepts_json_wrapped_in_text(self):
        module = load_module()

        parsed = module.parse_enrichment_content(
            'Here is the JSON: {"items":[{"document_id":"doc_justice_tenancy_1",'
            '"case_summary":"Summary.","catchwords":["Rent"],'
            '"questions_answered":[],"legal_principles":[],"llm_suggested_tags":[]}]}'
        )

        self.assertEqual(parsed.items[0].document_id, "doc_justice_tenancy_1")
        self.assertEqual(parsed.items[0].case_summary, "Summary.")

    def test_parse_enrichment_content_wraps_single_item_response(self):
        module = load_module()

        parsed = module.parse_enrichment_content(
            '{"case_summary":"Summary.",'
            '"catchwords":[],"questions_answered":[],"legal_principles":[],'
            '"llm_suggested_tags":[]}',
            default_document_id="doc_justice_tenancy_1",
        )

        self.assertEqual(len(parsed.items), 1)
        self.assertEqual(parsed.items[0].document_id, "doc_justice_tenancy_1")

    def test_run_conversion_counts_sequential_statuses(self):
        module = load_module()
        original = module.conversion_task
        statuses = iter(["converted", "skipped", "failed"])

        def fake_conversion_task(_document, _markdown_dir, _force):
            status = next(statuses)
            if status == "failed":
                raise RuntimeError("boom")
            return {"status": status}

        module.conversion_task = fake_conversion_task
        try:
            counts = module.run_conversion(
                [
                    SimpleNamespace(pdf_path=Path("a.pdf")),
                    SimpleNamespace(pdf_path=Path("b.pdf")),
                    SimpleNamespace(pdf_path=Path("c.pdf")),
                ],
                Path("/tmp/md"),
                workers=1,
                max_tasks_per_worker=0,
                convert_gpu="0",
                force=False,
            )
        finally:
            module.conversion_task = original

        self.assertEqual(counts, {"converted": 1, "skipped": 1, "failed": 1})

    def test_embed_batch_writes_source_and_generated_retrieval_records(self):
        module = load_module()

        class FakeDocument:
            def __init__(self, text, metadata):
                self.text = text
                self.metadata = metadata

        class FakeChunker:
            def run(self, documents):
                return documents

        class FakeEmbedModel:
            def get_text_embedding_batch(self, texts, show_progress):
                return [[0.1, 0.2] for _ in texts]

        class FakeWriter:
            def __init__(self):
                self.records = []

            def add_records(self, records):
                self.records.extend(records)

        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "doc.md"
            markdown_path.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_1"\nsource: "justice_tenancy"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\ncase_summary: "Summary view."\n---\n\nSource text.',
                encoding="utf-8",
            )
            writer = FakeWriter()

            module.embed_batch(
                [markdown_path],
                chunker=FakeChunker(),
                document_class=FakeDocument,
                embed_model=FakeEmbedModel(),
                writer=writer,
                embedding_model_name="test-model",
            )

        views = {record["retrieval_view"]: record for record in writer.records}
        self.assertEqual(set(views), {"source_text", "case_summary"})
        self.assertFalse(views["source_text"]["generated"])
        self.assertTrue(views["case_summary"]["generated"])
        self.assertEqual(views["case_summary"]["vector"], [0.1, 0.2])


if __name__ == "__main__":
    unittest.main()
