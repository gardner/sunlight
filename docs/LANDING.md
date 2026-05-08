# Sunlight Landing App

## Purpose

The landing app at `https://sunlight.nz` and `https://www.sunlight.nz` is the
public front door for the Sunlight Project.

It should explain what Sunlight is, why recurring OIA/LGOIMA disclosure
collection matters, and how agencies can recognize legitimate Sunlight Requests.

It is separate from:

* `https://admin.sunlight.nz`: internal operations app
* `https://requests.sunlight.nz`: agency response app

## Audience

Primary audiences:

* members of the public who want to understand the project
* journalists, researchers, and civic technologists
* agency staff who received a SunlightRequest
* potential supporters or collaborators

The landing app should be public, lightweight, and trustworthy.

## First View

The first viewport should make the project identity clear immediately.

Required first-view content:

* Sunlight name
* concise description of the project
* primary navigation
* clear path for agency staff who received a request

The page should not imply that Phase 0 already provides public search,
analytics, or a complete archive.

Suggested positioning:

Sunlight collects and preserves official information disclosure material so it
can be reviewed, searched, and reused responsibly by future public-interest
tools.

## Core Pages

Recommended routes:

* `/`
* `/about`
* `/for-agencies`
* `/method`
* `/contact`
* `/privacy`

Avoid building public browse/search pages in Phase 0.

## Home

The home page should explain:

* what Sunlight is building
* why OIA/LGOIMA disclosure material is useful
* what Phase 0 does and does not do
* how agencies can respond
* how to contact Sunlight

Calls to action:

* Agencies: respond using the unique link or reply address in the email they
  received.
* Public: follow project updates or contact Sunlight.

Do not include a generic upload form or public request submission form.

## For Agencies

This page should help agency staff verify and respond to a SunlightRequest.

It should explain:

* Sunlight sends recurring requests asking for OIA/LGOIMA requests and responses
  received by the agency for a defined period.
* Each request includes a unique reply email address.
* Each request includes a unique upload URL for large files.
* Agencies do not need to create an account.
* Agencies should not use the public landing page to upload files.
* If an agency is unsure whether a request is legitimate, it can contact
  Sunlight using published contact details.

The page should link to `requests.sunlight.nz` only in a general way. It should
not provide a tokenless response form.

## Method

The method page should describe the collection approach without overpromising.

Topics:

* recurring requests to selected agencies
* preservation of raw emails and files
* clear provenance from outbound request to received material
* operator review before publication
* future local processing for document parsing and metadata extraction
* no automatic public release in Phase 0

The page should distinguish:

* Sunlight's own request to agencies: `SunlightRequest`
* OIA/LGOIMA request material disclosed by agencies: disclosed request/response
  material

Public copy should avoid exposing internal class names unless useful. The
conceptual distinction should still be clear.

## Contact

Contact page content:

* general contact email
* agency response/support email
* project maintainer or organization details
* security/reporting contact for accidental sensitive disclosure concerns

Do not publish operational secrets, Worker routes, internal admin links, or raw
bucket URLs.

## Privacy

The privacy page should say:

* Sunlight receives and stores material from agencies.
* Material may contain personal or sensitive information.
* Phase 0 does not automatically publish received material.
* Raw material is preserved for review and processing.
* Publication, if added later, will require separate review workflows.
* Agencies can contact Sunlight about mistaken or sensitive submissions.

## Visual And UX Direction

The landing app should feel public-interest, calm, and credible.

Guidance:

* use restrained typography and layout
* avoid marketing-heavy claims
* make the project status clear
* keep agency instructions easy to scan
* make contact paths obvious

Do not present the landing page as a complete public OIA database until that
product exists.

## Relationship To Other Apps

The landing app can link to:

* `https://requests.sunlight.nz` only when explaining agency response links
* `mailto:` contact addresses
* future project updates

It should not link to:

* `https://admin.sunlight.nz`
* raw R2 assets
* unreviewed response material
* tokenized agency response URLs

## Non-Goals

The landing app does not:

* collect agency files
* authenticate admins
* expose the operational database
* provide public search in Phase 0
* let the public submit OIA requests
* publish unreviewed response material
