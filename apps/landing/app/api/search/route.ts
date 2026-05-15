import { env } from "cloudflare:workers";
import {
  type Bm25SearchRow,
  SearchInputError,
  buildAnswerPrompt,
  buildFtsMatchQuery,
  buildRerankContexts,
  coerceEmbeddingVector,
  extractAnswerText,
  fuseSearchCandidates,
  mapBm25RowToCitation,
  mapVectorizeMatchToCitation,
  normalizeSearchQuestion,
  rerankCitations,
} from "../../../lib/search";

const EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b";
const ANSWER_MODEL = "@cf/google/gemma-4-26b-a4b-it";
const RERANK_MODEL = "@cf/baai/bge-reranker-base" as string;
const VECTORIZE_CANDIDATE_COUNT = 50;
const BM25_CANDIDATE_COUNT = 50;
const RERANK_CANDIDATE_COUNT = 20;
const DEFAULT_RESULT_COUNT = 5;
const MAX_RESULT_COUNT = 10;

export async function POST(request: Request) {
  try {
    const body = await readJsonBody(request);
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
      RERANK_CANDIDATE_COUNT,
    );

    if (fusedCandidates.length === 0) {
      return jsonResponse({
        answer:
          "I could not find a strong matching record in the current Sunlight search index.",
        citations: [],
        question,
      });
    }

    const rerankResult = await timeAsync(
      async () => rerankSearchCandidates(question, fusedCandidates, resultCount),
    );
    const citations = rerankResult.value;
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
      fused_candidates: fusedCandidates.length,
      rerank_ms: rerankResult.durationMs,
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

async function readJsonBody(request: Request): Promise<Record<string, unknown>> {
  try {
    const value = await request.json();
    return isRecord(value) ? value : {};
  } catch {
    return {};
  }
}

function normalizeResultCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_RESULT_COUNT;
  }
  return Math.min(MAX_RESULT_COUNT, Math.max(1, Math.floor(value)));
}

async function rerankSearchCandidates(
  question: string,
  candidates: ReturnType<typeof mapVectorizeMatchToCitation>[],
  resultCount: number,
) {
  try {
    const rerankResult = await env.AI.run(RERANK_MODEL, {
      contexts: buildRerankContexts(candidates),
      query: question,
      top_k: Math.min(resultCount, candidates.length),
    });

    return rerankCitations(candidates, rerankResult, resultCount);
  } catch (error) {
    console.warn("Sunlight search reranker failed; falling back to Vectorize order", error);
    return rerankCitations(candidates, undefined, resultCount);
  }
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

function jsonResponse(body: unknown, status = 200): Response {
  return Response.json(body, {
    headers: {
      "cache-control": "no-store",
    },
    status,
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
