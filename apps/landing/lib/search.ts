const MIN_QUESTION_LENGTH = 4;
const MAX_QUESTION_LENGTH = 700;
const MAX_FTS_TERMS = 12;
const FINAL_VECTOR_RESERVED = 1;
const FINAL_BM25_RESERVED = 2;
const VECTOR_WEIGHT = 0.55;
const BM25_WEIGHT = 0.45;
const RRF_K = 60;
const FTS_STOP_WORDS = new Set([
  "about",
  "after",
  "all",
  "also",
  "and",
  "any",
  "are",
  "been",
  "between",
  "but",
  "can",
  "could",
  "did",
  "does",
  "for",
  "from",
  "had",
  "has",
  "have",
  "how",
  "information",
  "into",
  "its",
  "near",
  "not",
  "official",
  "or",
  "please",
  "provide",
  "provided",
  "release",
  "released",
  "request",
  "requested",
  "show",
  "that",
  "the",
  "their",
  "there",
  "these",
  "this",
  "was",
  "were",
  "what",
  "when",
  "where",
  "which",
  "who",
  "why",
  "with",
  "would",
]);

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
  bm25Rank?: number;
  bm25Score?: number;
  fusedScore?: number;
  label: string;
  originalFilename?: string;
  requestUrl?: string;
  requestYear?: number;
  rerankScore?: number;
  score: number;
  snippet: string;
  sourceUrl?: string;
  title: string;
  vectorRank?: number;
  vectorScore?: number;
}

interface VectorizeLikeMatch {
  id?: string;
  metadata?: Record<string, unknown>;
  score?: number;
}

export interface Bm25SearchRow extends Record<string, unknown> {
  authority_category?: unknown;
  authority_name?: unknown;
  authority_slug?: unknown;
  bm25_score?: unknown;
  chunk_id?: unknown;
  chunk_index?: unknown;
  document_id?: unknown;
  original_filename?: unknown;
  request_title?: unknown;
  request_url?: unknown;
  request_year?: unknown;
  source_url?: unknown;
  text_preview?: unknown;
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
    vectorRank: index + 1,
    vectorScore: roundScore(typeof match.score === "number" ? match.score : 0),
  };
}

