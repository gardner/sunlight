import { fromHono } from "chanfana";
import { Hono } from "hono";
import { CelestialCalendar } from "./endpoints/celestialCalendar";
import { SunriseCalendar } from "./endpoints/sunriseCalendar";

// Start a Hono app
const app = new Hono<{ Bindings: Env }>();

// Setup OpenAPI registry
const openapi = fromHono(app, {
	docs_url: "/",
});

// Register OpenAPI endpoints
openapi.get("/api/celestial", CelestialCalendar);
openapi.get("/api/sunrise", SunriseCalendar);

// Export the Hono app
export default app;
