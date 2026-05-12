# Unlocking Cloudflare Email Sending for Production

Cloudflare Workers provides a powerful native `send_email` binding, allowing you to dispatch emails directly from the edge. However, to prevent abuse and spam, Cloudflare places all new domains in a strict sandbox by default. 

In the sandbox, you can only send emails to **Verified Destination Addresses** (which require a manual opt-in click from the recipient). This is fine for testing, but untenable for sending bulk OIA requests to 1,300+ government authorities.

To send to arbitrary external addresses, you must unlock full Email Sending by proving your domain's reputation and properly configuring standard email authentication protocols.

## Phase 1: DNS Authentication Configuration

Before requesting to exit the sandbox, your domain (`sunlight.nz`) must be technically proven to be a legitimate sender. This requires setting up three DNS records to verify outbound authenticity and protect against spoofing.

### 1. SPF (Sender Policy Framework)
SPF tells receiving mail servers which IP addresses or services are authorized to send email on behalf of your domain.
- **Action:** Add a `TXT` record on `sunlight.nz`.
- **Value:** Cloudflare provides the specific include string for their outbound servers (usually something like `v=spf1 include:_spf.mx.cloudflare.net ~all`). If you also send email from another provider (like Google Workspace), you must combine them into a single SPF record.

### 2. DKIM (DomainKeys Identified Mail)
DKIM adds a cryptographic signature to every outgoing email, proving it genuinely originated from your domain and hasn't been altered in transit.
- **Action:** Cloudflare automatically generates DKIM keys for domains it manages. 
- **Action:** You must ensure the DKIM records (usually a few `CNAME` or `TXT` records like `cloudflare1._domainkey.sunlight.nz`) are active and successfully resolving in your Cloudflare DNS tab.

### 3. DMARC (Domain-based Message Authentication, Reporting, and Conformance)
DMARC ties SPF and DKIM together. It tells receiving servers what to do if an email *fails* the SPF/DKIM checks (e.g., quarantine it or reject it) and where to send reports of abuse.
- **Action:** Add a `TXT` record for `_dmarc.sunlight.nz`.
- **Value:** `v=DMARC1; p=quarantine; rua=mailto:admin@sunlight.nz;` (This instructs servers to send failing emails to the spam folder, and sends daily forensic reports to your admin address).

## Phase 2: Unlocking the Cloudflare Sandbox

Cloudflare Email Sending (for outbound emails to unverified external addresses) is a closely guarded feature.

### 1. Requesting Access
Currently, outbound sending to arbitrary addresses is in Beta or restricted access. 
- You must go to the **Email** -> **Email Routing** section of the Cloudflare Dashboard.
- Look for the **Outbound / Sending** settings or beta enrollment prompts.
- If no automated "Unlock" button is available, you must open a **Cloudflare Support Ticket**.

### 2. Information to Provide to Support
When opening a ticket to request full sending access, you must clearly explain your use case to prove you are not a spammer. Provide them with this template:

> **Subject:** Request to unlock Email Sending (Workers) for sunlight.nz
>
> We are Open Data Limited, a registered New Zealand non-profit operating a public-interest civic data project. We are using Cloudflare Workers to dispatch automated Official Information Act (OIA) requests to New Zealand government authorities.
> 
> We are currently limited to sending to Verified Destination Addresses. We need to unlock full outbound sending capabilities to dispatch requests to the ~1,300 government mailboxes in our database. 
> 
> We have already configured strict SPF, DKIM, and DMARC policies for `sunlight.nz`. Our outbound volume will be low-velocity, highly structured, and entirely compliant with New Zealand statutory frameworks. Could you please lift the destination verification restriction for our zone?

## Phase 3: Alternative Fallback (Transactional Providers)

If Cloudflare denies the request or the beta process is too slow, the standard industry fallback is to replace the native `send_email` binding with a transactional email API.

If necessary, we can swap the backend implementation in `apps/admin/lib/outbound-email.ts` to use a provider like **Resend**, **Postmark**, or **SendGrid** in under 20 lines of code. These services specialize in high deliverability and do not require destination verification once your domain DNS is configured.
