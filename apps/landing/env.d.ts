interface CloudflareEnv {
  ASSETS: Fetcher;
  AI: Ai;
  FYI_VECTORS: Vectorize;
}

declare namespace Cloudflare {
  interface Env extends CloudflareEnv {}
}

declare module "cloudflare:workers" {
  export const env: CloudflareEnv;
}
