const MIN_QUESTION_LENGTH = 4;
const MAX_QUESTION_LENGTH = 700;

export class SearchInputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SearchInputError";
  }
}

export interface SearchCitation {
  authorityCategory?: string;
  authorityName?: string;
  authoritySlug?: string;
  chunkId: string;
  chunkIndex?: number;
  documentId?: string;
  label: string;
  originalFilename?: string;
  requestUrl?: string;
  requestYear?: number;
  score: number;
  snippet: string;
  sourceUrl?: string;
  title: string;
}

interface VectorizeLikeMatch {
  id?: string;
  metadata?: Record<string, unknown>;
  score?: number;
}

export function normalizeSearchQuestion(value: unknown): string {
  if (typeof value !== "string") {
    throw new SearchInputError("Ask a question as text.");
  }

  const question = collapseWhitespace(value);
  if (question.length < MIN_QUESTION_LENGTH) {
    throw new SearchInputError(
      `Search questions must be at least ${MIN_QUESTION_LENGTH} characters.`,
    );
  }
  if (question.length > MAX_QUESTION_LENGTH) {
    throw new SearchInputError(
      `Search questions must be ${MAX_QUESTION_LENGTH} characters or fewer.`,
    );
  }

  return question;
}

export function coerceEmbeddingVector(value: unknown): number[] {
  if (!isRecord(value) || !Array.isArray(value.data)) {
    throw new Error("Workers AI did not return an embedding vector.");
  }

  const [firstVector] = value.data;
  if (!Array.isArray(firstVector) || !firstVector.every((item) => typeof item === "number")) {
    throw new Error("Workers AI did not return an embedding vector.");
  }

  return firstVector;
}

export function mapVectorizeMatchToCitation(
  match: VectorizeLikeMatch,
  index: number,
): SearchCitation {
  const metadata = isRecord(match.metadata) ? match.metadata : {};
  const chunkId = readString(metadata, "chunk_id") ?? match.id ?? `match_${index + 1}`;
  const originalFilename = readString(metadata, "original_filename");
  const authorityName = readString(metadata, "authority_name");
  const documentId = readString(metadata, "document_id");
  const title =
    readString(metadata, "request_title") ??
    originalFilename ??
    (authorityName ? `${authorityName} disclosure` : undefined) ??
    documentId ??
    chunkId;

  return {
    authorityCategory: readString(metadata, "authority_category"),
    authorityName,
    authoritySlug: readString(metadata, "authority_slug"),
    chunkId,
    chunkIndex: readNumber(metadata, "chunk_index"),
    documentId,
    label: `Source ${index + 1}`,
    originalFilename,
    requestUrl: readHttpUrl(metadata, "request_url"),
    requestYear: readNumber(metadata, "request_year"),
    score: roundScore(typeof match.score === "number" ? match.score : 0),
    snippet: collapseWhitespace(readString(metadata, "text_preview") ?? ""),
    sourceUrl: readHttpUrl(metadata, "source_url"),
    title,
  };
}

export function buildAnswerPrompt(question: string, citations: SearchCitation[]): string {
  const sources = citations
    .map((citation, index) => {
      const authority = citation.authorityName ? `Authority: ${citation.authorityName}\n` : "";
      const requestUrl = citation.requestUrl ? `Request URL: ${citation.requestUrl}\n` : "";
      const sourceUrl = citation.sourceUrl ? `Attachment URL: ${citation.sourceUrl}\n` : "";
      return [
        `[${index + 1}] ${citation.title}`,
        authority,
        requestUrl,
        sourceUrl,
        `Snippet: ${citation.snippet || "No preview available."}`,
      ]
        .filter(Boolean)
        .join("\n");
    })
    .join("\n\n");

  return `Question: ${question}

Sources:
${sources}

Write a concise answer grounded only in the sources above. Cite claims with bracketed source numbers like [1]. If the sources are not enough to answer, say what the sources show and what remains unclear.`;
}

export function extractAnswerText(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (!isRecord(value)) {
    return "";
  }

  const direct = readString(value, "response") ?? readString(value, "answer") ?? readString(value, "output_text");
  if (direct) {
    return direct.trim();
  }

  if (isRecord(value.result)) {
    const resultText = extractAnswerText(value.result);
    if (resultText) {
      return resultText;
    }
  }

  if (Array.isArray(value.choices) && value.choices.length > 0) {
    const [firstChoice] = value.choices;
    if (isRecord(firstChoice)) {
      const messageText = extractMessageContent(firstChoice.message);
      if (messageText) {
        return messageText;
      }
      const text = readString(firstChoice, "text");
      if (text) {
        return text.trim();
      }
    }
  }

  return "";
}

function extractMessageContent(message: unknown): string {
  if (!isRecord(message)) {
    return "";
  }

  const content = message.content;
  if (typeof content === "string") {
    return content.trim();
  }
  if (!Array.isArray(content)) {
    return "";
  }

  return content
    .map((part) => {
      if (typeof part === "string") {
        return part;
      }
      if (!isRecord(part)) {
        return "";
      }
      return readString(part, "text") ?? "";
    })
    .filter(Boolean)
    .join("\n")
    .trim();
}

function collapseWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  if (typeof value === "string") {
    const trimmed = collapseWhitespace(value);
    return trimmed || undefined;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const joined = value
      .filter((item): item is string => typeof item === "string")
      .map(collapseWhitespace)
      .filter(Boolean)
      .join(", ");
    return joined || undefined;
  }
  return undefined;
}

function readNumber(record: Record<string, unknown>, key: string): number | undefined {
  const value = record[key];
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function readHttpUrl(record: Record<string, unknown>, key: string): string | undefined {
  const value = readString(record, key);
  if (!value) {
    return undefined;
  }

  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function roundScore(value: number): number {
  return Math.round(value * 1000) / 1000;
}
