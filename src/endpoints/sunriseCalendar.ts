import { OpenAPIRoute } from "chanfana";
import { z } from "zod";
import SunCalc from "suncalc";
import type { AppContext } from "../types";

// AIDEV-NOTE: Express times in approximate local timezone (rounded from longitude) so events land
// on the correct calendar date in Google Calendar. Using UTC timestamps caused sunrise events for
// UTC+ locations (e.g. NZ UTC+12) to appear on the previous calendar day since their DTSTART
// would be in the evening of the prior UTC day (e.g. 19:32 UTC May 18 = 7:32 AM NZ May 19).
// The approximation (round(lon/15)) may be off by 1 hour during DST, but the day is always correct.

// AIDEV-NOTE: UIDs must be stable across calendar refreshes so Google Calendar doesn't duplicate events.
// UID date uses the local date (via the offset) so it matches the calendar day the event appears on.

// AIDEV-NOTE: suncalc returns NaN dates during polar night / midnight sun — always guard with isNaN check

function approxUtcOffsetHours(lon: number): number {
	return Math.round(lon / 15);
}

// Format a UTC Date as a local datetime string (YYYYMMDDTHHmmss) by applying the given hour offset
function formatLocalDate(utcDate: Date, offsetHours: number): string {
	const local = new Date(utcDate.getTime() + offsetHours * 3_600_000);
	return local.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "");
}

// Return the local YYYY-MM-DD for a UTC Date given an hour offset
function localDateString(utcDate: Date, offsetHours: number): string {
	const local = new Date(utcDate.getTime() + offsetHours * 3_600_000);
	return local.toISOString().slice(0, 10);
}

function eventUid(type: "sunrise" | "sunset", localDate: string, lat: number, lon: number): string {
	return `${type}-${localDate.replace(/-/g, "")}-${lat}-${lon}@sunlight`;
}

function buildEvent(
	type: "sunrise" | "sunset",
	time: Date,
	label: string,
	tzId: string,
	offsetHours: number,
	lat: number,
	lon: number,
): string | null {
	if (!time || isNaN(time.getTime())) return null;
	const end = new Date(time.getTime() + 60_000); // 1-minute duration
	const localDate = localDateString(time, offsetHours);
	return [
		"BEGIN:VEVENT",
		`DTSTART;TZID=${tzId}:${formatLocalDate(time, offsetHours)}`,
		`DTEND;TZID=${tzId}:${formatLocalDate(end, offsetHours)}`,
		`SUMMARY:${label}`,
		`UID:${eventUid(type, localDate, lat, lon)}`,
		"END:VEVENT",
	].join("\r\n");
}

function buildVtimezone(tzId: string, offsetHours: number): string {
	const sign = offsetHours >= 0 ? "+" : "-";
	const abs = Math.abs(offsetHours);
	const offset = `${sign}${String(abs).padStart(2, "0")}00`;
	return [
		"BEGIN:VTIMEZONE",
		`TZID:${tzId}`,
		"BEGIN:STANDARD",
		"DTSTART:16010101T000000",
		`TZOFFSETFROM:${offset}`,
		`TZOFFSETTO:${offset}`,
		`TZNAME:${tzId}`,
		"END:STANDARD",
		"END:VTIMEZONE",
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

		const offsetHours = approxUtcOffsetHours(lon);
		const sign = offsetHours >= 0 ? "+" : "-";
		const tzId = `UTC${sign}${String(Math.abs(offsetHours)).padStart(2, "0")}`;

		// Generate events from 1 year ago through 2 years from now
		const now = new Date();
		const start = new Date(Date.UTC(now.getUTCFullYear() - 1, 0, 1));
		const end = new Date(Date.UTC(now.getUTCFullYear() + 2, 0, 1));

		const events: string[] = [];

		for (const d = new Date(start); d < end; d.setUTCDate(d.getUTCDate() + 1)) {
			const day = new Date(d); // snapshot before mutation
			const times = SunCalc.getTimes(day, lat, lon);

			const rise = buildEvent("sunrise", times.sunrise, "Sunrise", tzId, offsetHours, lat, lon);
			const set = buildEvent("sunset", times.sunset, "Sunset", tzId, offsetHours, lat, lon);

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
			buildVtimezone(tzId, offsetHours),
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
