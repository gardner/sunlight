import unittest

from scripts.scrape_authority_contacts import (
    Authority,
    build_scrape_sql,
    candidate_id,
    discover_page_emails,
    EmailCandidate,
    fetch_authority_pages,
    find_candidate_links,
    normalize_email,
    score_email,
)


class AuthorityContactScraperTests(unittest.TestCase):
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

        pages = fetch_authority_pages(
            Authority(
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

    def test_probes_common_contact_paths_before_noisy_oia_links(self):
        session = FakeSession(
            {
                "https://example.govt.nz/": """
                  <a href="/news/latest-oia-statistics-released">Latest OIA statistics</a>
                """,
                "https://example.govt.nz/contact-us": """
                  <a href="mailto:enquiries@example.govt.nz">Contact us</a>
                """,
                "https://example.govt.nz/official-information-act-requests": """
                  Email enquiries@example.govt.nz for Official Information Act requests.
                """,
            },
        )

        pages = fetch_authority_pages(
            Authority(
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

    def test_uses_fyi_source_when_homepage_is_missing(self):
        session = FakeSession(
            {
                "https://fyi.org.nz/body/example": """
                  Official information requests can be sent to oia@example.govt.nz.
                """,
            },
        )

        pages = fetch_authority_pages(
            Authority(
                id="agy_1",
                name="Example",
                home_page_url=None,
                source_url="https://fyi.org.nz/body/example",
                contact_status="missing",
            ),
            session=session,
            timeout=20,
            max_pages=2,
        )

        self.assertEqual(pages, [(session.pages["https://fyi.org.nz/body/example"], "https://fyi.org.nz/body/example", "fyi_page")])

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

    def test_scores_school_office_address_on_contact_page(self):
        score = score_email(
            "office@example.school.nz",
            source_url="https://example.school.nz/contact-us",
            source_page_title="Contact us",
            source_snippet="office@example.school.nz",
            home_page_url="https://example.school.nz",
            discovery_method="linked_page",
        )

        self.assertGreaterEqual(score.confidence, 50)
        self.assertIn("medium local part", score.reason)

    def test_penalizes_external_domains_found_on_authority_pages(self):
        score = score_email(
            "info@ombudsman.parliament.nz",
            source_url="https://acc.co.nz/contact/official-information-act-requests",
            source_page_title="Official information requests",
            source_snippet="Contact the Ombudsman at info@ombudsman.parliament.nz",
            home_page_url="https://acc.co.nz",
            discovery_method="linked_page",
        )

        self.assertLess(score.confidence, 50)
        self.assertIn("email domain differs", score.reason)

    def test_builds_candidate_upsert_sql_and_review_status_update(self):
        authority = Authority(
            id="agy_1",
            name="Example Authority",
            home_page_url="https://example.govt.nz",
            source_url="https://fyi.org.nz/body/example",
            contact_status="missing",
        )
        candidates = discover_page_emails(
            '<a href="mailto:oia@example.govt.nz">OIA</a>',
            source_url="https://example.govt.nz/contact",
            discovery_method="homepage",
        )

        generated = build_scrape_sql({authority.id: candidates})

        self.assertIn("INSERT INTO sunlight_authority_contact_candidates", generated)
        self.assertIn(candidate_id("agy_1", "oia@example.govt.nz", "https://example.govt.nz/contact"), generated)
        self.assertIn("ON CONFLICT(authority_id, normalized_email, source_url) DO UPDATE", generated)
        self.assertIn("contact_status = 'needs_review'", generated)
        self.assertIn("sunlight_authority_contact_scrape_attempts", generated)
        self.assertIn("'needs_review'", generated)
        self.assertNotIn("primary_request_email", generated)

    def test_records_no_candidate_attempts(self):
        generated = build_scrape_sql({"auth_1": []})

        self.assertIn("sunlight_authority_contact_scrape_attempts", generated)
        self.assertIn("'no_candidate'", generated)
        self.assertNotIn("sunlight_authority_contact_candidates", generated)

    def test_auto_verifies_one_clear_candidate(self):
        candidate = EmailCandidate(
            email="oia@example.govt.nz",
            normalized_email="oia@example.govt.nz",
            source_url="https://example.govt.nz/oia",
            source_page_title="Official information requests",
            source_snippet="Email oia@example.govt.nz",
            discovery_method="linked_page",
            confidence=85,
            confidence_reason="strong local part",
        )

        generated = build_scrape_sql({"auth_1": [candidate]})

        self.assertIn("'accepted'", generated)
        self.assertIn("primary_request_email = 'oia@example.govt.nz'", generated)
        self.assertIn("contact_status = 'verified'", generated)
        self.assertIn("authority.contact_auto_verified", generated)
        self.assertIn("'auto_verified'", generated)
        self.assertNotIn("contact_status = 'needs_review'", generated)

    def test_keeps_ambiguous_candidates_for_review(self):
        candidates = [
            EmailCandidate(
                email="info@example.govt.nz",
                normalized_email="info@example.govt.nz",
                source_url="https://example.govt.nz/contact",
                source_page_title="Contact",
                source_snippet="info@example.govt.nz",
                discovery_method="linked_page",
                confidence=65,
                confidence_reason="medium local part",
            ),
            EmailCandidate(
                email="enquiries@example.govt.nz",
                normalized_email="enquiries@example.govt.nz",
                source_url="https://example.govt.nz/contact",
                source_page_title="Contact",
                source_snippet="enquiries@example.govt.nz",
                discovery_method="linked_page",
                confidence=60,
                confidence_reason="medium local part",
            ),
        ]

        generated = build_scrape_sql({"auth_1": candidates})

        self.assertIn("contact_status = 'needs_review'", generated)
        self.assertNotIn("contact_status = 'verified'", generated)


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": "text/html"}


class FakeSession:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **_kwargs):
        if url not in self.pages:
            return FakeResponse("", status_code=404)
        return FakeResponse(self.pages[url])


if __name__ == "__main__":
    unittest.main()
