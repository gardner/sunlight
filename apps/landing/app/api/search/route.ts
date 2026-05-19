import { env } from "cloudflare:workers";
import {
  type Bm25SearchRow,
  SearchInputError,
  buildAnswerPrompt,
  buildFtsMatchQuery,
  coerceEmbeddingVector,
  extractAnswerText,
  fuseSearchCandidates,
  mapBm25RowToCitation,
  mapVectorizeMatchToCitation,
  normalizeSearchQuestion,
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
const FUSED_CANDIDATE_COUNT = 20;
const DEFAULT_RESULT_COUNT = 5;
const MAX_RESULT_COUNT = 10;

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
    const startedAt = Date.now();

    const bm25Promise = timeAsync(async () => searchBm25Candidates(question, BM25_CANDIDATE_COUNT));

    const embedding = await env.AI.run(EMBEDDING_MODEL, {
      text: [question],
    });
    const vector = coerceEmbeddingVector(embedding);
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
    const bm25Candidates = bm25Result.value;
    const fusedCandidates = fuseSearchCandidates(
      candidates,
      bm25Candidates,
      FUSED_CANDIDATE_COUNT,
    );

    if (fusedCandidates.length === 0) {
      return jsonResponse({
        answer:
          "I could not find a strong matching record in the current Sunlight search index.",
        citations: [],
        question,
      });
    }

    const citations = fusedCandidates.slice(0, resultCount);
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
    const answer = extractAnswerText(answerResult.value);

    console.log("Sunlight search timings", {
      answer_ms: answerResult.durationMs,
      bm25_candidates: bm25Candidates.length,
      bm25_ms: bm25Result.durationMs,
      final_selection: "fused",
      fused_candidates: fusedCandidates.length,
      total_ms: Date.now() - startedAt,
      vector_candidates: candidates.length,
      vector_ms: matches.durationMs,
    });

    return jsonResponse({
      answer:
        answer ||
        "I found matching records, but could not generate a reliable answer from them.",
      citations,
      question,
    });
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
        c.text_preview
      FROM disclosed_chunks_fts
      JOIN disclosed_chunks c ON c.chunk_id = disclosed_chunks_fts.chunk_id
      WHERE disclosed_chunks_fts MATCH ?
      ORDER BY bm25_score
      LIMIT ?
    `).bind(matchQuery, limit).all();

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
