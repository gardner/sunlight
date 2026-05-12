import { describe, expect, it } from "vitest";
import {
  buildCompleteMultipartUploadXml,
  buildR2ObjectKey,
  buildResponseSubmission,
  buildUploadRequest,
  parseInitiateMultipartUploadResponse,
  requiresMultipartUpload,
  sanitizeFilename,
} from "./response-intake";

describe("buildResponseSubmission", () => {
  it("trims optional authority metadata", () => {
    expect(
      buildResponseSubmission({
        authorityReference: "  OIA-2026-10  ",
        category: "full_response",
        notes: "  Attached documents  ",
        submitterEmail: "  records@example.govt.nz  ",
        submitterName: "  Records Team  ",
      }),
    ).toEqual({
      authorityReference: "OIA-2026-10",
      category: "full_response",
      notes: "Attached documents",
      submitterEmail: "records@example.govt.nz",
      submitterName: "Records Team",
    });
  });

  it("rejects unsupported categories", () => {
    expect(() =>
      buildResponseSubmission({
        category: "not_a_real_category",
      }),
    ).toThrow("Unsupported response category");
  });
});

describe("upload request helpers", () => {
  it("creates isolated R2 object keys", () => {
    expect(
      buildR2ObjectKey({
        originalFilename: "Final response.pdf",
        requestId: "srq_123",
        uploadId: "upl_456",
      }),
    ).toBe("sunlight-requests/srq_123/uploads/upl_456/final-response.pdf");
  });

  it("sanitizes unsafe filenames", () => {
    expect(sanitizeFilename("../../Cabinet papers (final).PDF")).toBe(
      "cabinet-papers-final.pdf",
    );
    expect(sanitizeFilename("")).toBe("upload.bin");
  });

  it("validates browser upload metadata", () => {
    expect(
      buildUploadRequest({
        contentType: "application/pdf",
        filename: "bundle.pdf",
        sizeBytes: 1024,
      }),
    ).toEqual({
      contentType: "application/pdf",
      originalFilename: "bundle.pdf",
      sizeBytes: 1024,
    });
  });

  it("rejects empty or oversized uploads", () => {
    expect(() =>
      buildUploadRequest({
        filename: "empty.pdf",
        sizeBytes: 0,
      }),
    ).toThrow("empty");
    expect(() =>
      buildUploadRequest({
        filename: "huge.zip",
        sizeBytes: 6 * 1024 * 1024 * 1024 * 1024, // 6TB
      }),
    ).toThrow("larger than");
  });
});

describe("multipart upload helpers", () => {
  it("parses the XML response from InitiateMultipartUpload", () => {
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<InitiateMultipartUploadResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Bucket>example-bucket</Bucket>
  <Key>example-object</Key>
  <UploadId>VXBsb2FkIElEIGZvciA2aWWpbmcncyBteS1tdWx0aXBhcnQtdXBsb2Fk</UploadId>
</InitiateMultipartUploadResult>`;
    expect(parseInitiateMultipartUploadResponse(xml)).toBe("VXBsb2FkIElEIGZvciA2aWWpbmcncyBteS1tdWx0aXBhcnQtdXBsb2Fk");
  });

  it("builds the XML payload for CompleteMultipartUpload", () => {
    const parts = [
      { partNumber: 1, etag: '"a54357aff0632cce46d942af68356b38"' },
      { partNumber: 2, etag: '"0c78aef83f66abc1fa1e8477f296d394"' }
    ];
    const expected = `<CompleteMultipartUpload><Part><PartNumber>1</PartNumber><ETag>"a54357aff0632cce46d942af68356b38"</ETag></Part><Part><PartNumber>2</PartNumber><ETag>"0c78aef83f66abc1fa1e8477f296d394"</ETag></Part></CompleteMultipartUpload>`;
    expect(buildCompleteMultipartUploadXml(parts)).toBe(expected);
  });

  it("identifies if a file size requires multipart upload", () => {
    const CHUNK_SIZE = 5 * 1024 * 1024;
    expect(requiresMultipartUpload(CHUNK_SIZE - 1)).toBe(false);
    expect(requiresMultipartUpload(CHUNK_SIZE * 5)).toBe(true);
  });
});
