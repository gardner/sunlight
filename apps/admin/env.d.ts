interface CloudflareEnv {
  ASSETS: Fetcher;
  DB: D1Database;
  EMAIL: SendEmail;
  ARTIFACTS: R2Bucket;
  CF_ACCESS_AUD?: string;
  CF_ACCESS_ISSUER?: string;
  CF_ACCESS_JWKS_URL?: string;
  SUNLIGHT_CONTACT_DETAILS?: string;
  SUNLIGHT_FROM_EMAIL?: string;
}

declare module "cloudflare:workers" {
  export const env: CloudflareEnv;
}

declare module "next/navigation" {
  export function notFound(): never;
  export function redirect(url: string): never;
  export function usePathname(): string;
}


declare module "next/headers" {
  export function headers(): Promise<Headers>;
}
