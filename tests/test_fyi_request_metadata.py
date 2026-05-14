import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "fyi_requests"

sys.path.insert(0, str(SCRIPTS_DIR))

import fyi_request_metadata  # noqa: E402


class DeriveAuthorityCategoryTests(unittest.TestCase):
    def test_picks_specific_tag_over_popular_agency(self):
        tags = [["popular_agency", None], ["city_council", None]]
        self.assertEqual(
            fyi_request_metadata.derive_authority_category(tags), "city_council"
        )

    def test_picks_specific_tag_over_not_apply(self):
        tags = [["not_apply", None], ["ministry", None]]
        self.assertEqual(
            fyi_request_metadata.derive_authority_category(tags), "ministry"
        )

    def test_returns_none_when_only_flag_tags_present(self):
        tags = [["popular_agency", None], ["not_apply", None]]
        self.assertIsNone(fyi_request_metadata.derive_authority_category(tags))

    def test_returns_none_for_empty_tags(self):
        self.assertIsNone(fyi_request_metadata.derive_authority_category([]))

    def test_accepts_flat_strings_as_well_as_pairs(self):
        self.assertEqual(
            fyi_request_metadata.derive_authority_category(["dhb"]), "dhb"
        )


class LoadRequestMetadataTests(unittest.TestCase):
    def setUp(self):
        self.index = fyi_request_metadata.load_request_metadata(FIXTURE_DIR)

    def test_indexed_by_integer_request_id(self):
        self.assertIn(29087, self.index)
        self.assertIn(12345, self.index)

    def test_processed_json_is_excluded(self):
        # 14553 only appears in the _processed.json fixture
        self.assertNotIn(14553, self.index)

    def test_authority_slug_and_name(self):
        entry = self.index[29087]
        self.assertEqual(entry["authority_slug"], "auckland_council")
        self.assertEqual(entry["authority_name"], "Auckland Council")

    def test_authority_category_is_derived(self):
        self.assertEqual(self.index[29087]["authority_category"], "city_council")
        self.assertEqual(self.index[12345]["authority_category"], "ministry")
        self.assertIsNone(self.index[77777]["authority_category"])

    def test_law_used_and_described_state_preserved(self):
        entry = self.index[29087]
        self.assertEqual(entry["law_used"], "foi")
        self.assertEqual(entry["described_state"], "partially_successful")
        self.assertEqual(self.index[77777]["law_used"], "lgoima")

    def test_request_year_extracted_from_created_at(self):
        self.assertEqual(self.index[29087]["request_year"], 2024)
        self.assertEqual(self.index[12345]["request_year"], 2019)

    def test_url_title_and_title_preserved(self):
        entry = self.index[29087]
        self.assertEqual(entry["url_title"], "auckland-council-owned-leisure-centres")
        self.assertEqual(entry["request_title"], "Auckland Council Owned Leisure Centres")

    def test_missing_public_body_yields_none_authority_fields(self):
        entry = self.index[55555]
        self.assertIsNone(entry["authority_slug"])
        self.assertIsNone(entry["authority_name"])
        self.assertIsNone(entry["authority_category"])
        # Other fields still come through
        self.assertEqual(entry["law_used"], "foi")
        self.assertEqual(entry["described_state"], "waiting_response")

    def test_request_created_at_preserved_as_iso_string(self):
        self.assertEqual(
            self.index[29087]["request_created_at"], "2024-11-06T16:36:43+13:00"
        )

    def test_corrupt_json_files_are_skipped(self):
        # 88888-corrupt.json is HTML, not JSON. Loader must not crash.
        self.assertNotIn(88888, self.index)


if __name__ == "__main__":
    unittest.main()
