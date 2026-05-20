from __future__ import annotations

from pathlib import Path


class LanceDBChunkWriter:
    def __init__(self, persist_dir: Path, table_name: str = "chunks"):
        self.persist_dir = persist_dir
        self.table_name = table_name
        self._db = None
        self._table = None

    def _connect(self):
        if self._db is None:
            import lancedb

            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.persist_dir))
        return self._db

    def _schema(self, dimension: int):
        import pyarrow as pa

        return pa.schema(
            [
                pa.field("chunk_id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dimension)),
                pa.field("document_id", pa.string()),
                pa.field("chunk_index", pa.int32()),
                pa.field("chunk_text", pa.string()),
                pa.field("text_preview", pa.string()),
                pa.field("source", pa.string()),
                pa.field("source_type", pa.string()),
                pa.field("retrieval_view", pa.string()),
                pa.field("canonical_document_id", pa.string()),
                pa.field("generated", pa.bool_()),
                pa.field("authority_name", pa.string()),
                pa.field("authority_slug", pa.string()),
                pa.field("authority_category", pa.string()),
                pa.field("request_title", pa.string()),
                pa.field("request_year", pa.int64()),
                pa.field("source_url", pa.string()),
                pa.field("source_page_url", pa.string()),
                pa.field("request_url", pa.string()),
                pa.field("fyi_request_id", pa.int64()),
                pa.field("fyi_response_id", pa.int64()),
                pa.field("fyi_attachment_id", pa.int64()),
                pa.field("tenancy_order_id", pa.string()),
                pa.field("tenancy_application_number", pa.string()),
                pa.field("nztt_citation", pa.string()),
                pa.field("decision_date", pa.string()),
                pa.field("published_date", pa.string()),
                pa.field("legal_issue_tags", pa.string()),
                pa.field("statute_sections", pa.string()),
                pa.field("suppression_status", pa.string()),
                pa.field("original_filename", pa.string()),
                pa.field("pdf_r2_key", pa.string()),
                pa.field("markdown_r2_key", pa.string()),
                pa.field("markdown_path", pa.string()),
                pa.field("embedding_model", pa.string()),
                pa.field("text_sha256", pa.string()),
                pa.field("created_at", pa.string()),
                pa.field("vectorize_uploaded_at", pa.string()),
            ]
        )

    def add_records(self, records: list[dict[str, object]]) -> None:
        if not records:
            return

        import pyarrow as pa

        batch = pa.Table.from_pylist(records, schema=self._schema(len(records[0]["vector"])))
        if self._table is None:
            db = self._connect()
            try:
                self._table = db.open_table(self.table_name)
            except Exception:
                self._table = db.create_table(
                    self.table_name,
                    data=batch,
                    schema=batch.schema,
                    mode="create",
                )
                return

        self._table.merge_insert("chunk_id").when_not_matched_insert_all().execute(batch)
