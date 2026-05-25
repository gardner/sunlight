# Bifrost

This directory contains a repo-local copy of the Bifrost gateway config from
`/home/dev/src/bifrost/config.json`, used for LLM routing during local ingestion
and eval work.

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

Debug logging is enabled with `LOG_LEVEL=debug` and `LOG_STYLE=json`.

The copied routing rules are intentionally explicit:

- Tenancy enrichment should call `model: "nvidia/tenancy-regular"`. The
  `tenancy-regular` route currently splits that single model name across NVIDIA
  `regular` and OpenRouter `regular-openrouter`, with matching fallbacks.
- CEL uses `provider` and `model`, not `request.model`.
- Every routing rule has `scope: "global"`.
- OpenRouter targets use OpenRouter aliases such as `regular-openrouter`
  instead of carrying the incoming NVIDIA model alias.
- Fallbacks use `provider/model` values, such as
  `openrouter/regular-openrouter`, because bare provider names are ignored by
  Bifrost fallback parsing.

If you change `config.json`, reset the ignored local runtime DB before
restarting so Bifrost imports the file again:

```sh
docker compose -f bifrost/docker-compose.yml --env-file bifrost/.env down
rm -f bifrost/data/config.db*
docker compose -f bifrost/docker-compose.yml --env-file bifrost/.env up -d
```

Then compare provider, model, HTTP status, duration, and fallback attempts in
the logs for slow requests.
