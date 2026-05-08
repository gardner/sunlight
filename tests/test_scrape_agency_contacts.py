import unittest

from scripts.scrape_agency_contacts import (
    Agency,
    build_scrape_sql,
    candidate_id,
    discover_page_emails,
    find_candidate_links,
    normalize_email,
    score_email,
)


class AgencyContactScraperTests(unittest.TestCase):
    def test_normalizes_mailto_and_idna_domains(self):
        self.assertEqual(
            normalize_email("mailto:OIA@tamahere.māori.nz?subject=Request"),
            "oia@tamahere.xn--mori-qsa.nz",
        )

    def test_rejects_bad_or_unsafe_addresses(self):
        self.assertIsNone(normalize_email("noreply@example.govt.nz"))
        self.assertIsNone(normalize_email("person@example"))
        self.assertIsNone(normalize_email("not an email"))

    def test_discovers_mailto_visible_and_obfuscated_emails(self):
        html = """
        <html>
          <head><title>Official information</title></head>
          <body>
            <a href="mailto:OIA@example.govt.nz?subject=OIA">Make an OIA request</a>
            Contact privacy [at] example.govt.nz for privacy requests.
            General enquiries: info@example.govt.nz
          </body>
        </html>
        """

        emails = discover_page_emails(
            html,
            source_url="https://example.govt.nz/official-information",
            discovery_method="linked_page",
        )

        self.assertEqual(
            sorted(email.normalized_email for email in emails),
            ["info@example.govt.nz", "oia@example.govt.nz", "privacy@example.govt.nz"],
        )
        self.assertEqual(emails[0].source_page_title, "Official information")

    def test_selects_high_value_same_site_links(self):
        html = """
        <a href="/contact-us">Contact us</a>
        <a href="https://example.govt.nz/oia">OIA</a>
        <a href="https://facebook.com/example">Facebook</a>
        <a href="/careers">Careers</a>
        <a href="/reports/annual-report.pdf">Annual report</a>
        """

        links = find_candidate_links(html, "https://example.govt.nz")

        self.assertEqual(
            [link.url for link in links],
            ["https://example.govt.nz/contact-us", "https://example.govt.nz/oia"],
        )

    def test_scores_oia_candidate_with_explainable_reasons(self):
        score = score_email(
            "oia@example.govt.nz",
            source_url="https://example.govt.nz/official-information",
            source_page_title="Official information requests",
            source_snippet="Email oia@example.govt.nz to make an OIA request.",
            home_page_url="https://example.govt.nz",
            discovery_method="linked_page",
        )

        self.assertGreaterEqual(score.confidence, 80)
        self.assertIn("strong local part", score.reason)
        self.assertIn("source URL", score.reason)

    def test_builds_candidate_upsert_sql_and_review_status_update(self):
        agency = Agency(
            id="agy_1",
            name="Example Agency",
            home_page_url="https://example.govt.nz",
            source_url="https://fyi.org.nz/body/example",
            contact_status="missing",
        )
        candidates = discover_page_emails(
            '<a href="mailto:oia@example.govt.nz">OIA</a>',
            source_url="https://example.govt.nz/contact",
            discovery_method="homepage",
        )

        generated = build_scrape_sql({agency.id: candidates})

        self.assertIn("INSERT INTO sunlight_agency_contact_candidates", generated)
        self.assertIn(candidate_id("agy_1", "oia@example.govt.nz", "https://example.govt.nz/contact"), generated)
        self.assertIn("ON CONFLICT(agency_id, normalized_email, source_url) DO UPDATE", generated)
        self.assertIn("contact_status = 'needs_review'", generated)
        self.assertNotIn("primary_request_email", generated)


if __name__ == "__main__":
    unittest.main()
