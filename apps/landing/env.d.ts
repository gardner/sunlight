interface CloudflareEnv {
  ASSETS: Fetcher;
  AI: Ai;
  FYI_VECTORS: Vectorize;
  SEARCH_DB: D1Database;
}

declare namespace Cloudflare {
  interface Env extends CloudflareEnv {}
}

declare module "cloudflare:workers" {
  export const env: CloudflareEnv;
}
