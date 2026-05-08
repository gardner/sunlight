# Sunlight Public Web Design Brief

## Purpose

This document is a creative brief and prompt source for generating landing page
design directions in Stitch and Claude Design. It is not the implementation
spec; the implementation boundaries remain in `docs/LANDING.md`.

The goal is to generate two strong visual directions for the public Sunlight
landing page, then select and adapt the best ideas into the Vinext landing app.

## Typography Research

Use Fira Sans as the primary typeface.

Rationale:

* `govt.nz` uses Fira Sans with `Helvetica`, `Arial`, and `sans-serif`
  fallbacks.
* `govt.nz` describes Fira Sans as readable, open source, and intentionally not
  too formal.
* The wider New Zealand Government identity system uses more formal identity
  typefaces such as Ideal Sans, but Sunlight is not a government service and
  should avoid looking like an official government website.

References:

* <https://www.govt.nz/about/the-govt-nz-website/typography/>
* <https://dns.govt.nz/blog/govt-nz-design-overhaul>
* <https://www.publicservice.govt.nz/assets/DirectoryFile/New-Zealand-Government-Identity-Technical-Style-Guide.pdf>

Recommended CSS stack:

```css
font-family: "Fira Sans", Helvetica, Arial, sans-serif;
```

## Design Direction

Sunlight should feel independent, public-interest, calm, credible, and
operationally competent.

It should not look like:

* a government department
* a political campaign
* a generic SaaS landing page
* a crypto/transparency hype site
* a legal-services brochure

Avoid New Zealand government visual signals:

* no coat of arms
* no flags as major graphic devices
* no Beehive imagery as a hero image
* no official government green/black palette
* no dense bureaucratic header treatment

Use an independent civic palette. Good directions include warm white, ink,
deep teal, restrained yellow, muted coral, blue-grey, and soft paper tones. The
palette should have enough contrast for accessibility and should avoid being
dominated by a single hue.

The visual style should communicate trust through restraint, clarity,
provenance, and legible structure rather than decoration.

## Information Architecture

The landing page should support these audiences:

* members of the public who want to understand the project
* journalists, researchers, and civic technologists
* agency staff who received a SunlightRequest
* potential supporters or collaborators

Recommended top navigation:

* About
* For agencies
* Method
* Contact

Primary page sections:

1. Header
   * Sunlight wordmark or text identity
   * concise navigation
   * clear agency path

2. Hero
   * project name as the headline
   * one-sentence explanation
   * primary call to action for agency staff
   * secondary call to action for public readers
   * no claim that the archive is already publicly searchable

3. What Sunlight Does
   * sends recurring OIA/LGOIMA requests to agencies
   * receives request and response material
   * preserves files and metadata with provenance
   * prepares material for later review, search, and reuse

4. Why It Matters
   * disclosure material is public infrastructure
   * recurring collection reduces fragmentation
   * preserved material can support journalism, research, civic technology, and
     accountability

5. For Agencies
   * explain that agencies respond using the unique link or reply email they
     received
   * explain that no account is required
   * explain that large files can be uploaded through the unique response link
   * provide a contact path for verification questions

6. Method
   * explain collection, preservation, operator review, and future processing
   * distinguish Sunlight's own requests from the OIA/LGOIMA request material
     disclosed by agencies
   * avoid exposing internal implementation details unless useful to establish
     trust

7. Trust And Handling
   * state that Phase 0 does not automatically publish received files
   * state that sensitive or mistaken submissions can be raised with Sunlight
   * emphasize provenance, review, and careful handling

8. Footer
   * contact links
   * privacy link
   * project status
   * no admin links, raw storage links, or tokenized response URLs

## Copy Direction

Use plain, direct language.

The page should say that Sunlight is collecting and preserving official
information disclosure material so it can be reviewed, searched, and reused
responsibly by future public-interest tools.

Use `SunlightRequest` only where the distinction is useful. In public copy,
prefer phrases such as "a request from Sunlight" and "the material agencies
disclose in response".

