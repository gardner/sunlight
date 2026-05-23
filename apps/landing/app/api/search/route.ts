import { env } from "cloudflare:workers";
import {
  type Bm25SearchRow,
  type SearchProgressStage,
  type SearchResponsePayload,
  SearchInputError,
  buildAnswerPrompt,
  buildFtsMatchQuery,
  coerceEmbeddingVector,
  encodeSearchStreamEvent,
  extractAnswerText,
  fuseSearchCandidates,
  mapBm25RowToCitation,
  mapVectorizeMatchToCitation,
  normalizeSearchQuestion,
  selectFinalCitations,
} from "../../../lib/search";
import {
  SearchRequestError,
  assertContentLength,
  assertSupportedContentType,
  checkSearchRateLimit,
  readLimitedSearchJsonBody,
} from "../../../lib/search-security";

const EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b";
const ANSWER_MODEL = "@cf/google/gemma-4-26b-a4b-it";
const VECTORIZE_CANDIDATE_COUNT = 50;
const BM25_CANDIDATE_COUNT = 50;
const BM25_SNIPPET_CHARS = 2400;
const FUSED_CANDIDATE_COUNT = 20;
const DEFAULT_RESULT_COUNT = 5;
const MAX_RESULT_COUNT = 10;

type SearchStageEmitter = (stage: SearchProgressStage) => void;

export async function POST(request: Request) {
  try {
    assertSupportedContentType(request);
    assertContentLength(request);

    const rateLimit = await checkSearchRateLimit(env.SEARCH_DB, request);
    if (!rateLimit.allowed) {
      console.warn("Sunlight search rate limited", {
        limit: rateLimit.limitName,
        retry_after_seconds: rateLimit.retryAfterSeconds,
      });
      return jsonResponse(
        {
          error: "Too many search requests. Please try again shortly.",
          retryAfterSeconds: rateLimit.retryAfterSeconds,
        },
        429,
        {
          "retry-after": String(rateLimit.retryAfterSeconds ?? 60),
        },
      );
    }

    const body = await readLimitedSearchJsonBody(request);
    const question = normalizeSearchQuestion(body.question ?? body.query ?? body.message);
    const resultCount = normalizeResultCount(body.topK);

    if (wantsSearchStream(body)) {
      return streamSearchResponse(question, resultCount);
    }

    return jsonResponse(await runSearch(question, resultCount));
  } catch (error) {
    if (error instanceof SearchRequestError) {
      return jsonResponse({ error: error.message }, error.status);
    }

    if (error instanceof SearchInputError) {
      return jsonResponse({ error: error.message }, 400);
    }

    console.error("Sunlight search failed", error);
    return jsonResponse(
      {
        error:
          "Search is temporarily unavailable. Please try again in a moment.",
      },
      502,
    );
  }
}

async function runSearch(
  question: string,
  resultCount: number,
  emit?: SearchStageEmitter,
): Promise<SearchResponsePayload> {
  const startedAt = Date.now();
  const stages: SearchProgressStage[] = [];
  const recordStage = (stage: SearchProgressStage) => {
    const existingIndex = stages.findIndex((item) => item.id === stage.id);
    if (existingIndex >= 0) {
      stages[existingIndex] = stage;
    } else {
      stages.push(stage);
    }
    emit?.(stage);
  };

  recordStage({
    detail: "Matching exact names, numbers, titles, and source text in D1.",
    id: "bm25",
    label: "BM25 keyword search",
    status: "running",
  });
  const bm25Promise = timeAsync(async () => searchBm25Candidates(question, BM25_CANDIDATE_COUNT))
    .then((result) => {
      recordStage({
        count: result.value.length,
        detail: `${result.value.length} lexical candidates`,
        durationMs: result.durationMs,
        id: "bm25",
        label: "BM25 keyword search",
        status: "complete",
      });
      return result;
    });

  recordStage({
    detail: "Embedding the question for semantic retrieval.",
    id: "embedding",
    label: "Embed question",
    status: "running",
  });
  const embeddingResult = await timeAsync(() => env.AI.run(EMBEDDING_MODEL, {
    text: [question],
  }));
  recordStage({
    detail: "Query embedding ready",
    durationMs: embeddingResult.durationMs,
    id: "embedding",
    label: "Embed question",
    status: "complete",
  });

  const vector = coerceEmbeddingVector(embeddingResult.value);
  recordStage({
    detail: "Searching Vectorize for semantic neighbours.",
    id: "vector",
    label: "Vector search",
    status: "running",
  });
  const [matches, bm25Result] = await Promise.all([
    timeAsync(() => env.FYI_VECTORS.query(vector, {
      returnMetadata: "all",
      topK: VECTORIZE_CANDIDATE_COUNT,
    })),
    bm25Promise,
  ]);
  const candidates = matches.value.matches
    .map(mapVectorizeMatchToCitation)
    .filter((citation) => citation.snippet || citation.requestUrl || citation.sourceUrl);
  recordStage({
    count: candidates.length,
    detail: `${candidates.length} semantic candidates`,
    durationMs: matches.durationMs,
    id: "vector",
    label: "Vector search",
    status: "complete",
  });

  recordStage({
    detail: "Combining lexical and semantic ranks.",
    id: "fusion",
    label: "Hybrid fusion",
    status: "running",
  });
  const fusionStartedAt = Date.now();
  const bm25Candidates = bm25Result.value;
  const fusedCandidates = fuseSearchCandidates(
    candidates,
    bm25Candidates,
    FUSED_CANDIDATE_COUNT,
  );
  recordStage({
    count: fusedCandidates.length,
    detail: `${fusedCandidates.length} fused candidates`,
    durationMs: Date.now() - fusionStartedAt,
    id: "fusion",
    label: "Hybrid fusion",
    status: "complete",
  });

  if (fusedCandidates.length === 0) {
    return {
      answer:
        "I could not find a strong matching record in the current Sunlight search index.",
      citations: [],
      question,
      stages,
    };
  }

  recordStage({
    detail: "Choosing source-diverse evidence for the answer.",
    id: "selection",
    label: "Select citations",
    status: "running",
  });
  const citations = selectFinalCitations(
    fusedCandidates,
    candidates,
    bm25Candidates,
    resultCount,
  );
  recordStage({
    count: citations.length,
    detail: `${citations.length} citations selected`,
    id: "selection",
    label: "Select citations",
    status: "complete",
  });

  recordStage({
    detail: "Generating a grounded answer from selected evidence.",
    id: "answer",
    label: "Generate answer",
    status: "running",
  });
  const answerResult = await timeAsync(() => env.AI.run(ANSWER_MODEL, {
    max_completion_tokens: 1600,
    max_tokens: 1600,
    messages: [
      {
        role: "system",
        content:
          "You answer questions about New Zealand official information releases. Use only the supplied sources, keep answers concise, and cite factual claims with bracketed source numbers.",
      },
      {
        role: "user",
        content: buildAnswerPrompt(question, citations),
      },
    ],
    reasoning_effort: "low",
    temperature: 0.2,
  }));
  recordStage({
    detail: "Answer ready",
    durationMs: answerResult.durationMs,
    id: "answer",
    label: "Generate answer",
    status: "complete",
  });
  const answer = extractAnswerText(answerResult.value);

  console.log("Sunlight search timings", {
    answer_ms: answerResult.durationMs,
    bm25_candidates: bm25Candidates.length,
    bm25_ms: bm25Result.durationMs,
    final_selection: "source_diverse_fused",
    fused_candidates: fusedCandidates.length,
    total_ms: Date.now() - startedAt,
    vector_candidates: candidates.length,
    vector_ms: matches.durationMs,
  });

  return {
    answer:
      answer ||
      "I found matching records, but could not generate a reliable answer from them.",
    citations,
    question,
    stages,
  };
}

