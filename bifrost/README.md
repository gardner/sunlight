# Bifrost

This directory contains a repo-local copy of the Bifrost gateway config used for
LLM routing during local ingestion and eval work.

The provider keys live in `bifrost/.env`, which is intentionally ignored by git.
The committed `config.json` references provider keys and the virtual gateway key
through environment variables.

## Run

The copied `.env` defaults to port `8081` so it can run alongside the older
`pdf-to-podcast-bifrost-1` container currently bound to `8080`.

The `bifrost/data` directory is kept in git with an empty placeholder so the
Bifrost image's UID 1000 process can write logs and local SQLite state without
Docker creating the host bind mount as root.

```sh
docker compose -f bifrost/docker-compose.yml --env-file bifrost/.env up -d
```

Tail debug logs:

```sh
docker compose -f bifrost/docker-compose.yml --env-file bifrost/.env logs -f bifrost
```

Check models:

```sh
curl -s http://127.0.0.1:${BIFROST_HTTP_PORT:-8081}/v1/models
```

To replace the old `8080` gateway, stop the existing container first or set
`BIFROST_HTTP_PORT=8080` and `BIFROST_BASE_URL=http://localhost:8080/v1` in
`bifrost/.env`.

## Debugging Slow Fallbacks

Debug logging is enabled with `LOG_LEVEL=debug` and `LOG_STYLE=json`. Start by
comparing provider, model, HTTP status, duration, and fallback attempts in the
logs for the slow requests. The recent symptoms point at fallback/provider paths
that either return `413` quickly or stall until the gateway timeout, which can
make successful requests look much slower than the winning provider actually is.
