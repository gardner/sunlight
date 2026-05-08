from __future__ import annotations

import calendar
import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from string import Formatter
from typing import Any


class TemplateRenderError(ValueError):
    """Raised when a request template cannot be rendered."""


@dataclass(frozen=True)
class RequestCase:
    id: int
    agency_id: int
    cycle_id: int
    template_id: int
    reply_alias: str
    status: str
    expected_due_at: str | None
    sent_at: str | None
    closed_at: str | None


@dataclass(frozen=True)
class OutboundMessage:
    id: int
    request_case_id: int
    to_addresses: list[str]
    from_address: str
    subject: str
    body: str
    provider_message_id: str | None
    send_status: str
    sent_at: str | None


class RequestStore:
    def __init__(self, db: sqlite3.Connection, *, alias_domain: str):
        self.db = db
        self.alias_domain = alias_domain
        self.db.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self) -> None:
        self.db.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS request_templates (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                subject_template TEXT NOT NULL,
                body_template TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agencies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                legal_regime TEXT NOT NULL,
                request_email TEXT NOT NULL,
                secondary_emails TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'active',
                template_id INTEGER,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES request_templates(id)
            );

            CREATE TABLE IF NOT EXISTS request_cycles (
                id INTEGER PRIMARY KEY,
                month TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'draft',
                created_by TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT,
                sent_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS request_cases (
                id INTEGER PRIMARY KEY,
                agency_id INTEGER NOT NULL,
                cycle_id INTEGER NOT NULL,
                template_id INTEGER NOT NULL,
                reply_alias TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'scheduled',
                expected_due_at TEXT,
                sent_at TEXT,
                closed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (agency_id, cycle_id),
                FOREIGN KEY (agency_id) REFERENCES agencies(id),
                FOREIGN KEY (cycle_id) REFERENCES request_cycles(id),
                FOREIGN KEY (template_id) REFERENCES request_templates(id)
            );

            CREATE TABLE IF NOT EXISTS outbound_messages (
                id INTEGER PRIMARY KEY,
                request_case_id INTEGER NOT NULL UNIQUE,
                to_addresses TEXT NOT NULL,
                from_address TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                provider_message_id TEXT,
                send_status TEXT NOT NULL DEFAULT 'queued',
                sent_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (request_case_id) REFERENCES request_cases(id)
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def create_template(
        self,
        *,
        name: str,
        subject_template: str,
        body_template: str,
        status: str = "active",
    ) -> int:
        now = utcnow()
        cursor = self.db.execute(
            """
            INSERT INTO request_templates
                (name, subject_template, body_template, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, subject_template, body_template, status, now, now),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def create_agency(
        self,
        *,
        name: str,
        legal_regime: str,
        request_email: str,
        template_id: int | None,
        secondary_emails: list[str] | None = None,
        status: str = "active",
        notes: str = "",
    ) -> int:
        now = utcnow()
        cursor = self.db.execute(
            """
            INSERT INTO agencies
                (
                    name, slug, legal_regime, request_email, secondary_emails,
                    status, template_id, notes, created_at, updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                slugify(name),
                legal_regime,
                request_email,
                json.dumps(secondary_emails or []),
                status,
                template_id,
                notes,
                now,
                now,
            ),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def create_cycle(self, *, month: str, created_by: str) -> int:
        validate_month(month)
        now = utcnow()
        cursor = self.db.execute(
            """
            INSERT INTO request_cycles
                (month, status, created_by, created_at, updated_at)
            VALUES (?, 'draft', ?, ?, ?)
            """,
            (month, created_by, now, now),
        )
        cycle_id = int(cursor.lastrowid)
        self._audit(
            entity_type="request_cycle",
            entity_id=cycle_id,
            event_type="request_cycle_created",
            actor_type="operator",
            actor_id=created_by,
            metadata={"month": month},
        )
        self.db.commit()
        return cycle_id

    def preview_cycle(self, cycle_id: int) -> list[dict[str, Any]]:
        cycle = self._cycle(cycle_id)
        preview = []
        for agency in self._eligible_agencies():
            preview.append(
                {
                    "cycle_id": cycle_id,
                    "month": cycle["month"],
                    "agency_id": agency["id"],
                    "agency_name": agency["name"],
                    "legal_regime": agency["legal_regime"],
                    "request_email": agency["request_email"],
                    "template_id": agency["template_id"],
                }
            )
        return preview

    def approve_cycle(
        self,
        cycle_id: int,
        *,
        actor_id: str,
        from_address: str,
        reply_instructions: str,
        sunlight_contact_details: str,
        excluded_agency_ids: set[int] | None = None,
    ) -> list[RequestCase]:
        excluded_agency_ids = excluded_agency_ids or set()
        try:
            cycle = self._cycle(cycle_id)
            agencies = [
                agency
                for agency in self._eligible_agencies()
                if agency["id"] not in excluded_agency_ids
            ]
            now = utcnow()
            for agency in agencies:
                case = self._get_case_for_agency_cycle(agency["id"], cycle_id)
                if case is None:
                    if agency["template_id"] is None:
                        raise ValueError(f"Agency {agency['name']} has no template")
                    case = self._create_case(
                        agency_id=agency["id"],
                        cycle_id=cycle_id,
                        template_id=agency["template_id"],
                        cycle_month=cycle["month"],
                    )
                    self._audit(
                        entity_type="request_case",
                        entity_id=case.id,
                        event_type="request_case_created",
                        actor_type="operator",
                        actor_id=actor_id,
                        metadata={"agency_id": agency["id"], "cycle_id": cycle_id},
                    )
                if self._outbound_for_case(case.id) is None:
                    self._queue_outbound_message(
                        case=case,
                        agency=agency,
                        cycle_month=cycle["month"],
                        from_address=from_address,
                        reply_instructions=reply_instructions,
                        sunlight_contact_details=sunlight_contact_details,
                        actor_id=actor_id,
                    )

            self.db.execute(
                """
                UPDATE request_cycles
                SET status = 'approved', approved_by = ?, approved_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (actor_id, now, now, cycle_id),
            )
            self._audit(
                entity_type="request_cycle",
                entity_id=cycle_id,
                event_type="request_cycle_approved",
                actor_type="operator",
                actor_id=actor_id,
                metadata={"case_count": len(agencies)},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.cases_for_cycle(cycle_id)

    def cases_for_cycle(self, cycle_id: int) -> list[RequestCase]:
        rows = self.db.execute(
            """
            SELECT *
            FROM request_cases
            WHERE cycle_id = ?
            ORDER BY id
            """,
            (cycle_id,),
        ).fetchall()
        return [case_from_row(row) for row in rows]

    def outbound_messages_for_cycle(self, cycle_id: int) -> list[OutboundMessage]:
        rows = self.db.execute(
            """
            SELECT outbound_messages.*
            FROM outbound_messages
            JOIN request_cases ON request_cases.id = outbound_messages.request_case_id
            WHERE request_cases.cycle_id = ?
            ORDER BY outbound_messages.id
            """,
            (cycle_id,),
        ).fetchall()
        return [outbound_from_row(row) for row in rows]

    def audit_events(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT *
            FROM audit_events
            ORDER BY id
            """
        ).fetchall()
        return [
            {
                "id": row["id"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "event_type": row["event_type"],
                "actor_type": row["actor_type"],
                "actor_id": row["actor_id"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _create_case(
        self,
        *,
        agency_id: int,
        cycle_id: int,
        template_id: int,
        cycle_month: str,
    ) -> RequestCase:
        now = utcnow()
        expected_due_at = (datetime.fromisoformat(f"{cycle_month}-01") + timedelta(days=30)).date().isoformat()
        for _ in range(5):
            reply_alias = self._reply_alias(agency_id=agency_id, cycle_month=cycle_month)
            try:
                cursor = self.db.execute(
                    """
                    INSERT INTO request_cases
                        (
                            agency_id, cycle_id, template_id, reply_alias, status,
                            expected_due_at, created_at, updated_at
                        )
                    VALUES (?, ?, ?, ?, 'scheduled', ?, ?, ?)
                    """,
                    (
                        agency_id,
                        cycle_id,
                        template_id,
                        reply_alias,
                        expected_due_at,
                        now,
                        now,
                    ),
                )
                case_id = int(cursor.lastrowid)
                return self._case(case_id)
            except sqlite3.IntegrityError as error:
                if "reply_alias" not in str(error):
                    raise
        raise RuntimeError("Could not generate a unique reply alias")

    def _queue_outbound_message(
        self,
        *,
        case: RequestCase,
        agency: sqlite3.Row,
        cycle_month: str,
        from_address: str,
        reply_instructions: str,
        sunlight_contact_details: str,
        actor_id: str,
    ) -> None:
        template = self._template(case.template_id)
        variables = template_variables(
            agency_name=agency["name"],
            cycle_month=cycle_month,
            reply_alias=case.reply_alias,
            reply_instructions=reply_instructions,
            sunlight_contact_details=sunlight_contact_details,
        )
        subject = render_template(template["subject_template"], variables)
        body = render_template(template["body_template"], variables)
        to_addresses = [agency["request_email"], *json.loads(agency["secondary_emails"])]
        now = utcnow()
        cursor = self.db.execute(
            """
            INSERT INTO outbound_messages
                (
                    request_case_id, to_addresses, from_address, subject, body,
                    send_status, created_at, updated_at
                )
            VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)
            """,
            (
                case.id,
                json.dumps(to_addresses),
                from_address,
                subject,
                body,
                now,
                now,
            ),
        )
        self._audit(
            entity_type="outbound_message",
            entity_id=int(cursor.lastrowid),
            event_type="outbound_message_queued",
            actor_type="system",
            actor_id=actor_id,
            metadata={"request_case_id": case.id},
        )

    def _reply_alias(self, *, agency_id: int, cycle_month: str) -> str:
        agency = self._agency(agency_id)
        token = secrets.token_hex(6)
        return f"requests+{cycle_month}-{agency['slug']}-{token}@{self.alias_domain}"

    def _eligible_agencies(self) -> list[sqlite3.Row]:
        return self.db.execute(
            """
            SELECT *
            FROM agencies
            WHERE status = 'active'
            ORDER BY name
            """
        ).fetchall()

    def _cycle(self, cycle_id: int) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM request_cycles WHERE id = ?", (cycle_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown request cycle id {cycle_id}")
        return row

    def _agency(self, agency_id: int) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM agencies WHERE id = ?", (agency_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown agency id {agency_id}")
        return row

    def _template(self, template_id: int) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM request_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown template id {template_id}")
        return row

    def _case(self, case_id: int) -> RequestCase:
        row = self.db.execute("SELECT * FROM request_cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown request case id {case_id}")
        return case_from_row(row)

    def _get_case_for_agency_cycle(self, agency_id: int, cycle_id: int) -> RequestCase | None:
        row = self.db.execute(
            """
            SELECT *
            FROM request_cases
            WHERE agency_id = ? AND cycle_id = ?
            """,
            (agency_id, cycle_id),
        ).fetchone()
        return case_from_row(row) if row is not None else None

    def _outbound_for_case(self, case_id: int) -> OutboundMessage | None:
        row = self.db.execute(
            "SELECT * FROM outbound_messages WHERE request_case_id = ?",
            (case_id,),
        ).fetchone()
        return outbound_from_row(row) if row is not None else None

    def _audit(
        self,
        *,
        entity_type: str,
        entity_id: int,
        event_type: str,
        actor_type: str,
        actor_id: str,
        metadata: dict[str, Any],
    ) -> None:
        self.db.execute(
            """
            INSERT INTO audit_events
                (entity_type, entity_id, event_type, actor_type, actor_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                event_type,
                actor_type,
                actor_id,
                json.dumps(metadata, sort_keys=True),
                utcnow(),
            ),
        )


def render_template(template: str, variables: dict[str, str]) -> str:
    fields = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name is not None and field_name != ""
    }
    missing = fields - variables.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise TemplateRenderError(f"Template references unavailable variable(s): {names}")
    return template.format_map(variables)


def template_variables(
    *,
    agency_name: str,
    cycle_month: str,
    reply_alias: str,
    reply_instructions: str,
    sunlight_contact_details: str,
) -> dict[str, str]:
    year, month = (int(part) for part in cycle_month.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return {
        "agency_name": agency_name,
        "request_month": f"{calendar.month_name[month]} {year}",
        "date_range_covered": f"{year}-{month:02d}-01 to {year}-{month:02d}-{last_day:02d}",
        "reply_alias": reply_alias,
        "reply_instructions": reply_instructions,
        "sunlight_contact_details": sunlight_contact_details,
    }


def validate_month(month: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("Month must use YYYY-MM format")
    year, month_number = (int(part) for part in month.split("-"))
    if year < 2000 or not 1 <= month_number <= 12:
        raise ValueError("Month must contain a valid year and month")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "agency"


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def case_from_row(row: sqlite3.Row) -> RequestCase:
    return RequestCase(
        id=row["id"],
        agency_id=row["agency_id"],
        cycle_id=row["cycle_id"],
        template_id=row["template_id"],
        reply_alias=row["reply_alias"],
        status=row["status"],
        expected_due_at=row["expected_due_at"],
        sent_at=row["sent_at"],
        closed_at=row["closed_at"],
    )


def outbound_from_row(row: sqlite3.Row) -> OutboundMessage:
    return OutboundMessage(
        id=row["id"],
        request_case_id=row["request_case_id"],
        to_addresses=json.loads(row["to_addresses"]),
        from_address=row["from_address"],
        subject=row["subject"],
        body=row["body"],
        provider_message_id=row["provider_message_id"],
        send_status=row["send_status"],
        sent_at=row["sent_at"],
    )
