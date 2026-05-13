import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

import lancedb


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "parallel_convert_and_embed.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("parallel_convert_and_embed", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeQueue:
    def __init__(self):
        self.items = []

    def put(self, item, **_kwargs):
        self.items.append(item)


class ParallelConvertAndEmbedTests(unittest.TestCase):
    def test_safe_markdown_path_disambiguates_duplicate_filenames(self):
        module = load_module()

        first = module.safe_markdown_path(
            Path("/source/request/100/response/200/attach/1/Some%20PDF Name.pdf"),
            Path("/out"),
        )
        second = module.safe_markdown_path(
            Path("/source/request/101/response/201/attach/2/Some%20PDF Name.pdf"),
            Path("/out"),
        )

        self.assertEqual(first.suffix, ".md")
        self.assertIn("Some_PDF_Name.pdf", first.name)
        self.assertNotEqual(first, second)

    def test_build_document_metadata_extracts_fyi_provenance(self):
        module = load_module()
        pdf_path = Path(
            "/mnt/dgx-ssd/src/sunlight_nz/fyi/data/request/12117/response/47232/attach/2/Morrison%20OIA%20response.pdf"
        )
        markdown_path = Path("/tmp/doc_fyi_12117.md")

        metadata = module.build_document_metadata(pdf_path, markdown_path)

        self.assertEqual(metadata["source"], "fyi")
        self.assertEqual(metadata["parser"], "docling")
        self.assertEqual(metadata["fyi_request_id"], 12117)
        self.assertEqual(metadata["fyi_response_id"], 47232)
        self.assertEqual(metadata["fyi_attachment_id"], 2)
        self.assertEqual(metadata["request_url"], "https://fyi.org.nz/request/12117")
        self.assertEqual(
            metadata["source_url"],
            "https://fyi.org.nz/request/12117/response/47232/attach/2/"
            + quote("Morrison OIA response.pdf"),
        )
        self.assertEqual(
            metadata["markdown_r2_key"],
            "markdown/fyi/v1/request/12117/response/47232/attach/2/"
            + metadata["document_id"]
            + ".md",
        )

    def test_build_document_metadata_records_pymupdf_parser_when_specified(self):
        module = load_module()
        metadata = module.build_document_metadata(
            Path("/tmp/source/example.pdf"),
            Path("/tmp/out/example.md"),
            parser="pymupdf",
        )
        self.assertEqual(metadata["parser"], "pymupdf")

    def test_rescue_pdf_with_pymupdf_extracts_text_and_tags_parser(self):
        import pymupdf

        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "rescue.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Rescue path produced this text.")
            doc.save(str(pdf_path))
            doc.close()

            out_dir = Path(tmp_dir) / "md"
            out_dir.mkdir()

            ok, _, md_path = module.rescue_pdf_to_md_with_pymupdf(pdf_path, out_dir)

            self.assertTrue(ok)
            self.assertIsInstance(md_path, Path)
            rendered = md_path.read_text(encoding="utf-8")
            metadata, body = module.parse_markdown_document(rendered)
            self.assertEqual(metadata["parser"], "pymupdf")
            self.assertIn("Rescue path produced this text.", body)

    def test_rescue_pdf_with_pymupdf_returns_false_for_empty_file(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "empty.pdf"
            pdf_path.touch()
            out_dir = Path(tmp_dir) / "md"
            out_dir.mkdir()

            ok, _, info = module.rescue_pdf_to_md_with_pymupdf(pdf_path, out_dir)

            self.assertFalse(ok)
            self.assertFalse((out_dir / "empty.pdf__*.md").exists())
            self.assertIsInstance(info, str)

    def test_parse_markdown_document_raises_on_missing_frontmatter(self):
        module = load_module()
        with self.assertRaises(ValueError):
            module.parse_markdown_document("body without any frontmatter\n")

    def test_parse_markdown_document_raises_on_unclosed_frontmatter(self):
        module = load_module()
        with self.assertRaises(ValueError):
            module.parse_markdown_document("---\ndocument_id: foo\nbody here\n")

    def test_markdown_front_matter_round_trips(self):
        module = load_module()
        metadata = {
            "document_id": "doc_fyi_1_2_3_abcd1234",
            "source": "fyi",
            "source_url": "https://example.test/file.pdf",
            "request_url": "https://example.test/request/1",
            "fyi_request_id": 1,
        }
        body = "# Heading\n\nBody text.\n"

        rendered = module.render_markdown_document(metadata, body)
        parsed_metadata, parsed_body = module.parse_markdown_document(rendered)

        self.assertEqual(parsed_metadata, metadata)
        self.assertEqual(parsed_body, body)

    def test_put_markdown_for_embedding_skips_embedded_files(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "response.pdf.md"
            markdown_path.write_text("hello", encoding="utf-8")
            module.embedded_marker_path(markdown_path).touch()
            fake_queue = FakeQueue()

            self.assertFalse(module.put_markdown_for_embedding(fake_queue, markdown_path))
            self.assertEqual(fake_queue.items, [])

    def test_put_markdown_for_embedding_queues_unembedded_files(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "response.pdf.md"
            markdown_path.write_text("hello", encoding="utf-8")
            fake_queue = FakeQueue()

            self.assertTrue(module.put_markdown_for_embedding(fake_queue, markdown_path))
            self.assertEqual(fake_queue.items, [str(markdown_path)])

    def test_embedding_memory_defaults_are_bounded(self):
        module = load_module()

        args = module.build_parser().parse_args([])

        self.assertEqual(args.chunk_size, 1024)
        self.assertEqual(args.model_embed_batch_size, 64)

    def test_default_data_dirs_resolve_through_repo_symlink(self):
        module = load_module()

        args = module.build_parser().parse_args([])

        self.assertEqual(args.data_dir, Path("fyi/data/request"))
        self.assertEqual(args.markdown_dir, Path("fyi/markdown"))

    def test_default_gpu_layout_spans_both_cards(self):
        module = load_module()

        args = module.build_parser().parse_args([])

        self.assertEqual(args.convert_gpu, "0,1,0")
        self.assertEqual(args.embed_gpu, "1")

    def test_init_convert_worker_round_robins_across_gpus(self):
        import multiprocessing as mp

        module = load_module()
        counter = mp.Value("i", 0)
        original = os.environ.get("CUDA_VISIBLE_DEVICES")
        try:
            module._init_convert_worker(counter, ["0", "1"])
            first = os.environ["CUDA_VISIBLE_DEVICES"]
            module._init_convert_worker(counter, ["0", "1"])
            second = os.environ["CUDA_VISIBLE_DEVICES"]
            module._init_convert_worker(counter, ["0", "1"])
            third = os.environ["CUDA_VISIBLE_DEVICES"]
            self.assertEqual([first, second, third], ["0", "1", "0"])
        finally:
            if original is None:
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
            else:
                os.environ["CUDA_VISIBLE_DEVICES"] = original

    def test_init_convert_worker_pins_single_gpu(self):
        import multiprocessing as mp

        module = load_module()
        counter = mp.Value("i", 0)
        original = os.environ.get("CUDA_VISIBLE_DEVICES")
        try:
            module._init_convert_worker(counter, ["1"])
            self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "1")
            module._init_convert_worker(counter, ["1"])
            self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "1")
        finally:
            if original is None:
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
            else:
                os.environ["CUDA_VISIBLE_DEVICES"] = original

    def test_lancedb_writer_deduplicates_chunk_ids(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_dir = Path(tmp_dir) / "vectors.lancedb"
            writer = module.LanceDBChunkWriter(persist_dir)
            record = {
                "chunk_id": "chunk_doc_0001_abcd1234",
                "vector": [0.1, 0.2],
                "document_id": "doc_1",
                "chunk_index": 0,
                "chunk_text": "hello world",
                "text_preview": "hello world",
                "source": "fyi",
                "source_url": "https://example.test/file.pdf",
                "request_url": "https://example.test/request/1",
                "fyi_request_id": 1,
                "fyi_response_id": 2,
                "fyi_attachment_id": 3,
                "original_filename": "file.pdf",
                "pdf_r2_key": "canonical/fyi/v1/pdf/request/1/response/2/attach/3/file.pdf",
                "markdown_r2_key": "markdown/fyi/v1/request/1/response/2/attach/3/doc_1.md",
                "markdown_path": "/tmp/doc_1.md",
                "embedding_model": "test-model",
                "text_sha256": "abc123",
                "created_at": "2026-05-12T00:00:00Z",
                "vectorize_uploaded_at": None,
            }

            writer.add_records([record])
            writer.add_records([record])

            db = lancedb.connect(str(persist_dir))
            table = db.open_table(module.DEFAULT_TABLE_NAME)
            self.assertEqual(table.count_rows(), 1)


if __name__ == "__main__":
    unittest.main()
