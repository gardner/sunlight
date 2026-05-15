import { env } from "cloudflare:workers";
import {
  SearchInputError,
  buildAnswerPrompt,
  buildRerankContexts,
  coerceEmbeddingVector,
  extractAnswerText,
  mapVectorizeMatchToCitation,
  normalizeSearchQuestion,
  rerankCitations,
} from "../../../lib/search";

const EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b";
const ANSWER_MODEL = "@cf/google/gemma-4-26b-a4b-it";
const RERANK_MODEL = "@cf/baai/bge-reranker-base" as string;
const VECTORIZE_CANDIDATE_COUNT = 20;
const DEFAULT_RESULT_COUNT = 5;
const MAX_RESULT_COUNT = 10;

export async function POST(request: Request) {
  try {
    const body = await readJsonBody(request);
    const question = normalizeSearchQuestion(body.question ?? body.query ?? body.message);
    const resultCount = normalizeResultCount(body.topK);

    const embedding = await env.AI.run(EMBEDDING_MODEL, {
      text: [question],
    });
    const vector = coerceEmbeddingVector(embedding);
    const matches = await env.FYI_VECTORS.query(vector, {
      returnMetadata: "all",
      topK: VECTORIZE_CANDIDATE_COUNT,
    });
    const candidates = matches.matches
      .map(mapVectorizeMatchToCitation)
      .filter((citation) => citation.snippet || citation.requestUrl || citation.sourceUrl);

    if (candidates.length === 0) {
      return jsonResponse({
        answer:
          "I could not find a strong matching record in the current Sunlight search index.",
        citations: [],
        question,
      });
    }

    const citations = await rerankSearchCandidates(question, candidates, resultCount);
    const answerResult = await env.AI.run(ANSWER_MODEL, {
      max_completion_tokens: 700,
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
      temperature: 0.2,
    });
    const answer = extractAnswerText(answerResult);

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
