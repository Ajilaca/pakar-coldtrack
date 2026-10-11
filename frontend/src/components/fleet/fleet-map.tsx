"use client";

// Peta armada (Leaflet). Dimuat lewat next/dynamic({ ssr: false }) karena Leaflet butuh window.
// Lingkaran = truk (warna status, abu-abu = offline); kotak = depo/hub (warna = status terburuk truk aktif).

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useRouter } from "next/navigation";
import { MapContainer, Marker, TileLayer, Tooltip } from "react-leaflet";
import { trukPath } from "@/lib/fleet-api";
import { Peta } from "@/lib/fleet-types";
import { tone } from "@/lib/fleet-status";

const JAWA: [number, number] = [-7.0, 109.6];

function ikon(warna: string, bentuk: "lingkaran" | "kotak", besar = 12) {
  const r = bentuk === "lingkaran" ? "50%" : "3px";
  return L.divIcon({
    className: "",
    html: `<span style="display:block;width:${besar}px;height:${besar}px;border-radius:${r};background:${warna};border:2px solid #fff;box-shadow:0 0 0 1px rgb(15 23 42/.25)"></span>`,
    iconSize: [besar, besar],
    iconAnchor: [besar / 2, besar / 2],
  });
}

export default function FleetMap({ peta, mini = false }: { peta: Peta; mini?: boolean }) {
  const router = useRouter();
  return (
    <MapContainer
      center={JAWA} zoom={mini ? 6 : 7} scrollWheelZoom={!mini} zoomControl={!mini} attributionControl
      className="size-full rounded-xl" style={{ minHeight: mini ? 220 : 420 }}
    >
      {/* Tile OpenStreetMap standar: tanpa API key (CARTO basemaps kini meminta key). Diabu-abukan lewat CSS
          (.peta-abu di globals.css) agar mirip peta Figma. Kebijakan tile OSM: pemakaian ringan + atribusi. */}
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
        className="peta-abu"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      {peta.depo.map((d) => (
        <Marker key={d.id} position={[d.lat, d.lon]} icon={ikon(d.status ? tone(d.status).dot : "#94a3b8", "kotak", mini ? 12 : 16)}>
          <Tooltip direction="top" offset={[0, -8]} permanent={!mini}>
            <span className="text-[12px] font-semibold">{d.kota}</span>
          </Tooltip>
        </Marker>
      ))}
      {peta.truk.filter((t) => t.lat != null && t.lon != null).map((t) => (
        <Marker
          key={t.truck_id} position={[t.lat!, t.lon!]} icon={ikon(tone(t.status).dot, "lingkaran", mini ? 9 : 12)}
          eventHandlers={{ click: () => router.push(trukPath(t.truck_id)) }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <span className="text-[12px]"><b>{t.truck_id}</b> · {tone(t.status).short}</span>
          </Tooltip>
        </Marker>
      ))}
    </MapContainer>
  );
}
