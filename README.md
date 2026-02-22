# sunlight

A Cloudflare Worker that serves subscribable iCal calendar feeds for astronomical events.

Live at **[cal.sunlight.nz](https://cal.sunlight.nz)** — Swagger UI available at the root.

## Endpoints

### `GET /api/sunrise?lat=&lon=`

Sunrise and sunset times for a given location, covering 1 year back through 2 years ahead.

Subscribe in Google Calendar via **Other Calendars → From URL**:
```
https://cal.sunlight.nz/api/sunrise?lat=-41.27&lon=173.28
```

Times are expressed in the approximate local timezone derived from the longitude (`round(lon / 15)` hours), so events always land on the correct calendar date. The approximation may be off by 1 hour during DST months, but the day is always right.

### `GET /api/celestial`

Global celestial events — no location required — covering the same 3-year window:

- **Solstices & equinoxes** (March, June, September, December) via the Meeus polynomial, accurate to ±5–15 minutes
- **Cross-quarter days** (Imbolc, Beltane, Lughnasadh, Samhain) computed as the temporal midpoint between adjacent season instants
- **Moon phases** (New Moon, First Quarter, Full Moon, Last Quarter) binary-searched to sub-millisecond precision using suncalc

```
https://cal.sunlight.nz/api/celestial
```

## Development

```bash
pnpm install
pnpm dev        # local dev server at http://localhost:8787
pnpm deploy     # deploy to Cloudflare Workers
```

## Stack

- [Cloudflare Workers](https://workers.cloudflare.com)
- [Hono](https://hono.dev) — web framework
- [Chanfana](https://chanfana.pages.dev) — OpenAPI 3.1 schema generation
- [suncalc](https://github.com/mourner/suncalc) — sun and moon position calculations