function streamSearchResponse(question: string, resultCount: number): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      let streamOpen = true;
      const write = (event: Parameters<typeof encodeSearchStreamEvent>[0]) => {
        if (!streamOpen) {
          return;
        }
        try {
          controller.enqueue(encoder.encode(encodeSearchStreamEvent(event)));
        } catch {
          streamOpen = false;
        }
      };

      try {
        const result = await runSearch(question, resultCount, (stage) => {
          write({ stage, type: "stage" });
        });
        write({ result, type: "result" });
      } catch (error) {
        console.error("Sunlight streaming search failed", error);
        write({
          error: "Search is temporarily unavailable. Please try again in a moment.",
          status: 502,
          type: "error",
        });
      } finally {
        if (streamOpen) {
          try {
            controller.close();
          } catch {
            // The browser may close the fetch stream before the Worker finishes.
          }
        }
      }
    }
  });

  return new Response(stream, {
    headers: {
      "cache-control": "no-store",
      "content-type": "application/x-ndjson; charset=utf-8",
      "x-content-type-options": "nosniff",
    },
  });
}

function wantsSearchStream(body: Record<string, unknown>): boolean {
  return body.stream === true || body.streamEvents === true;
}

function normalizeResultCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_RESULT_COUNT;
  }
  return Math.min(MAX_RESULT_COUNT, Math.max(1, Math.floor(value)));
}

async function searchBm25Candidates(question: string, limit: number) {
  const matchQuery = buildFtsMatchQuery(question);
  if (!matchQuery) {
    return [];
  }

  try {
    const result = await env.SEARCH_DB.prepare(`
      SELECT
        c.authority_category,
        c.authority_name,
        c.authority_slug,
        bm25(disclosed_chunks_fts, 0.0, 0.0, 2.0, 3.0, 1.0, 1.0) AS bm25_score,
        c.chunk_id,
        c.chunk_index,
        c.document_id,
        c.original_filename,
        c.request_title,
        c.request_url,
        c.request_year,
        c.source_url,
        substr(c.chunk_text, 1, ?) AS text_preview
      FROM disclosed_chunks_fts
      JOIN disclosed_chunks c ON c.chunk_id = disclosed_chunks_fts.chunk_id
      WHERE disclosed_chunks_fts MATCH ?
      ORDER BY bm25_score
      LIMIT ?
    `).bind(BM25_SNIPPET_CHARS, matchQuery, limit).all();

    return (result.results ?? [])
      .map((row, index) => mapBm25RowToCitation(row as Bm25SearchRow, index))
      .filter((citation) => citation.snippet || citation.requestUrl || citation.sourceUrl);
  } catch (error) {
    console.warn("Sunlight BM25 search failed; falling back to Vectorize-only retrieval", error);
    return [];
  }
}

async function timeAsync<T>(operation: () => Promise<T>): Promise<{ durationMs: number; value: T }> {
  const start = Date.now();
  const value = await operation();
  return {
    durationMs: Date.now() - start,
    value,
  };
}

function jsonResponse(body: unknown, status = 200, headers?: HeadersInit): Response {
  const responseHeaders = new Headers(headers);
  responseHeaders.set("cache-control", "no-store");

  return Response.json(body, {
    headers: responseHeaders,
    status,
  });
}
