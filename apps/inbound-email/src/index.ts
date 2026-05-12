import PostalMime from "postal-mime";

export interface Env {
  DB: D1Database;
  ARTIFACTS: R2Bucket;
  AI: any;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext) {
    const url = new URL(request.url);
    if (url.pathname === '/test-ai') {
      try {
        const aiResponse = await env.AI.run('@cf/qwen/qwen3-embedding-0.6b', {
          text: "This is a test of the emergency broadcasting system."
        });
        return new Response(JSON.stringify(aiResponse), { headers: { 'Content-Type': 'application/json' } });
      } catch (e) {
        return new Response(String(e), { status: 500 });
      }
    }
    return new Response("Not found", { status: 404 });
  },

  async email(message: ForwardableEmailMessage, env: Env, ctx: ExecutionContext) {
    const rawEmail = await new Response(message.raw).arrayBuffer();
    const parser = new PostalMime();
    const email = await parser.parse(rawEmail);

    const from = message.from;
    const to = message.to;
    const subject = email.subject || "No Subject";
    
    // Save raw email to R2
    const messageId = email.messageId || `msg_${crypto.randomUUID()}`;
    const rawKey = `inbound/raw/${messageId}.eml`;
    await env.ARTIFACTS.put(rawKey, rawEmail);

    let sunlightRequestId: string | null = null;
    let sunlightResponseId: string | null = null;
    
    // Look for reply-TOKEN@sunlight.nz in the 'to' address
    const replyMatch = to.match(/reply-([a-zA-Z0-9_-]+)@sunlight\.nz/);
    let caseToken = replyMatch ? replyMatch[1] : null;

    let associationStatus: "matched" | "unmatched" | "ambiguous" = "unmatched";
    let associationReason: string | null = null;
    let req: { id: string, authority_id: string } | null = null;

    if (caseToken) {
      const data = new TextEncoder().encode(caseToken);
      const hashBuf = await crypto.subtle.digest("SHA-256", data);
      const hashStr = Array.from(new Uint8Array(hashBuf))
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");
        
      req = await env.DB.prepare(`
        SELECT id, authority_id FROM sunlight_requests WHERE case_token_hash = ?
      `).bind(hashStr).first<{id: string, authority_id: string}>();
      
      if (!req) {
        associationReason = "invalid case token in to-address";
      } else {
        associationReason = "matched via reply-to token";
      }
    } else if (email.inReplyTo) {
      req = await env.DB.prepare(`
        SELECT sunlight_requests.id, sunlight_requests.authority_id 
        FROM sunlight_outbound_emails
        JOIN sunlight_requests ON sunlight_requests.id = sunlight_outbound_emails.sunlight_request_id
        WHERE provider_message_id = ? AND provider_message_id IS NOT NULL
      `).bind(email.inReplyTo).first<{id: string, authority_id: string}>();

      if (req) {
        associationReason = "matched via In-Reply-To header";
      } else {
        associationReason = "no case token in to-address and no matching In-Reply-To";
      }
    } else {
      associationReason = "no case token found in to-address and no In-Reply-To header";
    }

    if (req) {
      sunlightRequestId = req.id;
      associationStatus = "matched";
      
      sunlightResponseId = `rsp_${crypto.randomUUID().replaceAll("-", "")}`;
      
      const bodyTextLower = (email.text || "").toLowerCase();
      
      const isRefusal = bodyTextLower.includes("refuse") || 
                        bodyTextLower.includes("decline") || 
                        bodyTextLower.includes("withheld") || 
                        bodyTextLower.includes("18(d)") || 
                        bodyTextLower.includes("17(d)") ||
                        bodyTextLower.includes("18(f)") ||
                        bodyTextLower.includes("17(f)");
      
      const category = isRefusal ? "refusal" : (email.attachments && email.attachments.length > 0 ? "full_response" : "unknown");

      await env.DB.prepare(`
        INSERT INTO sunlight_responses (
          id, sunlight_request_id, authority_id, channel, category, status, received_at, submitter_email
        ) VALUES (?, ?, ?, 'email', ?, 'received', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)
      `).bind(sunlightResponseId, sunlightRequestId, req.authority_id, category, from).run();
      
      await env.DB.prepare(`
        UPDATE sunlight_requests SET status = 'response_received', last_response_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?
      `).bind(sunlightRequestId).run();

      if (isRefusal) {
         const mitigationId = `mit_${crypto.randomUUID().replaceAll("-", "")}`;
         
         let reason = "unknown";
         let draft = "Kia ora,\n\nWe have received your refusal. Could you please clarify the specific section under which this was refused?\n\nNgā mihi,\nSunlight Project";
         
         if (bodyTextLower.includes("18(d)") || bodyTextLower.includes("17(d)")) {
           reason = "Section 18(d) / 17(d)";
           draft = "Kia ora,\n\nWe note you have refused this request under section 18(d) / 17(d) as the information is publicly available. However, in accordance with the Ombudsman's guidelines, please provide the exact URL or location where this information can be accessed.\n\nNgā mihi,\nSunlight Project";
         } else if (bodyTextLower.includes("18(f)") || bodyTextLower.includes("17(f)")) {
           reason = "Section 18(f) / 17(f)";
           draft = "Kia ora,\n\nWe note you have refused this request under section 18(f) / 17(f) due to substantial collation or research. Before refusing entirely, would fixing a charge or extending the timeframe enable the request to be granted? Alternatively, how might we refine our request to remove this burden?\n\nNgā mihi,\nSunlight Project";
         }

         await env.DB.prepare(`
           INSERT INTO sunlight_refusal_mitigations (
             id, sunlight_request_id, sunlight_response_id, refusal_reason, status, drafted_response
           ) VALUES (?, ?, ?, ?, 'drafted', ?)
         `).bind(mitigationId, sunlightRequestId, sunlightResponseId, reason, draft).run();
      }
    }

    const inboundEmailId = `inb_${crypto.randomUUID().replaceAll("-", "")}`;
    
    let needsHumanReview = 0;
    let aiTriageReason = "LLM triage not available";

    if (!req) {
      needsHumanReview = 1;
      aiTriageReason = "Direct email (unmatched), requires human review";
    } else if (email.text) {
      try {
        const aiResponse = await env.AI.run('@cf/moonshotai/kimi-k2.6', {
          messages: [
            { role: "system", content: "You are an assistant for an Official Information Act project. Read the following email response from a government agency. Determine if this email requires a human volunteer to read and respond to it. If the email is just an automated acknowledgement, an out-of-office auto-reply, a standard extension notice, a standard response with attached files, or a standard refusal, it DOES NOT need human review (reply false). If the agency is asking a clarifying question, requesting payment, stating the request is too broad and asking us to refine it, or asking us to call them, it DOES need human review (reply true). Respond ONLY with a valid JSON object matching this schema: {\"needs_human_review\": boolean, \"reason\": \"brief explanation\"}" },
            { role: "user", content: `Subject: ${subject}\n\n${email.text}` }
          ]
        });

        let rawResponseString = "";
        try {
          rawResponseString = JSON.stringify(aiResponse);
        } catch (e) {
          rawResponseString = String(aiResponse);
        }

        let jsonStr = "";
        if (typeof aiResponse === 'string') {
          jsonStr = aiResponse;
        } else if (aiResponse && aiResponse.response) {
          jsonStr = aiResponse.response;
        } else if (aiResponse && aiResponse.content) {
          jsonStr = aiResponse.content;
        } else if (aiResponse && aiResponse.result && aiResponse.result.response) {
          jsonStr = aiResponse.result.response;
        } else if (aiResponse && Array.isArray(aiResponse.choices) && aiResponse.choices.length > 0 && aiResponse.choices[0].message && aiResponse.choices[0].message.content) {
          jsonStr = aiResponse.choices[0].message.content;
        } else {
          jsonStr = rawResponseString;
        }

        if (jsonStr) {
          const firstBrace = jsonStr.indexOf('{');
          const lastBrace = jsonStr.lastIndexOf('}');
          if (firstBrace !== -1 && lastBrace !== -1 && lastBrace >= firstBrace) {
            jsonStr = jsonStr.substring(firstBrace, lastBrace + 1);
          } else {
            jsonStr = jsonStr.replace(/```json/g, "").replace(/```/g, "").trim();
          }
          
          try {
            const parsed = JSON.parse(jsonStr);
            needsHumanReview = parsed.needs_human_review ? 1 : 0;
            aiTriageReason = parsed.reason || "No reason provided";
          } catch (parseError) {
            aiTriageReason = `JSON Parse error on: ${jsonStr}. Raw output was: ${rawResponseString}`;
          }
        } else {
          aiTriageReason = `No string extracted. Raw output was: ${rawResponseString}`;
        }
      } catch (e) {
        aiTriageReason = `LLM error: ${e instanceof Error ? e.message : String(e)}`;
      }
    }

    await env.DB.prepare(`
      INSERT INTO sunlight_inbound_emails (
        id, sunlight_request_id, sunlight_response_id, provider, raw_r2_bucket, raw_r2_key,
        from_email, to_emails_json, subject, message_id_header, in_reply_to_header, received_at,
        association_status, association_reason, status, body_text, body_html, needs_human_review, human_review_status, ai_triage_reason
      ) VALUES (?, ?, ?, 'cloudflare_email_routing', 'sunlight-request-artifacts', ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?, 'stored', ?, ?, ?, 'pending', ?)
    `).bind(
      inboundEmailId, sunlightRequestId ?? null, sunlightResponseId ?? null, rawKey ?? null,
      from ?? null, JSON.stringify([to]), subject ?? null, email.messageId ?? null, email.inReplyTo ?? null,
      associationStatus ?? null, associationReason ?? null, email.text ?? null, email.html ?? null, needsHumanReview, aiTriageReason ?? null
    ).run();

    if (email.attachments && email.attachments.length > 0) {
      for (const attachment of email.attachments) {
        const attId = `att_${crypto.randomUUID().replaceAll("-", "")}`;
        const safeName = (attachment.filename || "unnamed").replace(/[^a-zA-Z0-9.-]/g, "_");
        const key = `inbound/attachments/${inboundEmailId}/${safeName}`;
        
        await env.ARTIFACTS.put(key, attachment.content, {
          httpMetadata: { contentType: attachment.mimeType }
        });
        
        const sizeBytes = typeof attachment.content === 'string' ? new TextEncoder().encode(attachment.content).byteLength : attachment.content.byteLength;
        
        if (sunlightRequestId) {
           await env.DB.prepare(`
             INSERT INTO sunlight_inbound_attachments (
               id, inbound_email_id, sunlight_request_id, filename, content_type, size_bytes, r2_bucket, r2_key, status
             ) VALUES (?, ?, ?, ?, ?, ?, 'sunlight-request-artifacts', ?, 'stored')
           `).bind(
             attId, inboundEmailId, sunlightRequestId, attachment.filename || "unnamed", 
             attachment.mimeType ?? null, sizeBytes, key
           ).run();
        }
      }
    }
  }
}
