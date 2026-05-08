import unittest

from scripts.import_fyi_authorities import (
    build_import_sql,
    infer_legal_regime,
    sql,
    upsert_statement,
)


class FyiAuthorityImportTests(unittest.TestCase):
    def test_infers_lgoima_for_councils(self):
        self.assertEqual(infer_legal_regime({"district_council"}), "LGOIMA")

    def test_infers_oia_for_ministries(self):
        self.assertEqual(infer_legal_regime({"ministry"}), "OIA")

    def test_infers_oia_for_upstream_departmental_tag(self):
        self.assertEqual(infer_legal_regime({"departmental_agency"}), "OIA")

    def test_sql_escapes_single_quotes(self):
        self.assertEqual(sql("Bob's authority"), "'Bob''s authority'")

    def test_import_rows_are_not_sendable_by_default(self):
        statement = upsert_statement(example_row())

        self.assertIn("'missing'", statement)
        self.assertIn("primary_request_email", statement)
        self.assertIn("NULL", statement)

    def test_generated_sql_omits_transactions_by_default(self):
        generated = build_import_sql([example_row()])

        self.assertNotIn("BEGIN TRANSACTION", generated)
        self.assertNotIn("COMMIT", generated)


def example_row():
    return {
        "Name": "Example Authority",
        "Short name": "EA",
        "URL name": "example_authority",
        "Tags": "ministry",
        "Home page": "https://example.govt.nz",
        "Publication scheme": "",
        "Disclosure log": "",
        "Notes": "",
        "Created at": "",
        "Updated at": "2025-01-01 00:00:00 +1300",
        "Version": "1",
    }


if __name__ == "__main__":
    unittest.main()