Avoid overpromising:

* do not imply public search is live
* do not imply all received material is automatically published
* do not imply Sunlight is a government service
* do not imply agencies can upload files from the public homepage

## Prompt For Design Tools

Use this prompt in Stitch and Claude Design:

```text
Design a polished public landing page for Sunlight, an independent New Zealand
public-interest project that collects and preserves official information
disclosure material from government agencies.

Sunlight sends recurring OIA/LGOIMA requests to agencies asking for the OIA and
LGOIMA requests and responses they received during a defined period. Agencies
respond by email or by using a unique upload link for large files. Sunlight
preserves the raw emails, files, metadata, and provenance so the material can be
reviewed, searched, and reused responsibly by future public-interest tools.

This is not a government website. The design should feel trustworthy, civic,
independent, calm, transparent, and operationally competent. Avoid looking like
a New Zealand government service, political campaign, legal brochure, or generic
SaaS landing page. Do not use official government visual signals such as coats
of arms, flags as major graphic devices, Beehive imagery, or the official
government green/black color scheme.

Use Fira Sans as the primary typeface, with Helvetica, Arial, and sans-serif
fallbacks. The typography should feel clear, public-service minded, and highly
legible without becoming bureaucratic.

Create a trust-based visual system using restraint and clarity. Use an
independent civic palette such as warm white, ink, deep teal, restrained yellow,
muted coral, blue-grey, and soft paper tones. The palette must be accessible,
high contrast, and not dominated by one hue. Use subtle structural details,
document/provenance motifs, timeline or chain-of-custody patterns, and clear
content hierarchy. Avoid decorative gradient blobs, oversized marketing cards,
and vague stock imagery.

Information architecture:

Header:
- Sunlight identity
- Navigation: About, For agencies, Method, Contact
- A clear path for agency staff who received a request

Hero:
- Headline: Sunlight
- Supporting copy explaining that Sunlight collects and preserves official
  information disclosure material for future public-interest review, search,
  and reuse
- Primary CTA: For agencies
- Secondary CTA: How it works
- Make clear this is an independent project, not a government service

What Sunlight does:
- Sends recurring OIA/LGOIMA requests to selected agencies
- Receives agency request and response material
- Preserves files and metadata with provenance
- Prepares material for later review, search, and responsible reuse

Why it matters:
- Disclosure material is public infrastructure
- Recurring collection reduces fragmentation
- Preserved material can support journalism, research, civic technology, and
  accountability

For agencies:
- Agencies respond using the unique link or reply email in the request they
  received
- No account is required
- Large files can be uploaded through the unique response link
- Agencies can contact Sunlight to verify a request

Method:
- Explain collection, preservation, operator review, and future processing
- Clearly distinguish Sunlight's own requests from the OIA/LGOIMA material that
  agencies disclose in response
- Do not imply that all received material is automatically published

Trust and handling:
- Phase 0 does not automatically publish received files
- Raw material is preserved for review and processing
- Sensitive or mistaken submissions can be raised with Sunlight
- Emphasize provenance, careful handling, and operational transparency

Footer:
- Contact
- Privacy
- Project status
- No admin links, raw storage links, or tokenized response URLs

Design requirements:
- Build the actual landing page experience, not a marketing splash page
- The first viewport must make the Sunlight name and purpose clear
- The hero should leave a hint of the next section visible on desktop and mobile
- Keep agency instructions easy to scan
- Use clear section rhythm, strong typography, and practical responsive layout
- Avoid nested cards, heavy illustration, dark atmospheric imagery, and vague
  decorative UI
- Do not include public search, public upload, or public OIA request submission
  features in this phase
```

## Evaluation Criteria

When comparing generated designs, prefer the direction that:

* makes the project purpose immediately clear
* feels independent but institutionally credible
* gives agency staff a clear and calm path
* explains project status without overpromising
* has accessible contrast and readable typography
* can be implemented cleanly in the existing Vinext landing app
* avoids government mimicry while still feeling civic and trustworthy
