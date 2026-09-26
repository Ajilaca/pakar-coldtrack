# Dashboard Page Overrides

> **PROJECT:** ColdTrack
> **Page Type:** Operational monitoring dashboard (single vehicle view)
> **Base:** Rules here override `../MASTER.md`. Anything not listed follows Master.

---

## Why these overrides

The generated Master is a landing-page pattern with a green accent. ColdTrack is an operations
console where color must carry *status*, so:

- Brand accent is the **Ocean/Teal palette** (cold chain), never green or red.
- Green / amber / red are reserved **only** for status (safe / warning / critical).
- ~90% of the UI is neutral slate. Red appears at most in 1–2 places per screen.

---

## Color Overrides

Light mode is the default (control-room screens are often bright); dark mode is paired.

**Brand palette (source of truth):**

| Name | Hex | Role |
|---|---|---|
| Snow | `#FEFCFB` | Light background |
| Ocean | `#034078` | Primary brand (buttons, links, active nav) |
| Navy | `#001F54` | Header / strong emphasis / dark elevated surface |
| Frost | `#88BFCF` | Soft accent: predicted band, highlights, dark-mode brand text |
| Teal | `#1282A2` | Data accent: actual-temperature line, focus ring, icons |
| Ink | `#0A1128` | Text (light) / background (dark) |

Contrast notes: Ocean on Snow ≈ 10:1 (any text). Teal on Snow ≈ 4.3:1 — **not** for small
text, only lines/icons/≥18px. Frost is never text on light surfaces. Frost on Ink ≈ 9:1.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#FEFCFB` | `#0A1128` | Page background |
| `--surface` | `#FFFFFF` | `#0F1A3A` | Cards |
| `--surface-muted` | `#EEF5F8` | `#001F54` | Inset areas, table header, header bar (dark) |
| `--border` | `#DCE7EC` | `#1C2A4F` | 1px card/divider |
| `--text` | `#0A1128` | `#FEFCFB` | Primary text |
| `--text-muted` | `#4A5670` | `#A9C6D2` | Labels, meta (passes 4.5:1) |
| `--brand` | `#034078` | `#88BFCF` | Primary button, links, active nav |
| `--brand-strong` | `#001F54` | `#FEFCFB` | Headings accent, pressed state |
| `--accent` | `#1282A2` | `#1282A2` | Chart actual line, focus ring, icons |
| `--accent-soft` | `#88BFCF` | `#88BFCF` | Predicted series, safe-band fill (low opacity) |
| `--status-ok` | `#15803D` | `#4ADE80` | Within range |
| `--status-warn` | `#B45309` | `#FBBF24` | Approaching limit |
| `--status-crit` | `#B91C1C` | `#F87171` | Out of range / action required |
| `--status-*-soft` | 8% tint of status | 15% tint | Badge/alert background only |

Rules:
- Status color is **always** paired with an icon + text label (never color alone).
- Status colors stay outside the blue palette on purpose — blues mean "brand/data", never "OK".
- Palette gradients (Frost→Teal, Navy→Ink) allowed **only** on login/empty-state hero, never on data cards.
- No glows or colored shadows. Elevation = 1px border + at most `0 1px 2px rgb(0 0 0 / .04)`.

## Typography Overrides

- UI: **Fira Sans** 400/500/600. Numbers & sensor values: **Fira Code** (tabular).
- Scale (px): 12 meta · 13 label · 14 body · 16 section title · 20 page title · 32 KPI value.
- Labels: sentence case, 13px, `--text-muted`. **No** all-caps labels everywhere.
- Max 2 weights per card.

## Spacing & Shape

- 4px base, dense scale: 4 · 8 · 12 · 16 · 24 · 32.
- Card padding 16–20px, grid gap 16px.
- Radius: 8px cards, 6px inputs/buttons, 999px badges only.
- Icons: Phosphor, regular weight, 16px inline / 20px headers. One icon per card header max.

## Layout Overrides

12-column grid, max width 1440px, 24px page gutter.

```
┌ Header: logo · vehicle selector · live status dot + "updated 12s ago" · bell · user ┐
├ AlertBar (only when crit/warn): icon · message · duration · [Acknowledge] [Details] ┤
├ KPI row (4 × col-3) ─────────────────────────────────────────────────────────────────┤
│ Cargo temp │ Rate of change │ Door status │ Time to limit                           │
├ Temperature chart (col-8) ──────────────────────┬ Side panel (col-4) ────────────────┤
│ actual line, predicted dashed, safe band shaded │ Diagnosis (cause + confidence)     │
│ 1h / 6h / 24h segmented control                 │ Cargo details (key–value list)     │
│                                                 │ Vehicle schematic (flat SVG)       │
└─────────────────────────────────────────────────┴────────────────────────────────────┘
```

Responsive: <1024px side panel stacks under chart; <768px KPI row becomes 2×2.

## Component Specs

**AlertBar** — single row, 48px tall, `--status-crit-soft` background, 3px left border in status
color. One primary action. Dismissable only via Acknowledge. `role="alert"` on first appearance.

**KpiCard** — label (13px muted) → value (32px Fira Code) + unit → delta/sparkline line.
Status shown by a small badge, not by coloring the whole card. No donut rings for non-proportions
(door status is a state, not a percentage).

**TemperatureChart** — Recharts line. Safe range as shaded band (`--status-ok` at 6%), limit as
1px dashed line with inline label. Actual = `--accent` solid 2px; predicted = `--accent-soft` dashed.
Gridlines `--border`. Tooltip shows time, value, status. Include a visually hidden summary.

**DiagnosisCard** — cause text, confidence as number + thin bar, recommended action as list.

**CargoPanel** — definition list (label / value), no per-row icons or boxes.

**VehicleSchematic** — flat top-down outline SVG, 1.5px stroke; sensors/doors as dots
colored by status with labels. Replaces the 3D truck render.

## Motion

- 150ms color/opacity transitions only. No scroll reveals on the dashboard.
- Live value update: brief 600ms background fade on the changed number, off under reduced motion.

## Anti-patterns (from the current mockup)

- 3D rendered truck hero, glowing red doors
- Giant red "CRITICAL" headline + red banner + red badges all at once
- Donut percentages for non-percentage data
- Icon in a tinted circle on every row
- All-caps micro labels on every field
