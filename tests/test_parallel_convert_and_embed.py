import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "parallel_convert_and_embed.py"


def load_module():
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
    def test_safe_markdown_path_matches_existing_naming(self):
        module = load_module()

        self.assertEqual(
            module.safe_markdown_path(
                Path("/source/Some%20PDF Name.pdf"),
                Path("/out"),
            ),
            Path("/out/Some_PDF_Name.pdf.md"),
        )

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


if __name__ == "__main__":
    unittest.main()
