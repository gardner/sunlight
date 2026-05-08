import { createRemoteJWKSet, jwtVerify } from "jose";

export interface AccessIdentity {
  email: string;
  subject: string;
}

export interface AdminUser {
  id: string;
  email: string;
  role: "operator" | "reviewer" | "maintainer";
  status: "active" | "inactive";
}

export class AdminAuthError extends Error {}

const ACCESS_JWT_HEADER = "cf-access-jwt-assertion";

export async function requireAdmin(
  request: Request,
  db: D1Database,
  config: CloudflareEnv,
): Promise<AdminUser> {
  const identity = await verifyAccessIdentity(request, config);
  const admin = await findAdminUser(db, identity);

  if (!admin || admin.status !== "active") {
    throw new AdminAuthError("Authenticated user is not an active admin");
  }

  return admin;
}

export async function verifyAccessIdentity(
  request: Request,
  config: CloudflareEnv,
): Promise<AccessIdentity> {
  const token = request.headers.get(ACCESS_JWT_HEADER);
  if (!token) {
    throw new AdminAuthError("Missing Cloudflare Access JWT");
  }

  if (!config.CF_ACCESS_AUD || !config.CF_ACCESS_ISSUER) {
    throw new AdminAuthError("Cloudflare Access configuration is incomplete");
  }

  const jwksUrl = config.CF_ACCESS_JWKS_URL ?? `${config.CF_ACCESS_ISSUER}/cdn-cgi/access/certs`;
  const jwks = createRemoteJWKSet(new URL(jwksUrl));
  const { payload } = await jwtVerify(token, jwks, {
    audience: config.CF_ACCESS_AUD,
    issuer: config.CF_ACCESS_ISSUER,
  });

  if (!payload.sub || typeof payload.email !== "string") {
    throw new AdminAuthError("Cloudflare Access JWT is missing identity claims");
  }

  return {
    email: payload.email.toLowerCase(),
    subject: payload.sub,
  };
}

async function findAdminUser(
  db: D1Database,
  identity: AccessIdentity,
): Promise<AdminUser | null> {
  const admin = await db
    .prepare(
      `
        SELECT id, email, role, status
        FROM admin_users
        WHERE lower(email) = lower(?) OR access_subject_id = ?
        LIMIT 1
      `,
    )
    .bind(identity.email, identity.subject)
    .first<AdminUser>();

  if (!admin) {
    return null;
  }

  if (admin.email.toLowerCase() === identity.email) {
    await db
      .prepare(
        `
          UPDATE admin_users
          SET access_subject_id = COALESCE(access_subject_id, ?),
              last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
              updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
          WHERE id = ?
        `,
      )
      .bind(identity.subject, admin.id)
      .run();
  }

  return admin;
}
