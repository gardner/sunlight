const processSteps = [
  {
    marker: "01",
    title: "Request",
    body: "Sunlight sends recurring OIA and LGOIMA requests to selected public authorities.",
  },
  {
    marker: "02",
    title: "Receive",
    body: "Authorities reply by email or use a secure upload link for larger files.",
  },
  {
    marker: "03",
    title: "Preserve",
    body: "Responses, attachments, and key metadata are stored together so the source and timing remain clear.",
  },
  {
    marker: "04",
    title: "Prepare",
    body: "Material is prepared for review, search, and responsible public use.",
  },
];

const publicValue = [
  "Official information responses are often scattered across inboxes, release pages, and one-off exchanges. That makes them hard to find and easy to lose.",
  "Sunlight helps preserve these records in one place so they can be reviewed, searched, and reused more easily.",
  "Bringing this material together supports journalism, research, public understanding, and civic technology.",
];

const authorityItems = [
  {
    title: "Reply by email",
    body: "Use the reply address shown in the request email.",
  },
  {
    title: "Send large files",
    body: "If the response package is too large for email, use the secure upload link provided.",
  },
  {
    title: "No account required",
    body: "Authority staff do not need to create an account to respond.",
  },
  {
    title: "Need to confirm a request is genuine?",
    body: "Contact Sunlight and we can verify it.",
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
          <a href="#about">How it works</a>
          <a href="#authorities">For authorities</a>
          <a href="#method">Method</a>
          <a href="#contact">Contact</a>
        </nav>
        <a className="nav-action" href="#authorities">
          For authorities
        </a>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="status-label">Public-interest archive for official information</p>
          <h1>Sunlight</h1>
          <p className="lede">
            Sunlight collects official information responses from public authorities, preserves them with clear provenance, and prepares them for careful review, search, and reuse.
          </p>
          <p className="context">
            Sunlight is an independent project. It is not a government service, and material sent to Sunlight is not published automatically.
          </p>
          <div className="hero-actions" aria-label="Landing page actions">
            <a className="button button-primary" href="#about">
              Learn how it works
            </a>
            <a className="button button-secondary" href="#authorities">
              For authorities
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
            Kept with clear provenance.
          </figcaption>
        </figure>
      </section>

      <section className="process-band" id="about" aria-labelledby="process-title">
        <div className="section-heading">
          <p className="kicker">How it works</p>
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
          <p className="kicker">Why this matters</p>
          <h2 id="value-title">Official information, kept accessible.</h2>
          <p>
            Sunlight is building infrastructure for better access to official information. The goal is simple: make important public records easier to find, easier to search, and easier to use.
          </p>
        </div>
        <div className="value-list">
          {publicValue.map((item, index) => (
            <div className="value-item" key={index}>
              <span aria-hidden="true" />
              <p>{item}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="authority-panel" id="authorities" aria-labelledby="authority-title">
        <div>
          <p className="kicker">For authorities</p>
          <h2 id="authority-title">Responding to a Sunlight request</h2>
          <p>
            If your authority has received a request from Sunlight, please use the unique reply address or secure upload link included in that request.
          </p>
          <div className="authority-grid">
            {authorityItems.map((item) => (
              <article className="authority-item" key={item.title}>
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
          <h2>Requests and responses are tracked separately.</h2>
          <p>
            Sunlight sends recurring requests to authorities. Authorities then send back the material covered by those requests.
            To keep the record clear, Sunlight tracks the outgoing request, the authority response, and the preserved material as related but separate records.
          </p>
          <div className="flow" aria-label="Collection flow">
            <span>Sunlight request</span>
            <span>Authority response</span>
            <span>Preserved material</span>
          </div>
        </article>
        <article>
          <p className="kicker">Trust and handling</p>
          <h2>Careful by default.</h2>
          <p>
            Sunlight focuses on collecting and preserving material responsibly. Files are kept with their provenance intact, reviewed before publication, and handled carefully if something sensitive or mistaken is submitted.
          </p>
          <div className="trust-markers">
            <span>Secure storage</span>
            <span>Kept with clear provenance</span>
          </div>
        </article>
      </section>

      <footer className="site-footer" id="contact">
        <strong>Sunlight</strong>
        <nav aria-label="Footer navigation">
          <a href="mailto:sunlight@spunts.net">Contact Sunlight</a>
          <a href="#method">Privacy</a>
          <a href="#about">Project status</a>
        </nav>
        <span>Sunlight is an independent public-interest project. It is not part of government. Material received by Sunlight is preserved for review and processing and is not published automatically.</span>
      </footer>
    </main>
  );
}
