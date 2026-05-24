import { SearchClient } from "./SearchClient";

export default function SearchPage() {
  return (
    <main className="search-page">
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
          <h1>Search Sunlight</h1>
          <p className="lede">
            Ask source-cited questions across public FYI.org.nz disclosures indexed by Sunlight.
          </p>
        </div>
      </section>

      <SearchClient />
    </main>
  );
}
