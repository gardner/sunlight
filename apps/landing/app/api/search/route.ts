import { env } from "cloudflare:workers";
import {
  SearchInputError,
  buildAnswerPrompt,
  coerceEmbeddingVector,
  extractAnswerText,
  mapVectorizeMatchToCitation,
  normalizeSearchQuestion,
} from "../../../lib/search";

const EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b";
const ANSWER_MODEL = "@cf/google/gemma-4-26b-a4b-it";
const DEFAULT_TOP_K = 7;
const MAX_TOP_K = 10;

export async function POST(request: Request) {
  try {
    const body = await readJsonBody(request);
    const question = normalizeSearchQuestion(body.question ?? body.query ?? body.message);
    const topK = normalizeTopK(body.topK);

    const embedding = await env.AI.run(EMBEDDING_MODEL, {
      text: [question],
    });
    const vector = coerceEmbeddingVector(embedding);
    const matches = await env.FYI_VECTORS.query(vector, {
      returnMetadata: "all",
      topK,
    });
    const citations = matches.matches
      .map(mapVectorizeMatchToCitation)
      .filter((citation) => citation.snippet || citation.requestUrl || citation.sourceUrl);

    if (citations.length === 0) {
      return jsonResponse({
        answer:
          "I could not find a strong matching record in the current Sunlight search index.",
        citations: [],
        question,
      });
    }

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

function normalizeTopK(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_TOP_K;
  }
  return Math.min(MAX_TOP_K, Math.max(1, Math.floor(value)));
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
