const processSteps = [
  {
    marker: "01",
    title: "Request",
    body: "Sends recurring OIA/LGOIMA requests to selected public agencies.",
  },
  {
    marker: "02",
    title: "Receive",
    body: "Intakes material by reply email or a unique upload link for large files.",
  },
  {
    marker: "03",
    title: "Preserve",
    body: "Stores files, emails, and metadata with a clear provenance trail.",
  },
  {
    marker: "04",
    title: "Prepare",
    body: "Keeps material ready for later review, search, and responsible reuse.",
  },
];

const publicValue = [
  "Disclosure material is public infrastructure.",
  "Recurring collection reduces fragmentation across agencies.",
  "Preserved material can support journalism, research, and civic technology.",
];

const agencyItems = [
  {
    title: "Respond directly",
    body: "Use the unique link or reply address in the Sunlight request email.",
  },
  {
    title: "Large files supported",
    body: "Transfer substantial response packages through the unique upload page.",
  },
  {
    title: "No account required",
    body: "Agency staff do not need to create or manage another login.",
  },
  {
    title: "Verify requests",
    body: "Contact Sunlight if you need to confirm a request is legitimate.",
  },
];

export default function LandingPage() {
  return (
    <main>
      <header className="site-header" aria-label="Sunlight navigation">
        <a className="brand" href="#top" aria-label="Sunlight home">
          Sunlight
        </a>
        <nav className="nav-links" aria-label="Primary navigation">
          <a href="#about">About</a>
          <a href="#agencies">For agencies</a>
          <a href="#method">Method</a>
          <a href="#contact">Contact</a>
        </nav>
        <a className="nav-action" href="#agencies">
          Agency path
        </a>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="status-label">Public interest archive</p>
          <h1>Sunlight</h1>
          <p className="lede">
            We collect and preserve official information disclosure material for
            future public-interest review, search, and reuse.
          </p>
          <p className="context">
            Sunlight is an independent project building quiet, reliable
            infrastructure for civic transparency. It is not a government
            service, and Phase 0 does not automatically publish received files.
          </p>
          <div className="hero-actions" aria-label="Landing page actions">
            <a className="button button-primary" href="#agencies">
              For agencies
            </a>
            <a className="button button-secondary" href="#method">
              How it works
            </a>
          </div>
        </div>
        <figure className="archive-figure">
          <img
            alt="A neatly stacked set of official disclosure documents in warm light"
            height="941"
            src="/sunlight.webp"
            width="1672"
          />
          <figcaption>
            Preserved with source, timing, and request provenance intact.
          </figcaption>
        </figure>
      </section>

      <section className="process-band" id="about" aria-labelledby="process-title">
        <div className="section-heading">
          <p className="kicker">What Sunlight does</p>
          <h2 id="process-title">The preservation process</h2>
        </div>
        <div className="process-grid">
          {processSteps.map((step) => (
            <article className="process-step" key={step.title}>
              <span aria-hidden="true">{step.marker}</span>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="split-section" aria-labelledby="value-title">
        <div className="section-heading">
          <p className="kicker">Why it matters</p>
          <h2 id="value-title">Information as infrastructure.</h2>
          <p>
            OIA and LGOIMA disclosures often arrive as isolated transactions.
            Sunlight preserves them as durable public-interest material.
          </p>
        </div>
        <div className="value-list">
          {publicValue.map((item) => (
            <div className="value-item" key={item}>
              <span aria-hidden="true" />
              <p>{item}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="agency-panel" id="agencies" aria-labelledby="agency-title">
        <div>
          <p className="kicker">For agencies</p>
          <h2 id="agency-title">A clear path for responding.</h2>
          <p>
            If your agency received a Sunlight request, use the unique response
            link or reply address in that email. The public homepage does not
            provide a tokenless upload form.
          </p>
          <div className="agency-grid">
            {agencyItems.map((item) => (
              <article className="agency-item" key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="secure-link-card" aria-label="Example secure response link">
          <div className="window-dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="mock-line long" />
          <div className="mock-line" />
          <div className="mock-line medium" />
          <div className="mock-button">Unique response link</div>
        </div>
      </section>

      <section className="method-trust" id="method">
        <article>
          <p className="kicker">Method</p>
          <h2>Requests and disclosures stay distinct.</h2>
          <p>
            Sunlight sends its own recurring requests to agencies. Agencies then
            disclose OIA/LGOIMA request and response material back to Sunlight.
            The collection workflow keeps those two layers separate.
          </p>
          <div className="flow" aria-label="Collection flow">
            <span>Sunlight request</span>
            <span>Agency disclosure</span>
            <span>Preserved material</span>
          </div>
        </article>
        <article>
          <p className="kicker">Trust and handling</p>
          <h2>Careful by default.</h2>
          <p>
            Phase 0 focuses on collection, provenance, and review. Raw material
            is preserved for later processing, and sensitive or mistaken
            submissions can be raised with Sunlight.
          </p>
          <div className="trust-markers">
            <span>Secure storage</span>
            <span>Provenance maintained</span>
          </div>
        </article>
      </section>

      <footer className="site-footer" id="contact">
        <strong>Sunlight</strong>
        <nav aria-label="Footer navigation">
          <a href="mailto:sunlight@spunts.net">Contact</a>
          <a href="#method">Privacy</a>
          <a href="#about">Project status</a>
        </nav>
        <span>Independent public-interest infrastructure.</span>
      </footer>
    </main>
  );
}