export function mapBm25RowToCitation(row: Bm25SearchRow, index: number): SearchCitation {
  const chunkId = readString(row, "chunk_id") ?? `bm25_match_${index + 1}`;
  const originalFilename = readString(row, "original_filename");
  const authorityName = readString(row, "authority_name");
  const documentId = readString(row, "document_id");
  const title =
    readString(row, "request_title") ??
    originalFilename ??
    (authorityName ? `${authorityName} disclosure` : undefined) ??
    documentId ??
    chunkId;

  return {
    authorityCategory: readString(row, "authority_category"),
    authorityName,
    authoritySlug: readString(row, "authority_slug"),
    bm25Rank: index + 1,
    bm25Score: roundScore(readNumber(row, "bm25_score") ?? 0),
    chunkId,
    chunkIndex: readNumber(row, "chunk_index"),
    documentId,
    label: `Source ${index + 1}`,
    originalFilename,
    requestUrl: readHttpUrl(row, "request_url"),
    requestYear: readNumber(row, "request_year"),
    score: 0,
    snippet: collapseWhitespace(readString(row, "text_preview") ?? ""),
    sourceUrl: readHttpUrl(row, "source_url"),
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

export function buildRerankContexts(citations: SearchCitation[]): { text: string }[] {
  return citations.map((citation) => {
    const parts = [
      `Title: ${citation.title}`,
      citation.authorityName ? `Authority: ${citation.authorityName}` : undefined,
      citation.requestYear ? `Request year: ${citation.requestYear}` : undefined,
      `Snippet: ${citation.snippet || "No preview available."}`,
    ].filter((part): part is string => Boolean(part));

    return { text: parts.join("\n") };
  });
}

export function rerankCitations(
  citations: SearchCitation[],
  rerankResult: unknown,
  topK: number,
): SearchCitation[] {
  const scored = parseRerankScores(rerankResult)
    .flatMap(({ index, score }) => {
      const citation = citations[index];
      if (!citation) {
        return [];
      }

      return [removeUndefinedValues({
        ...citation,
        rerankScore: roundScore(score),
        score: roundScore(score),
        vectorScore: citation.vectorScore,
      })];
    })
    .sort((left, right) => right.score - left.score);

  const ranked = scored.length > 0 ? scored : citations;
  return relabelCitations(ranked.slice(0, topK));
}

export function buildFtsMatchQuery(question: string): string {
  const terms = Array.from(question.toLocaleLowerCase("en-NZ").matchAll(/[\p{L}\p{N}_]+/gu))
    .map(([term]) => term)
    .filter((term) => term.length >= 2 && !FTS_STOP_WORDS.has(term));
  const uniqueTerms = Array.from(new Set(terms)).slice(0, MAX_FTS_TERMS);

  return uniqueTerms.map(quoteFtsTerm).join(" OR ");
}

export function fuseSearchCandidates(
  vectorCandidates: SearchCitation[],
  bm25Candidates: SearchCitation[],
  limit: number,
): SearchCitation[] {
  const candidates = new Map<string, SearchCitation>();

  vectorCandidates.forEach((candidate, index) => {
    upsertFusedCandidate(candidates, candidate, {
      fusedContribution: VECTOR_WEIGHT * reciprocalRank(index + 1),
      vectorRank: index + 1,
      vectorScore: candidate.vectorScore ?? candidate.score,
    });
  });

  bm25Candidates.forEach((candidate, index) => {
    upsertFusedCandidate(candidates, candidate, {
      bm25Rank: index + 1,
      bm25Score: candidate.bm25Score,
      fusedContribution: BM25_WEIGHT * reciprocalRank(index + 1),
    });
  });

  return relabelCitations(
    Array.from(candidates.values())
      .sort((left, right) => {
        const byScore = (right.fusedScore ?? 0) - (left.fusedScore ?? 0);
        return byScore || left.label.localeCompare(right.label);
      })
      .slice(0, limit),
  );
}

export function selectFinalCitations(
  fusedCandidates: SearchCitation[],
  vectorCandidates: SearchCitation[],
  bm25Candidates: SearchCitation[],
  topK: number,
): SearchCitation[] {
  if (topK <= 0) {
    return [];
  }
  if (topK < 3) {
    return relabelCitations(dedupeCitations(fusedCandidates).slice(0, topK));
  }

  const selected: SearchCitation[] = [];
  const seen = new Set<string>();
  addSelectedCitations(selected, seen, vectorCandidates, FINAL_VECTOR_RESERVED, topK);
  addSelectedCitations(
    selected,
    seen,
    bm25Candidates,
    Math.min(FINAL_BM25_RESERVED, topK - selected.length),
    topK,
  );
  addSelectedCitations(selected, seen, fusedCandidates, Number.POSITIVE_INFINITY, topK);

  return relabelCitations(selected);
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

function quoteFtsTerm(term: string): string {
  return `"${term.replaceAll('"', '""')}"`;
}

function dedupeCitations(citations: SearchCitation[]): SearchCitation[] {
  const selected: SearchCitation[] = [];
  const seen = new Set<string>();
  addSelectedCitations(selected, seen, citations, Number.POSITIVE_INFINITY, citations.length);
  return selected;
}

function addSelectedCitations(
  selected: SearchCitation[],
  seen: Set<string>,
  candidates: SearchCitation[],
  candidateLimit: number,
  totalLimit: number,
): void {
  let added = 0;
  for (const candidate of candidates) {
    if (selected.length >= totalLimit || added >= candidateLimit) {
      return;
    }
    const key = citationDedupeKey(candidate);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    selected.push(candidate);
    added += 1;
  }
}

function citationDedupeKey(citation: SearchCitation): string {
  return citation.documentId ?? citation.sourceUrl ?? citation.chunkId;
}

function reciprocalRank(rank: number): number {
  return 1 / (RRF_K + rank);
}

function upsertFusedCandidate(
  candidates: Map<string, SearchCitation>,
  candidate: SearchCitation,
  details: {
    bm25Rank?: number;
    bm25Score?: number;
    fusedContribution: number;
    vectorRank?: number;
    vectorScore?: number;
  },
) {
  const existing = candidates.get(candidate.chunkId);
  const currentFusedScore = existing?.fusedScore ?? 0;
  const fusedScore = currentFusedScore + details.fusedContribution;
  const merged = {
    ...candidate,
    ...existing,
    bm25Rank: existing?.bm25Rank ?? details.bm25Rank ?? candidate.bm25Rank,
    bm25Score: existing?.bm25Score ?? details.bm25Score ?? candidate.bm25Score,
    fusedScore: roundScore(fusedScore),
    score: roundScore(fusedScore),
    vectorRank: existing?.vectorRank ?? details.vectorRank ?? candidate.vectorRank,
    vectorScore: existing?.vectorScore ?? details.vectorScore ?? candidate.vectorScore,
  };

  candidates.set(candidate.chunkId, removeUndefinedValues(merged));
}

function removeUndefinedValues(citation: SearchCitation): SearchCitation {
  return Object.fromEntries(
    Object.entries(citation).filter(([, value]) => value !== undefined),
  ) as unknown as SearchCitation;
}

function parseRerankScores(value: unknown): { index: number; score: number }[] {
  if (!isRecord(value) || !Array.isArray(value.response)) {
    return [];
  }

  return value.response.flatMap((item) => {
    if (!isRecord(item)) {
      return [];
    }

    const index = readNumber(item, "id");
    const score = readNumber(item, "score");
    if (index === undefined || score === undefined) {
      return [];
    }

    return [{ index, score }];
  });
}

function relabelCitations(citations: SearchCitation[]): SearchCitation[] {
  return citations.map((citation, index) => ({
    ...citation,
    label: `Source ${index + 1}`,
  }));
}
