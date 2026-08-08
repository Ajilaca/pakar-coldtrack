# Frontend — notes

Per your latest direction: this now matches `analisis_1620x1080px.pdf`
structurally and content-wise, section by section, rather than being
adapted to the single-shipment MVP scope. The role-context constraint
is still true of the actual submission (see `role context/context-r4-frontend.md`)
— this build treats that as a separate concern from what you asked for
here, not as something resolved. Worth a team conversation before this
is what ships as the judged demo app, since the two aren't the same
thing.

## What's in each section
- **Overview**: PDF's 5 KPI cards (fleet numbers are static/illustrative;
  "Vehicle ID" is live), the live temperature chart + route map for
  whichever scenario/CSV is selected, a fleet-wide prediction trend
  chart, and an AI Prediction summary panel.
- **Shipments**: PDF's exact 8-row table, search + status filter (filter
  is live, search is live — try typing an ID), 5 KPI cards, pagination
  footer.
- **Real-time Monitoring**: fleet temp chart, temperature distribution +
  sensor health donuts, live vehicle status table — all static/illustrative,
  matching the PDF's numbers.
- **Route Tracking**: active routes list, the dummy map, selected-route
  detail panel, full route status table — matching the PDF's Bandung→Malang
  example exactly (same distance, driver, stops).
- **Temperature Analytics**: compliance donut, temp-over-time + distribution
  charts, temperature-by-route table, violations donut.
- **AI Prediction**: risk distribution donut, 7-day prediction trend,
  top risk factors, upcoming high-risk predictions table, AI insights +
  recommendations.

All fleet-wide numbers live in `src/lib/fleet-data.ts` — static, mirrors
the PDF's own example values, clearly separate from the real analysis
engine (`lib/scenario-data.ts`, `lib/mock.ts`, `lib/api.ts`, all
untouched).

## Icons
Every icon slot — sidebar, KPI cards, map markers, buttons — renders
the same generic "missing image" glyph (`public/icons/placeholder-white.png`
and `placeholder-gray.png`, picked automatically by `<Icon tone="white|gray">`
depending on background). Nothing custom-illustrated this round, on
purpose: swap either PNG file directly, or point specific `<Icon>` calls
at your own per-slot images once you have them — the component in
`src/components/icon.tsx` is the only place that needs to change.

## Chart notes
Recharts' `Pie`/donut kept failing to render in this environment
whenever one segment dominated (rendered blank — a known SVG-arc edge
case, not a data problem). Replaced every donut with `components/donut-stat.tsx`,
a small pure-CSS conic-gradient version that doesn't have that failure
mode. If you add another donut anywhere, use that component rather
than recharts' `Pie`.

## Still dummy
The map (`components/dummy-map.tsx`) and all `fleet-data.ts` numbers are
illustrative, same as before — swap the map for Google Maps and the
fleet numbers for a real backend whenever those exist.

## Layout (latest round)
Every section is now sized to fit one viewport without a scrollbar
(desktop, ~1440x900) - KPI cards went to a compact horizontal style,
chart heights got tighter, and each panel uses `flex h-full flex-col`
with `flex-1 min-h-0` chart rows so content fills the available height
rather than overflowing. Every section carries two peer charts: one
tied to the selected Vehicle ID (live, changes when you switch scenarios
or import a CSV) and one fleet-wide (static, doesn't change) - that's
also why Real-time Monitoring no longer has the Live Vehicle Status
table; it traded that space for the second chart.

Background is a blue gradient (`coldship-bg` in globals.css) rather
than a flat tint, and the sidebar got a matching subtle dark-blue
gradient instead of flat navy.

One real bug fixed here: several line charts looked like they had
disconnected points near the end. That was recharts' default draw-in
animation, not a data issue - every `<Line>`/`<Bar>` now has
`isAnimationActive={false}` for deterministic rendering.
