import { ShipmentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Batas di mana angka TTB masih layak ditampilkan sebagai angka.
 *
 * Dari audit R2 (role/update-r4-frontend.md): MAE model 3,30 menit untuk TTB
 * ≤ 10 menit dan 7,08 menit untuk ≤ 30 menit — tapi melonjak ke 52,00 menit di
 * seluruh rentang. Model ini andal sebagai alarm jangka pendek, TIDAK andal
 * sebagai hitung mundur jarak jauh. Di atas ambang ini kita hanya menyebut
 * status risikonya, tanpa angka, supaya tidak memberi kesan presisi palsu.
 *
 * Nilai yang sama ada di backend/config.yaml sebagai `ttb_display_cap_min`.
 */
const TTB_RELIABLE_MAX_MIN = 30;

interface TtbDisplayProps {
  status: ShipmentStatus;
  minutes: number | null;
  /** rata tengah — dipakai saat tampil di dalam blok status bergradien */
  centered?: boolean;
}

/**
 * Dirender DI ATAS BLOK GRADIEN. Warnanya tidak diatur di sini — wadahnya
 * memakai kelas `.on-gradient` (lihat globals.css) yang memaksa seluruh teks
 * di dalamnya jadi putih penuh. Menaruh `text-white` di sini justru TIDAK
 * bekerja: kelas skala tipografi menetapkan warnanya sendiri dan menang
 * karena urutan berkas hasil kompilasi.
 */
export function TtbDisplay({ status, minutes, centered = false }: TtbDisplayProps) {
  const align = centered ? "text-center" : "";

  if (status === "AMAN" || minutes === null) {
    return (
      <div className={cn("space-y-1", align)}>
        <p className="t-label">Time-to-Breach</p>
        <p className="t-metric">Tidak ada risiko breach</p>
        <p className="t-meta">Suhu diproyeksikan tetap di dalam ambang aman.</p>
      </div>
    );
  }

  // Di luar jangkauan andal — sebut risikonya, jangan sebut angkanya.
  if (minutes > TTB_RELIABLE_MAX_MIN) {
    return (
      <div className={cn("space-y-1", align)}>
        <p className="t-label">Time-to-Breach</p>
        <p className="t-metric">Lebih dari {TTB_RELIABLE_MAX_MIN} menit</p>
        <p className="t-meta">
          Model tidak menampilkan estimasi waktu spesifik di luar rentang ini.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-1", align)}>
      <p className="t-label">Time-to-Breach</p>
      <p className="t-hero">
        {minutes.toFixed(0)}
        <span className="t-hero-unit ml-1.5">menit</span>
      </p>
      <p className="t-meta">
        Muatan aman <span className="font-semibold">{minutes.toFixed(0)} menit</span> lagi sebelum ambang terlampaui.
      </p>
    </div>
  );
}
