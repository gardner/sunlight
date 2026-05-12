"use client";

import { useState } from "react";

interface UploadPanelProps {
  caseToken: string;
}

interface UploadRow {
  error?: string;
  name: string;
  file: File;
  status: "ready" | "uploading" | "uploaded" | "failed";
}

interface UploadSessionResponse {
  headers: Record<string, string>;
  method: "PUT";
  uploadId: string;
  uploadUrl: string;
  multipart?: {
    uploadId: string;
    partCount: number;
    partUrls: string[];
  };
}

export function UploadPanel({ caseToken }: UploadPanelProps) {
  const [rows, setRows] = useState<UploadRow[]>([]);

  async function uploadFiles(files: FileList | null) {
    if (!files) return;

    const newFiles = Array.from(files).map((file) => ({
      name: file.name,
      file,
      status: "ready" as const,
    }));
    
    setRows((current) => [...current, ...newFiles]);

    for (const newFile of newFiles) {
      void processUpload(newFile);
    }
  }

  async function processUpload(rowToUpload: UploadRow) {
    setRows((current) => updateRowByName(current, rowToUpload.name, { status: "uploading", error: undefined }));
    try {
      await uploadOneFile(caseToken, rowToUpload.file);
      setRows((current) => updateRowByName(current, rowToUpload.name, { status: "uploaded" }));
    } catch (error) {
      setRows((current) =>
        updateRowByName(current, rowToUpload.name, {
          error: error instanceof Error ? error.message : String(error),
          status: "failed",
        }),
      );
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
              <div className="flex justify-between w-full">
                <span>{row.name}</span>
                <div className="flex gap-4">
                  <strong>{row.status}</strong>
                  {row.status === "failed" && (
                     <button type="button" onClick={() => void processUpload(row)} className="text-blue-500 hover:underline">Retry</button>
                  )}
                  {row.status !== "uploading" && (
                     <button type="button" onClick={() => setRows(curr => curr.filter(r => r.name !== row.name))} className="text-red-500 hover:underline">Remove</button>
                  )}
                </div>
              </div>
              {row.error ? <small className="text-red-500 block">{row.error}</small> : null}
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
  
  if (session.multipart) {
    const CHUNK_SIZE = 5 * 1024 * 1024;
    const parts: { partNumber: number; etag: string }[] = [];
    
    for (let i = 0; i < session.multipart.partCount; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);
      const partUrl = session.multipart.partUrls[i];
      
      const partResponse = await fetch(partUrl, {
        method: "PUT",
        headers: session.headers,
        body: chunk
      });
      
      if (!partResponse.ok) {
        throw new Error(`R2 upload failed at part ${i + 1} with ${partResponse.status}`);
      }
      
      const etag = partResponse.headers.get("ETag");
      if (!etag) throw new Error("Missing ETag from part upload");
      
      parts.push({ partNumber: i + 1, etag });
    }

    const completeResponse = await fetch(
      `/response/${caseToken}/uploads/${session.uploadId}/complete`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parts, multipartUploadId: session.multipart.uploadId })
      },
    );

    if (!completeResponse.ok) {
      throw new Error(await completeResponse.text());
    }

  } else {
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
}

function updateRowByName(rows: UploadRow[], name: string, update: Partial<UploadRow>): UploadRow[] {
  return rows.map((row) => (row.name === name ? { ...row, ...update } : row));
}
