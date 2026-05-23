"use client";

import { CheckCircle2, CircleDashed, ExternalLink, LoaderCircle, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import {
  type SearchProgressStage,
  type SearchStreamEvent,
  parseSearchStreamLines,
} from "../../lib/search";

interface SearchCitation {
  authorityName?: string;
  chunkId: string;
  label: string;
  requestUrl?: string;
  score: number;
  snippet: string;
  sourceUrl?: string;
  title: string;
}

interface SearchResponse {
  answer?: string;
  citations?: SearchCitation[];
  error?: string;
  question?: string;
  stages?: SearchProgressStage[];
}

const EXAMPLE_QUESTIONS = [
  "What information has been released about council leisure centre contracts?",
  "Which records mention proactive release processes?",
  "What do the sources say about official information response delays?",
];

export function SearchClient() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [stages, setStages] = useState<SearchProgressStage[]>([]);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) {
      setError("Enter a search question.");
      setResult(null);
      return;
    }

    setIsLoading(true);
    setError("");
    setResult(null);
    setStages([]);

    try {
      const response = await fetch("/api/search", {
        body: JSON.stringify({ question: trimmed, stream: true }),
        headers: {
          "content-type": "application/json",
        },
        method: "POST",
      });
      if (!response.ok) {
        const payload = (await response.json()) as SearchResponse;
        throw new Error(payload.error || "Search failed.");
      }

      if (!response.body) {
        const payload = (await response.json()) as SearchResponse;
        setStages(payload.stages ?? []);
        setResult(payload);
        return;
      }

      await readSearchStream(response, {
        onError: (message) => {
          throw new Error(message);
        },
        onResult: (payload) => {
          setStages(payload.stages ?? []);
          setResult(payload);
        },
        onStage: (stage) => {
          setStages((current) => upsertStage(current, stage));
        },
      });
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Search failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="search-workspace">
      <form className="search-form" onSubmit={submitSearch}>
        <label htmlFor="search-question">Search the disclosure archive</label>
        <div className="search-box">
          <textarea
            id="search-question"
            maxLength={700}
            onChange={(event) => setQuestion(event.currentTarget.value)}
            placeholder="Ask about released official information records..."
            rows={4}
            value={question}
          />
          <button className="search-submit" disabled={isLoading} type="submit">
            {isLoading ? (
              <LoaderCircle aria-hidden="true" className="spin-icon" size={19} />
            ) : (
              <Search aria-hidden="true" size={19} />
            )}
            <span>{isLoading ? "Searching" : "Search"}</span>
          </button>
        </div>
        <div className="example-queries" aria-label="Example questions">
          {EXAMPLE_QUESTIONS.map((example) => (
            <button
              key={example}
              onClick={() => {
                setQuestion(example);
                setError("");
              }}
              type="button"
            >
              {example}
            </button>
          ))}
        </div>
      </form>

      {error ? <p className="search-error">{error}</p> : null}

      {stages.length > 0 ? (
        <section className="search-stages" aria-label="Search progress" aria-live="polite">
          {stages.map((stage) => (
            <div className="search-stage" data-status={stage.status} key={stage.id}>
              {stage.status === "complete" ? (
                <CheckCircle2 aria-hidden="true" size={18} />
              ) : stage.status === "running" ? (
                <LoaderCircle aria-hidden="true" className="spin-icon" size={18} />
              ) : (
                <CircleDashed aria-hidden="true" size={18} />
              )}
              <div>
                <p>{stage.label}</p>
                <span>{stage.detail ?? stageStatusLabel(stage)}</span>
              </div>
            </div>
          ))}
        </section>
      ) : null}

      {result ? (
        <section className="search-results" aria-live="polite">
          <div className="answer-panel">
            <p className="result-kicker">Answer</p>
            <p>{result.answer}</p>
          </div>

          <div className="citation-list" aria-label="Search citations">
            {(result.citations ?? []).map((citation) => (
              <article className="citation-item" key={citation.chunkId}>
                <div>
                  <p className="citation-label">
                    {citation.label}
                    {citation.authorityName ? ` / ${citation.authorityName}` : ""}
                  </p>
                  <h2>{citation.title}</h2>
                </div>
                <p>{citation.snippet || "No preview available."}</p>
                <div className="citation-meta">
                  <span>{Math.round(citation.score * 100)}% match</span>
                  {citation.requestUrl ? (
                    <a href={citation.requestUrl} rel="noreferrer" target="_blank">
                      FYI request
                      <ExternalLink aria-hidden="true" size={14} />
                    </a>
                  ) : null}
                  {citation.sourceUrl ? (
                    <a href={citation.sourceUrl} rel="noreferrer" target="_blank">
                      Source file
                      <ExternalLink aria-hidden="true" size={14} />
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

async function readSearchStream(
  response: Response,
  handlers: {
    onError(message: string): void;
    onResult(payload: SearchResponse): void;
    onStage(stage: SearchProgressStage): void;
  },
) {
  const reader = response.body?.getReader();
  if (!reader) {
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSearchStreamLines(buffer);
    buffer = parsed.remainder;
    handleSearchStreamEvents(parsed.events, handlers);
  }

  const tail = decoder.decode();
  if (tail || buffer) {
    const parsed = parseSearchStreamLines(`${buffer}${tail}\n`);
    handleSearchStreamEvents(parsed.events, handlers);
  }
}

function handleSearchStreamEvents(
  events: SearchStreamEvent[],
  handlers: {
    onError(message: string): void;
    onResult(payload: SearchResponse): void;
    onStage(stage: SearchProgressStage): void;
  },
) {
  for (const event of events) {
    if (event.type === "stage") {
      handlers.onStage(event.stage);
    } else if (event.type === "result") {
      handlers.onResult(event.result);
    } else {
      handlers.onError(event.error);
    }
  }
}

function upsertStage(
  stages: SearchProgressStage[],
  stage: SearchProgressStage,
): SearchProgressStage[] {
  const existingIndex = stages.findIndex((item) => item.id === stage.id);
  if (existingIndex === -1) {
    return [...stages, stage];
  }

  return stages.map((item, index) => (index === existingIndex ? stage : item));
}

function stageStatusLabel(stage: SearchProgressStage): string {
  if (stage.count !== undefined) {
    return `${stage.count} items`;
  }
  if (stage.durationMs !== undefined) {
    return `${stage.durationMs} ms`;
  }
  return stage.status === "running" ? "In progress" : "Complete";
}
