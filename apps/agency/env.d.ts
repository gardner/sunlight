interface CloudflareEnv {
  ASSETS: Fetcher;
  DB: D1Database;
  ARTIFACTS: R2Bucket;
}

declare module "cloudflare:workers" {
  export const env: CloudflareEnv;
}

declare module "next/navigation" {
  export function notFound(): never;
}
