# frontend/

Dasbor operator armada ColdTrack, dibangun dengan Next.js 14 (App Router), Tailwind, Recharts, dan
Leaflet. Data datang dari API backend (`/api/v1/fleet/*`, SSE `/stream`).

| Path | Isi |
|---|---|
| `src/app/(dashboard)/` | Halaman: Ringkasan (`page.tsx`), `kondisi`, `truk` (detail), `tindakan`, `kerugian`, `sensor`, `lokasi`, `simulasi` |
| `src/components/` | Komponen UI; komponen khusus armada di `fleet/` |
| `src/lib/` | Klien API dan utilitas |
| `design-system/coldtrack/` | Panduan desain (`MASTER.md`) dan catatan per halaman |
| `public/` | Aset statis |
| `Dockerfile`, `Dockerfile.dev` | Image produksi dan image dev dengan live reload |
| `FRONTEND_NOTES.md` | Catatan lama dari versi dasbor sebelumnya |

## Menjalankan

Cara paling mudah adalah lewat `docker compose` di root repo (lihat `README.md`). Untuk pengembangan lokal:

```bash
cd frontend
npm ci
npm run dev        # http://localhost:3000
npm run lint
npm run build
```

`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) dibaca saat `npm run build`, jadi harus sudah terisi
sebelum image dibangun.
