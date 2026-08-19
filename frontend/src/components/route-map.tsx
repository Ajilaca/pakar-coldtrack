"use client";

import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from "react-leaflet";
import type { LatLngExpression, LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { ChartPoint, ShipmentStatus } from "@/lib/types";

const STATUS_COLOR: Record<ShipmentStatus, string> = {
  AMAN: "hsl(160 84% 30%)",
  WASPADA: "hsl(33 95% 45%)",
  KRITIS: "hsl(4 78% 52%)",
};

/** Menyesuaikan viewport peta setiap kali jejaknya berganti. */
function FitBounds({ bounds }: { bounds: LatLngBoundsExpression | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [26, 26] });
  }, [bounds, map]);
  return null;
}

export function RouteMap({ points, status }: { points: ChartPoint[]; status: ShipmentStatus }) {
  const track = useMemo(
    () =>
      points
        .filter((p) => typeof p.lat === "number" && typeof p.lon === "number")
        .map((p) => [p.lat as number, p.lon as number] as LatLngExpression),
    [points]
  );

  const bounds = useMemo<LatLngBoundsExpression | null>(() => {
    if (track.length < 2) return null;
    const lats = track.map((t) => (t as [number, number])[0]);
    const lons = track.map((t) => (t as [number, number])[1]);
    return [
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ];
  }, [track]);

  if (track.length < 2) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl bg-secondary/60 px-4 text-center">
        <p className="t-meta max-w-xs">
          Data ini tidak memuat koordinat, jadi rutenya tidak bisa dipetakan.
        </p>
      </div>
    );
  }

  const origin = track[0];
  const current = track[track.length - 1];
  const color = STATUS_COLOR[status];

  return (
    <div className="h-full w-full overflow-hidden rounded-2xl">
      <MapContainer
        center={origin}
        zoom={9}
        scrollWheelZoom={false}
        zoomControl={false}
        attributionControl
        className="h-full w-full"
        style={{ background: "hsl(var(--secondary))" }}
      >
        {/* Tile terang CARTO (turunan OpenStreetMap) agar menyatu dengan tema putih.
            CATATAN: tile diambil dari internet — kalau demo dijalankan tanpa
            koneksi, peta akan kosong sementara jejaknya tetap tergambar. */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          subdomains={["a", "b", "c", "d"]}
          maxZoom={19}
        />

        <FitBounds bounds={bounds} />

        {/* jejak yang sudah ditempuh */}
        <Polyline positions={track} pathOptions={{ color, weight: 4, opacity: 0.9 }} />

        {/* Warna literal, bukan var(): Leaflet memasang `fill` sebagai atribut
            SVG, dan atribut SVG tidak mengenal var(). */}
        <CircleMarker
          center={origin}
          radius={6}
          pathOptions={{ color: "#fff", weight: 2, fillColor: "#003B5C", fillOpacity: 1 }}
        >
          <Tooltip direction="top">Titik berangkat</Tooltip>
        </CircleMarker>

        <CircleMarker
          center={current}
          radius={8}
          pathOptions={{ color: "#fff", weight: 2, fillColor: color, fillOpacity: 1 }}
        >
          <Tooltip direction="top" permanent>
            Posisi terakhir · {status}
          </Tooltip>
        </CircleMarker>
      </MapContainer>
    </div>
  );
}

export default RouteMap;
