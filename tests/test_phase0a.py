import sqlite3
import unittest

from sunlight_requests.core import RequestStore, TemplateRenderError


class Phase0ARequestIntakeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.store = RequestStore(self.db, alias_domain="reply.sunlight.test")
        self.template_id = self.store.create_template(
            name="Monthly disclosure",
            subject_template="OIA disclosure request for {authority_name} - {request_month}",
            body_template=(
                "Kia ora {authority_name},\n\n"
                "Please provide responses for {date_range_covered}.\n"
                "Reply to {reply_alias}.\n\n"
                "{sunlight_contact_details}"
            ),
        )

    def test_creates_cycle_cases_for_active_authorities(self):
        authority_id = self.store.create_authority(
            name="Ministry of Testing",
            legal_regime="OIA",
            request_email="oia@example.govt.nz",
            template_id=self.template_id,
        )
        self.store.create_authority(
            name="Dormant Council",
            legal_regime="LGOIMA",
            request_email="info@example.govt.nz",
            status="inactive",
            template_id=self.template_id,
        )
        cycle_id = self.store.create_cycle(month="2026-05", created_by="operator")

        cases = self.store.approve_cycle(
            cycle_id,
            actor_id="operator",
            from_address="requests@sunlight.test",
            reply_instructions="Reply directly to this email.",
            sunlight_contact_details="Sunlight Project",
        )

        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case.authority_id, authority_id)
        self.assertEqual(case.status, "scheduled")
        self.assertRegex(
            case.reply_alias,
            r"^requests\+2026-05-ministry-of-testing-[a-f0-9]{12}@reply\.sunlight\.test$",
        )

        outbound = self.store.outbound_messages_for_cycle(cycle_id)
        self.assertEqual(len(outbound), 1)
        self.assertEqual(outbound[0].to_addresses, ["oia@example.govt.nz"])
        self.assertIn("Ministry of Testing", outbound[0].subject)
        self.assertIn(case.reply_alias, outbound[0].body)
        self.assertEqual(outbound[0].send_status, "queued")

    def test_cycle_approval_is_idempotent_per_authority_and_cycle(self):
        self.store.create_authority(
            name="Repeatable Authority",
            legal_regime="OIA",
            request_email="oia@example.govt.nz",
            template_id=self.template_id,
        )
        cycle_id = self.store.create_cycle(month="2026-06", created_by="operator")

        first = self.store.approve_cycle(
            cycle_id,
            actor_id="operator",
            from_address="requests@sunlight.test",
            reply_instructions="Reply directly to this email.",
            sunlight_contact_details="Sunlight Project",
        )
        second = self.store.approve_cycle(
            cycle_id,
            actor_id="operator",
            from_address="requests@sunlight.test",
            reply_instructions="Reply directly to this email.",
            sunlight_contact_details="Sunlight Project",
        )

        self.assertEqual([case.id for case in second], [case.id for case in first])
        self.assertEqual(len(self.store.outbound_messages_for_cycle(cycle_id)), 1)

    def test_preview_does_not_create_cases_or_messages(self):
        self.store.create_authority(
            name="Preview Authority",
            legal_regime="OIA",
            request_email="oia@example.govt.nz",
            template_id=self.template_id,
        )
        cycle_id = self.store.create_cycle(month="2026-07", created_by="operator")

        preview = self.store.preview_cycle(cycle_id)

        self.assertEqual([item["authority_name"] for item in preview], ["Preview Authority"])
        self.assertEqual(self.store.cases_for_cycle(cycle_id), [])
        self.assertEqual(self.store.outbound_messages_for_cycle(cycle_id), [])

    def test_template_render_errors_name_missing_variables(self):
        bad_template_id = self.store.create_template(
            name="Bad",
            subject_template="Hello {authority_name}",
            body_template="Missing {not_available}",
        )
        self.store.create_authority(
            name="Broken Template Authority",
            legal_regime="OIA",
            request_email="oia@example.govt.nz",
            template_id=bad_template_id,
        )
        cycle_id = self.store.create_cycle(month="2026-08", created_by="operator")

        with self.assertRaisesRegex(TemplateRenderError, "not_available"):
            self.store.approve_cycle(
                cycle_id,
                actor_id="operator",
                from_address="requests@sunlight.test",
                reply_instructions="Reply directly to this email.",
                sunlight_contact_details="Sunlight Project",
            )

    def test_approval_writes_audit_events(self):
        self.store.create_authority(
            name="Audited Authority",
            legal_regime="OIA",
            request_email="oia@example.govt.nz",
            template_id=self.template_id,
        )
        cycle_id = self.store.create_cycle(month="2026-09", created_by="operator")

        self.store.approve_cycle(
            cycle_id,
            actor_id="operator",
            from_address="requests@sunlight.test",
            reply_instructions="Reply directly to this email.",
            sunlight_contact_details="Sunlight Project",
        )

        event_types = [event["event_type"] for event in self.store.audit_events()]
        self.assertIn("request_cycle_created", event_types)
        self.assertIn("request_case_created", event_types)
        self.assertIn("outbound_message_queued", event_types)
        self.assertIn("request_cycle_approved", event_types)


if __name__ == "__main__":
    unittest.main()
