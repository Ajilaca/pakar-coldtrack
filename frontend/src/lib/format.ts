// Format tampilan armada. Waktu ditampilkan dalam WIB (zona armada, sama dengan fleet.zona_waktu di backend).

const ZONA = "Asia/Jakarta";

export function rupiah(n: number | null | undefined): string {
  if (n == null) return "—";
  const a = Math.abs(n);
  const f = (x: number, d = 1) => x.toLocaleString("id-ID", { maximumFractionDigits: d });
  if (a >= 1e12) return `Rp ${f(n / 1e12, 2)} T`;
  if (a >= 1e9) return `Rp ${f(n / 1e9, 2)} M`;
  if (a >= 1e6) return `Rp ${f(n / 1e6, 0)} jt`;
  if (a >= 1e3) return `Rp ${f(n / 1e3, 0)} rb`;
  return `Rp ${f(n, 0)}`;
}

export function jam(ts: string | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", timeZone: ZONA });
}

export function tanggalJam(ts: string | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("id-ID", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: ZONA,
  });
}

/** Selisih menit terhadap "sekarang" server (jam simulasi di dev), bukan jam browser. */
export function menitLalu(ts: string | null | undefined, now: string | null | undefined): number | null {
  if (!ts || !now) return null;
  return Math.max(0, Math.round((new Date(now).getTime() - new Date(ts).getTime()) / 60000));
}

export function relatif(ts: string | null | undefined, now: string | null | undefined): string {
  const m = menitLalu(ts, now);
  if (m == null) return jam(ts);
  if (m < 1) return "baru saja";
  if (m < 60) return `${m} mnt lalu`;
  if (m < 60 * 24) return `${Math.floor(m / 60)} jam lalu`;
  return `${Math.floor(m / 1440)} hari lalu`;
}

export function suhu(v: number | null | undefined, d = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d })} °C`;
}

export function angka(v: number | null | undefined, d = 0): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function persen(n: number, total: number): string {
  if (!total) return "0%";
  return `${((n / total) * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
}
