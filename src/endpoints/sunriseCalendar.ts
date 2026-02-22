import { OpenAPIRoute } from "chanfana";
import { z } from "zod";
import SunCalc from "suncalc";
import type { AppContext } from "../types";

// AIDEV-NOTE: iCal UTC timestamps must be formatted as YYYYMMDDTHHMMSSz (no dashes/colons, trailing Z)
function formatIcalDate(date: Date): string {
	return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

// AIDEV-NOTE: UIDs must be stable across calendar refreshes so Google Calendar doesn't duplicate events
function eventUid(type: "sunrise" | "sunset", date: Date, lat: number, lon: number): string {
	const d = date.toISOString().slice(0, 10).replace(/-/g, "");
	return `${type}-${d}-${lat}-${lon}@sunlight`;
}

// AIDEV-NOTE: suncalc returns NaN dates during polar night / midnight sun — always guard with isNaN check
function buildEvent(type: "sunrise" | "sunset", time: Date, label: string, date: Date, lat: number, lon: number): string | null {
	if (!time || isNaN(time.getTime())) return null;
	const end = new Date(time.getTime() + 60_000); // 1-minute duration for all-day-adjacent display
	return [
		"BEGIN:VEVENT",
		`DTSTART:${formatIcalDate(time)}`,
		`DTEND:${formatIcalDate(end)}`,
		`SUMMARY:${label}`,
		`UID:${eventUid(type, date, lat, lon)}`,
		"END:VEVENT",
	].join("\r\n");
}

export class SunriseCalendar extends OpenAPIRoute {
	schema = {
		tags: ["Calendar"],
		summary: "Sunrise & Sunset iCal Feed",
		description:
			"Returns an iCal calendar feed with sunrise and sunset events for the given location. " +
			"Subscribe to this URL in Google Calendar via Other Calendars > From URL.",
		request: {
			query: z.object({
				lat: z.coerce.number().min(-90).max(90).describe("Latitude (-90 to 90)"),
				lon: z.coerce.number().min(-180).max(180).describe("Longitude (-180 to 180)"),
			}),
		},
		responses: {
			"200": {
				description: "iCal calendar feed (text/calendar)",
				content: {
					"text/calendar": {
						schema: z.string(),
					},
				},
			},
		},
	};

	async handle(c: AppContext) {
		const data = await this.getValidatedData<typeof this.schema>();
		const { lat, lon } = data.query;

		// Generate events from 1 year ago through 2 years from now
		const now = new Date();
		const start = new Date(Date.UTC(now.getUTCFullYear() - 1, 0, 1));
		const end = new Date(Date.UTC(now.getUTCFullYear() + 2, 0, 1));

		const events: string[] = [];

		for (const d = new Date(start); d < end; d.setUTCDate(d.getUTCDate() + 1)) {
			const day = new Date(d); // snapshot before mutation
			const times = SunCalc.getTimes(day, lat, lon);

			const rise = buildEvent("sunrise", times.sunrise, "Sunrise", day, lat, lon);
			const set = buildEvent("sunset", times.sunset, "Sunset", day, lat, lon);

			if (rise) events.push(rise);
			if (set) events.push(set);
		}

		const calendar = [
			"BEGIN:VCALENDAR",
			"VERSION:2.0",
			"PRODID:-//Sunlight//Sunrise Calendar//EN",
			"CALSCALE:GREGORIAN",
			"METHOD:PUBLISH",
			`X-WR-CALNAME:Sunrise & Sunset (${lat}, ${lon})`,
			"X-WR-TIMEZONE:UTC",
			...events,
			"END:VCALENDAR",
		].join("\r\n");

		return new Response(calendar, {
			headers: {
				"Content-Type": "text/calendar; charset=utf-8",
				"Content-Disposition": `attachment; filename="sunrise-${lat}-${lon}.ics"`,
			},
		});
	}
}
