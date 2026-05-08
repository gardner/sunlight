import unittest

from scripts.scrape_agency_contacts import (
    Agency,
    build_scrape_sql,
    candidate_id,
    discover_page_emails,
    fetch_agency_pages,
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
        self.assertIsNone(normalize_email("privacy@example.govt.nz"))
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
            ["info@example.govt.nz", "oia@example.govt.nz"],
        )
        self.assertEqual(emails[0].source_page_title, "Official information")

    def test_prioritizes_oia_links_over_generic_same_site_links(self):
        html = """
        <a href="/about">About</a>
        <a href="/contact-us">Contact us</a>
        <a href="https://example.govt.nz/oia">OIA</a>
        <a href="https://facebook.com/example">Facebook</a>
        <a href="/careers">Careers</a>
        <a href="/reports/annual-report.pdf">Annual report</a>
        """

        links = find_candidate_links(html, "https://example.govt.nz")

        self.assertEqual(
            [link.url for link in links],
            [
                "https://example.govt.nz/oia",
                "https://example.govt.nz/contact-us",
            ],
        )

    def test_fetches_links_discovered_from_linked_pages_within_page_cap(self):
        session = FakeSession(
            {
                "https://example.govt.nz/": """
                  <a href="/about">About</a>
                  <a href="/contact-us">Contact us</a>
                """,
                "https://example.govt.nz/contact-us": """
                  <a href="/official-information-act-requests">OIA requests</a>
                """,
                "https://example.govt.nz/official-information-act-requests": """
                  OIA email: oia@example.govt.nz
                """,
            },
        )

        pages = fetch_agency_pages(
            Agency(
                id="agy_1",
                name="Example",
                home_page_url="https://example.govt.nz/",
                source_url=None,
                contact_status="missing",
            ),
            session=session,
            timeout=20,
            max_pages=3,
        )

        self.assertEqual(
            [page[1] for page in pages],
            [
                "https://example.govt.nz/",
                "https://example.govt.nz/contact-us",
                "https://example.govt.nz/official-information-act-requests",
            ],
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

    def test_scores_official_information_as_role_address_not_person(self):
        score = score_email(
            "official.information@wcc.govt.nz",
            source_url="https://wellington.govt.nz/contact-us/information-requests",
            source_page_title="Make an official information request",
            source_snippet="official.information@wcc.govt.nz",
            home_page_url="https://wellington.govt.nz",
            discovery_method="linked_page",
        )

        self.assertGreaterEqual(score.confidence, 70)
        self.assertNotIn("personal-looking", score.reason)

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


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.status_code = 200
        self.headers = {"content-type": "text/html"}


class FakeSession:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **_kwargs):
        return FakeResponse(self.pages[url])


if __name__ == "__main__":
    unittest.main()
