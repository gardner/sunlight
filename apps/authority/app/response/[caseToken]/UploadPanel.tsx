"use client";

import { useState } from "react";

interface UploadPanelProps {
  caseToken: string;
}

interface UploadRow {
  error?: string;
  name: string;
  status: "ready" | "uploading" | "uploaded" | "failed";
}

interface UploadSessionResponse {
  headers: Record<string, string>;
  method: "PUT";
  uploadId: string;
  uploadUrl: string;
}

export function UploadPanel({ caseToken }: UploadPanelProps) {
  const [rows, setRows] = useState<UploadRow[]>([]);

  async function uploadFiles(files: FileList | null) {
    if (!files) {
      return;
    }

    const nextRows = Array.from(files).map((file) => ({
      name: file.name,
      status: "ready" as const,
    }));
    setRows(nextRows);

    for (const [index, file] of Array.from(files).entries()) {
      setRows((current) => updateRow(current, index, { status: "uploading" }));
      try {
        await uploadOneFile(caseToken, file);
        setRows((current) => updateRow(current, index, { status: "uploaded" }));
      } catch (error) {
        setRows((current) =>
          updateRow(current, index, {
            error: error instanceof Error ? error.message : String(error),
            status: "failed",
          }),
        );
      }
    }
  }

  return (
    <section className="panel stack">
      <div>
        <p className="eyebrow">Large files</p>
        <h2>Upload response files</h2>
      </div>
      <label className="uploadBox">
        <input multiple onChange={(event) => void uploadFiles(event.target.files)} type="file" />
        <span>Select files to upload directly to Sunlight storage</span>
      </label>
      {rows.length > 0 ? (
        <ul className="uploadList">
          {rows.map((row) => (
            <li key={row.name}>
              <span>{row.name}</span>
              <strong>{row.status}</strong>
              {row.error ? <small>{row.error}</small> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

async function uploadOneFile(caseToken: string, file: File): Promise<void> {
  const sessionResponse = await fetch(`/response/${caseToken}/uploads`, {
    body: JSON.stringify({
      contentType: file.type,
      filename: file.name,
      sizeBytes: file.size,
    }),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });

  if (!sessionResponse.ok) {
    throw new Error(await sessionResponse.text());
  }

  const session = (await sessionResponse.json()) as UploadSessionResponse;
  const uploadResponse = await fetch(session.uploadUrl, {
    body: file,
    headers: session.headers,
    method: session.method,
  });

  if (!uploadResponse.ok) {
    throw new Error(`R2 upload failed with ${uploadResponse.status}`);
  }

  const completeResponse = await fetch(
    `/response/${caseToken}/uploads/${session.uploadId}/complete`,
    {
      method: "POST",
    },
  );

  if (!completeResponse.ok) {
    throw new Error(await completeResponse.text());
  }
}

function updateRow(rows: UploadRow[], index: number, update: Partial<UploadRow>): UploadRow[] {
  return rows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...update } : row));
}
