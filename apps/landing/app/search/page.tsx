import { SearchClient } from "./SearchClient";

export default function SearchPage() {
  return (
    <main>
      <header className="site-header" aria-label="Sunlight navigation">
        <a className="brand" href="/" aria-label="Sunlight home">
          Sunlight
        </a>
        <nav className="nav-links" aria-label="Primary navigation">
          <a href="/#about">How it works</a>
          <a href="/search">Search</a>
          <a href="/#authorities">For authorities</a>
          <a href="/#method">Method</a>
          <a href="/#contact">Contact</a>
        </nav>
        <a className="nav-action" href="/#authorities">
          For authorities
        </a>
      </header>

      <section className="search-hero">
        <div>
          <p className="status-label">Semantic search for official information</p>
          <h1>Search Sunlight</h1>
          <p className="lede">
            Ask source-cited questions across the public FYI.org.nz disclosure corpus indexed by Sunlight.
          </p>
        </div>
      </section>

      <SearchClient />
    </main>
  );
}
