import dynamic from "next/dynamic";
import { Muat } from "./ui";

/** Peta Leaflet tanpa SSR (Leaflet butuh window). */
export const FleetMap = dynamic(() => import("./fleet-map"), { ssr: false, loading: () => <Muat tinggi={240} /> });

export function LegendaPeta({ catatan = true }: { catatan?: boolean }) {
  const item = [
    ["Kritis", "var(--crit)"], ["Waspada", "var(--warn)"], ["Aman", "var(--ok)"], ["Offline", "var(--offline)"],
  ];
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
        {item.map(([n, w]) => (
          <li key={n} className="flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: w }} />{n}</li>
        ))}
      </ul>
      {catatan && (
        <p className="text-[11px] text-muted">Lingkaran = truk · Kotak = depo/hub (warna = status terburuk truk aktif di depo)</p>
      )}
    </div>
  );
}
