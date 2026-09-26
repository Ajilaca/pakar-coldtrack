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

## Scope (MVP rules + 26 Sep changes)

- Single page, one flow: **manual input → AI result**. No scenarios, no "Mode Demo" badge,
  no "Analisis Perjalanan" button, no login/user avatar, no date filters, no KPI board, no fleet list.
- Analysis runs **automatically**: 600ms after the last valid form change (debounced), the
  frontend builds the 60-reading window and calls `POST /api/v1/analyze`.

## Input Form (option 2 — current condition, window synthesized)

Backend needs >= 60 per-minute readings. The user enters the *current condition* once; the
frontend synthesizes the 60-minute window (`lib/window.ts`).

| Field | Control | Maps to | Default |
|---|---|---|---|
| ID pengiriman | text | `shipment_id` | `TRK-` + random |
| Jenis muatan | select (5 profiles, label from `config.yaml` name) | `cargo_profile` | vaksin_2_8C |
| Massa muatan (kg) | number | `mass_kg` | 1000 |
| Suhu muatan sekarang (°C) | number, step 0.1 | last `temp_c` | profile midpoint |
| Suhu muatan 60 menit lalu (°C) | number, step 0.1 | first `temp_c` (linear ramp) | = current |
| Suhu luar (°C) | number | `ambient_c` (constant) | 31 |
| Kelembapan luar (%) | number 0–100 | `humidity` (constant) | 75 |
| Pintu | toggle Tertutup/Terbuka + "sejak … menit" (1–60) | `door_open` true for last N rows | tertutup |
| Truk | toggle Bergerak/Berhenti + "sejak … menit" | `speed_kmh` 40 / 0 for last N rows | bergerak |

Window synthesis: 60 rows, `ts` = now − 59…0 min (absolute ISO, local tz), `temp_c` linear
from "60 menit lalu" to "sekarang" + ±0.05 °C noise, `reefer_on: true`, `harsh_events: 0`.
Show a small caption under the form: "Data 60 menit disusun dari kondisi yang diisi."

Validation inline per field (Indonesian), no request while invalid. Form state in `useState` only.

## Layout Overrides

12-column grid, max width 1440px, 24px page gutter. Fits 1366×768 without scrolling the result.

```
┌ Header: logo · "ColdTrack AI" · one-line positioning ───────────────────────────────┐
├ Input panel (col-4, sticky) ───┬ Result (col-8) ────────────────────────────────────┤
│ Pengiriman: ID · muatan · massa│ StatusHero: AMAN/WASPADA/KRITIS · TTB raksasa     │
│ Suhu: sekarang · 60 mnt lalu   │             · risk index · diagnosis + keyakinan  │
│ Lingkungan: suhu luar · RH     │ TemperatureChart (actual + t15/30/60 + profile band)│
│ Kondisi: pintu · truk (+ menit)│ TruckVisual (3D PNG + overlay labels)              │
│                                │ Actions (3 steps)   │ "Mengapa AI berpikir begini"  │
│ caption: window disusun otomatis│                    │ (3 drivers)                   │
├────────────────────────────────┴───────────────────────────────────────────────────┤
│ Footer: model_version · inference_ms · "alat bantu keputusan, bukan pengganti operator"│
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Responsive: <1024px input panel stacks above result.

## Result states

- Empty (form invalid/incomplete): muted placeholder "Isi kondisi muatan untuk melihat analisis".
- Loading: skeleton on result only; keep previous result visible dimmed if one exists.
- Error 400/422/network: inline alert in result area with message + "Coba lagi".

## Component Specs

**StatusHero** — status label with icon (AMAN/WASPADA/KRITIS, API wording), TTB as the largest
number on the page (48px Fira Code): "Muatan aman **23** menit lagi".
TTB rules follow the backend (`engine.py` CFG `ttb_tampil=60`): the frontend applies **no cap of
its own** — any non-null `time_to_breach_min` is shown as the big number, regardless of status
(drift projection can give a TTB while still AMAN). `null` → show "—" + "Tidak ada risiko pelanggaran dalam 60 menit" (AMAN) or status
text; diagnosis contains "sensor" → hide TTB, show "Sensor bermasalah — cek manual".
`ttb_model_min` shown only as small secondary text ("estimasi model: 95 mnt"), never as main number.
Risk index as number 0–1 + thin bar. Status tint only on a 3px left border + badge, not full card.

**Diagnosis labels (display text):** normal_sehat → "Normal", pintu_terbuka → "Pintu terbuka",
pintu_terbuka_lama → "Pintu terbuka terlalu lama", kejutan_ambien_ekstrem → "Kejut suhu luar ekstrem",
masalah_sensor → "Sensor bermasalah", suhu_muatan_mendekati_batas → "Suhu muatan mendekati batas".
Unknown label → humanize snake_case.

**TemperatureChart** — Recharts line. X = minutes (−60…+60). Actual = `--accent` solid 2px;
forecast points t15/t30/t60 joined by `--accent-soft` dashed line from the last actual point.
Profile safe band (min–max) shaded `--status-ok` 6%; `critical_temp_c` as 1px dashed red line
with inline label. No time-range filter. Visually hidden text summary.

**ActionSteps** — ordered list of 3, priority number + text + "± {eta_min} mnt" when not null.

**DriverList** — 3 rows: feature (humanized) · value · contribution as % + thin bar.

**TruckVisual (3D PNG, kept by product decision)** — the team's own 3D truck render, shown in
the result column next to StatusHero. Assets in `frontend/public/images/truck/`:

Image is chosen by **API result** (`status` + `failure_mode.label`), not by the form:

| Status | Label | File |
|---|---|---|
| AMAN | any | `normal.webp` |
| WASPADA / KRITIS | `pintu_terbuka`, `pintu_terbuka_lama` | `door-open-{yellow,red}.webp` |
| WASPADA / KRITIS | `kejutan_ambien_ekstrem` | `ambient-shock-{yellow,red}.webp` |
| WASPADA | `masalah_sensor` (backend locks WASPADA) | `sensor-fault-yellow.webp` |
| WASPADA / KRITIS | `suhu_muatan_mendekati_batas` or unknown label | `near-limit-{yellow,red}.webp` |

WASPADA → `yellow`, KRITIS → `red`. Status color is baked into these images (product decision),
so the overlay labels stay neutral and small.

Rules: transparent PNG/WebP, ~1200px wide, same camera angle and framing in every variant so
swapping does not jump; `next/image` with fixed width/height (no layout shift). Overlay labels (HTML):
"Pintu terbuka · 15 mnt", "Berhenti · 10 mnt", "Sensor bermasalah" when label has "sensor".
Overlay dots use status colors + text. Image is decorative (`alt=""`); overlay text carries meaning.

**Reefer — dropped from UI.** No reefer field in the form, no reefer text, icon, or overlay.
`reefer_on` is still required by the API, so the window builder always sends `true`. Driver
`durasi_reefer_aktif` or action text returned by the backend is shown as-is, but the UI adds no
reefer-specific copy, icons, or diagnosis mapping.

## Motion

- 150ms color/opacity transitions only. No scroll reveals on the dashboard.
- Live value update: brief 600ms background fade on the changed number, off under reduced motion.

## Anti-patterns (from the current mockup)

- Glowing red doors / red-tinted 3D (the 3D truck itself is kept — see TruckVisual)
- Giant red "CRITICAL" headline + red banner + red badges all at once
- Donut percentages for non-percentage data
- Scenario picker, "Mode Demo" badge, "Analisis Perjalanan" button, user avatar, time filters
- Icon in a tinted circle on every row
- All-caps micro labels on every field
