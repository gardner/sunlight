# Inbound Email & Refusal Mitigation Architecture

## 1. Overview
The Sunlight system relies on Cloudflare Email Routing to send outbound OIA/LGOIMA requests. While authorities are encouraged to use the direct-to-R2 secure portal for large data uploads, many will inevitably reply directly via email with attachments or refusal notices. 

To maintain our goal of minimal human intervention, we need a robust **Inbound Email Worker** to catch these replies, extract their contents, and an **Automated Refusal Mitigation** system to classify the responses and handle unjustified refusals.

## 2. Inbound Email Worker Architecture

Cloudflare allows routing incoming emails directly to a Worker. The worker implements an `email(message, env, ctx)` handler.

### 2.1. Responsibilities
1. **Intercept and Parse:** Receive incoming raw MIME emails. Use a library like `postal-mime` to parse headers, text/html bodies, and attachments.
2. **Identify the Request:** Match the `In-Reply-To`, `References`, or the `reply-TOKEN@sunlight.nz` recipient address to the original `SunlightRequest` in D1.
3. **Store Assets:**
   - Save the raw `.eml` file to R2 for archival purposes.
   - Extract attachments (PDFs, CSVs, XLSXs) and upload them to the `sunlight-request-artifacts` R2 bucket under the specific request's namespace.
4. **Update D1:** 
   - Create a `sunlight_responses` record linked to the `SunlightRequest`.
   - Update the `sunlight_requests.status` (e.g., from `awaiting_response` to `responded` or `refused`).

## 3. Automated Refusal Detection & Mitigation

Authorities frequently refuse bulk requests using standard statutory grounds (e.g., Section 18(d) OIA / Section 17(d) LGOIMA - "information is soon to be publicly available" or "administrative burden").

### 3.1. Detection
When a response is received (via email or the portal) without a data attachment, or containing standard refusal language, the system must classify it.
- **Heuristic Matching:** Regex/keyword matching for common refusal sections (e.g., "18(d)", "18(f)", "17(d)", "refuse", "decline").
- **LLM Classification:** If budget permits, run the response body through a lightweight AI prompt to classify the response type: `[GRANTED, PARTIAL, REFUSED_DATA_UNAVAILABLE, REFUSED_ADMIN_BURDEN, REFUSED_ALREADY_PUBLIC, EXTENSION_REQUESTED]`.

### 3.2. Automated Mitigation Workflow
If a refusal is detected, the system should automatically prepare a counter-response or flag it for specific mitigation workflows:

*   **Section 18(d) / 17(d) (Publicly Available):**
    *   **Guidance:** The Ombudsman's [Publicly Available Information Guide](https://www.ombudsman.parliament.nz/resources/publicly-available-information-guide-section-18d-oia-and-section-17d-lgoima) states that agencies must reasonably assist the requester. If they claim it's online, they must provide the *exact link*.
    *   **Mitigation:** If the response cites 18(d) but does not contain a URL, the system automatically drafts a follow-up email: *"Kia ora, you have refused this under section 18(d), but have not provided the location of the information. Under the Ombudsman's guidelines, please provide the direct URL..."*

*   **Section 18(f) / 17(f) (Substantial Collation or Research):**
    *   **Guidance:** Agencies must consider whether fixing a charge or extending the timeframe would enable the request to be granted before refusing it entirely.
    *   **Mitigation:** System drafts a follow-up asking if narrowing the scope (e.g., to just the top 3 levels of the directory) or extending the timeframe would mitigate the administrative burden.

### 3.3. Mitigation State Machine
1. `responded_refused`: The initial state when a refusal is detected.
2. `mitigation_drafted`: The system generates the automated counter-argument based on the refusal type.
3. `mitigation_sent`: The admin reviews and approves the counter-argument, sending it back to the authority.
4. `ombudsman_complaint_drafted`: If the authority upholds an illegitimate refusal after mitigation, the system drafts a formal Ombudsman complaint template.

## 4. Admin Response UI

The Admin UI will be expanded to manage this lifecycle.

1. **Inbox/Triage View:** A dashboard showing recently received responses, automatically categorized by their detected status.
2. **Response Detail View:**
   - Full email thread history.
   - List of extracted attachments with one-click download/preview from R2.
   - **Refusal Action Panel:** If a refusal is detected, this panel surfaces the Ombudsman guidelines relevant to the cited section and provides the pre-drafted mitigation email for the admin to approve and send.
3. **Audit Log:** Every automated classification, drafted mitigation, and received email is logged to `sunlight_audit_events`.

## 5. Next Implementation Steps
1. Add `sunlight_responses` and `sunlight_communications` tables to the D1 schema.
2. Create the Cloudflare Email Worker (`apps/inbound-email`) using `postal-mime`.
3. Build the Admin UI for reading email threads and viewing R2 attachments.
4. Implement the Refusal Classifier and Mitigation Drafter logic.
