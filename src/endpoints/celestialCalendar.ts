import { OpenAPIRoute } from "chanfana";
import { z } from "zod";
import SunCalc from "suncalc";
import type { AppContext } from "../types";

// AIDEV-NOTE: Solstice/equinox times use the Meeus Table 27.a polynomial (Astronomical Algorithms,
// Chapter 27). Accuracy is ±5–15 min without the full periodic correction table — adequate for a
// calendar. JDE → Unix: (jde - 2440587.5) * 86_400_000. The ~69 s TT-UTC delta-T is ignored.

// AIDEV-NOTE: Moon phases are found by iterating daily over SunCalc.getMoonIllumination().phase
// (0 → 1 over one synodic month ≈ 29.53 days) and binary-searching each threshold crossing.
// New moon requires detecting the 1 → 0 wrap: prevPhase > 0.875 && currPhase < 0.125.

const DAY_MS = 86_400_000;

// ─── Seasons ──────────────────────────────────────────────────────────────────

// Meeus Table 27.a coefficients for Y = (year − 2000) / 1000
const SEASON_COEFFS: [number, number, number, number, number][] = [
	[2451623.80984, 365242.37404,  0.05169, -0.00411, -0.00057], // March equinox
	[2451716.56767, 365241.62603,  0.00325,  0.00888, -0.00030], // June solstice
	[2451810.21715, 365242.01767, -0.11575,  0.00337,  0.00078], // September equinox
	[2451900.05952, 365242.74049, -0.06223, -0.00823,  0.00032], // December solstice
];

const SEASON_NAMES = [
	"March Equinox",
	"June Solstice",
	"September Equinox",
	"December Solstice",
] as const;

function jdeToDate(jde: number): Date {
	return new Date((jde - 2440587.5) * DAY_MS);
}

function seasonJDE(year: number, season: 0 | 1 | 2 | 3): number {
	const Y = (year - 2000) / 1000;
	const [a, b, c, d, e] = SEASON_COEFFS[season];
	return a + b * Y + c * Y ** 2 + d * Y ** 3 + e * Y ** 4;
}

// ─── Cross-quarter days ───────────────────────────────────────────────────────

const CROSS_QUARTER_NAMES = ["Imbolc", "Beltane", "Lughnasadh", "Samhain"] as const;

// Each cross-quarter is the temporal midpoint between two adjacent season instants.
function crossQuarterDate(year: number, idx: 0 | 1 | 2 | 3): Date {
	const pairs: [number, number][] = [
		[seasonJDE(year - 1, 3), seasonJDE(year, 0)], // Dec solstice → March equinox
		[seasonJDE(year, 0),     seasonJDE(year, 1)], // March equinox → June solstice
		[seasonJDE(year, 1),     seasonJDE(year, 2)], // June solstice → Sept equinox
		[seasonJDE(year, 2),     seasonJDE(year, 3)], // Sept equinox → Dec solstice
	];
	const [j1, j2] = pairs[idx];
	return jdeToDate((j1 + j2) / 2);
}

// ─── Moon phases ──────────────────────────────────────────────────────────────

function binarySearchPhase(
	t1: number,
	t2: number,
	isBefore: (phase: number) => boolean,
): Date {
	let lo = t1, hi = t2;
	for (let i = 0; i < 30; i++) {
		const mid = (lo + hi) / 2;
		if (isBefore(SunCalc.getMoonIllumination(new Date(mid)).phase)) lo = mid;
		else hi = mid;
	}
	return new Date((lo + hi) / 2);
}

function findMoonPhases(start: Date, end: Date): Array<{ time: Date; name: string }> {
	const results: Array<{ time: Date; name: string }> = [];
	let prev = SunCalc.getMoonIllumination(start).phase;

	for (let t = start.getTime() + DAY_MS; t <= end.getTime(); t += DAY_MS) {
		const curr = SunCalc.getMoonIllumination(new Date(t)).phase;

		if (prev < 0.25 && curr >= 0.25)
			results.push({ time: binarySearchPhase(t - DAY_MS, t, p => p < 0.25), name: "First Quarter" });

		if (prev < 0.5 && curr >= 0.5)
			results.push({ time: binarySearchPhase(t - DAY_MS, t, p => p < 0.5), name: "Full Moon" });

		if (prev < 0.75 && curr >= 0.75)
			results.push({ time: binarySearchPhase(t - DAY_MS, t, p => p < 0.75), name: "Last Quarter" });

		// New moon: phase wraps from ~1 back to ~0
		if (prev > 0.875 && curr < 0.125)
			results.push({ time: binarySearchPhase(t - DAY_MS, t, p => p > 0.5), name: "New Moon" });

		prev = curr;
	}

	return results;
}

// ─── iCal helpers ─────────────────────────────────────────────────────────────

function toIcalUtc(date: Date): string {
	return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

function vevent(summary: string, time: Date, uid: string): string {
	const end = new Date(time.getTime() + 60_000); // 1-minute duration
	return [
		"BEGIN:VEVENT",
		`DTSTART:${toIcalUtc(time)}`,
		`DTEND:${toIcalUtc(end)}`,
		`SUMMARY:${summary}`,
		`UID:${uid}`,
		"END:VEVENT",
	].join("\r\n");
}

// ─── Endpoint ─────────────────────────────────────────────────────────────────

export class CelestialCalendar extends OpenAPIRoute {
	schema = {
		tags: ["Calendar"],
		summary: "Celestial Events iCal Feed",
		description:
			"Returns an iCal calendar feed with solstices, equinoxes, cross-quarter days " +
			"(Imbolc, Beltane, Lughnasadh, Samhain), and moon phases. " +
			"These are global events — no location required.",
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
		const now = new Date();
		const startYear = now.getUTCFullYear() - 1;
		const endYear = now.getUTCFullYear() + 2; // exclusive

		const start = new Date(Date.UTC(startYear, 0, 1));
		const end   = new Date(Date.UTC(endYear,   0, 1));

		const events: string[] = [];

		// Solstices, equinoxes, and cross-quarter days
		for (let year = startYear; year < endYear; year++) {
			for (let s = 0; s < 4; s++) {
				events.push(vevent(
					SEASON_NAMES[s],
					jdeToDate(seasonJDE(year, s as 0 | 1 | 2 | 3)),
					`season-${s}-${year}@sunlight`,
				));
			}

			for (let q = 0; q < 4; q++) {
				const time = crossQuarterDate(year, q as 0 | 1 | 2 | 3);
				if (time >= start && time < end) {
					events.push(vevent(
						CROSS_QUARTER_NAMES[q],
						time,
						`crossquarter-${q}-${year}@sunlight`,
					));
				}
			}
		}

		// Moon phases (iterate over full range)
		for (const { time, name } of findMoonPhases(start, end)) {
			const d = time.toISOString().slice(0, 10).replace(/-/g, "");
			events.push(vevent(name, time, `moon-${name.toLowerCase().replace(/\s+/g, "")}-${d}@sunlight`));
		}

		const calendar = [
			"BEGIN:VCALENDAR",
			"VERSION:2.0",
			"PRODID:-//Sunlight//Celestial Calendar//EN",
			"CALSCALE:GREGORIAN",
			"METHOD:PUBLISH",
			"X-WR-CALNAME:Celestial Events",
			...events,
			"END:VCALENDAR",
		].join("\r\n");

		return new Response(calendar, {
			headers: {
				"Content-Type": "text/calendar; charset=utf-8",
				"Content-Disposition": 'attachment; filename="celestial.ics"',
			},
		});
	}
}
