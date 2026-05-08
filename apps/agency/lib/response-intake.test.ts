import { describe, expect, it } from "vitest";
import {
  buildR2ObjectKey,
  buildResponseSubmission,
  buildUploadRequest,
  sanitizeFilename,
} from "./response-intake";

describe("buildResponseSubmission", () => {
  it("trims optional agency metadata", () => {
    expect(
      buildResponseSubmission({
        agencyReference: "  OIA-2026-10  ",
        category: "full_response",
        notes: "  Attached documents  ",
        submitterEmail: "  records@example.govt.nz  ",
        submitterName: "  Records Team  ",
      }),
    ).toEqual({
      agencyReference: "OIA-2026-10",
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
        sizeBytes: 6 * 1024 * 1024 * 1024,
      }),
    ).toThrow("larger than");
  });
});
