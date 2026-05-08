interface CloudflareEnv {
  ASSETS: Fetcher;
  DB: D1Database;
  ARTIFACTS: R2Bucket;
  R2_ACCESS_KEY_ID?: string;
  R2_ACCOUNT_ID?: string;
  R2_BUCKET_NAME?: string;
  R2_PRESIGN_EXPIRES_SECONDS?: string;
  R2_SECRET_ACCESS_KEY?: string;
}

declare module "cloudflare:workers" {
  export const env: CloudflareEnv;
}

declare module "next/navigation" {
  export function notFound(): never;
  export function redirect(url: string): never;
}
