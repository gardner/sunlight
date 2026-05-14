"use client";

import { ExternalLink, LoaderCircle, Search } from "lucide-react";
import { FormEvent, useState } from "react";

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

    try {
      const response = await fetch("/api/search", {
        body: JSON.stringify({ question: trimmed }),
        headers: {
          "content-type": "application/json",
        },
        method: "POST",
      });
      const payload = (await response.json()) as SearchResponse;
      if (!response.ok) {
        throw new Error(payload.error || "Search failed.");
      }
      setResult(payload);
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
