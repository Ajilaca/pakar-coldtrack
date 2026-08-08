// Presentation-only "flavor" data for the single-shipment dashboard shell.
// Deliberately kept OUT of lib/types.ts, which must stay in sync with R3's
// API contract — none of this is part of that contract. Route coordinates
// are an abstract 0-100 canvas for the placeholder map, not real geo data;
// swap for actual lat/lng once the Google Maps integration lands.

export interface RoutePoint {
  x: number; // 0-100, abstract map canvas
  y: number; // 0-100
}

export interface RouteInfo {
  origin: string;
  destination: string;
  distanceKm: number | null;
  durationMin: number | null;
  originPoint: RoutePoint;
  destPoint: RoutePoint;
  waypoint: RoutePoint;
}

export const VEHICLE_LABEL: Record<string, string> = {
  sehat: "B 1234 CCH",
  pintu_terbuka: "L 5678 CCH",
  kompresor_melemah: "D 3344 ZZ",
  sensor_macet: "BK 1122 CC",
  kejut_suhu_ambien: "AB 7788 YY",
};

export const ROUTE_INFO: Record<string, RouteInfo> = {
  sehat: {
    origin: "Bandung",
    destination: "Yogyakarta",
    distanceKm: 370,
    durationMin: 450,
    originPoint: { x: 22, y: 62 },
    destPoint: { x: 78, y: 58 },
    waypoint: { x: 50, y: 40 },
  },
  pintu_terbuka: {
    origin: "Jakarta",
    destination: "Bandung",
    distanceKm: 150,
    durationMin: 180,
    originPoint: { x: 18, y: 30 },
    destPoint: { x: 74, y: 70 },
    waypoint: { x: 45, y: 60 },
  },
  kompresor_melemah: {
    origin: "Surabaya",
    destination: "Malang",
    distanceKm: 95,
    durationMin: 150,
    originPoint: { x: 26, y: 32 },
    destPoint: { x: 68, y: 78 },
    waypoint: { x: 52, y: 48 },
  },
  sensor_macet: {
    origin: "Semarang",
    destination: "Solo",
    distanceKm: 105,
    durationMin: 150,
    originPoint: { x: 24, y: 28 },
    destPoint: { x: 76, y: 66 },
    waypoint: { x: 55, y: 34 },
  },
  kejut_suhu_ambien: {
    origin: "Jakarta",
    destination: "Bandung (via Puncak)",
    distanceKm: 130,
    durationMin: 240,
    originPoint: { x: 16, y: 26 },
    destPoint: { x: 80, y: 72 },
    waypoint: { x: 46, y: 66 },
  },
};

export const CUSTOM_ROUTE: RouteInfo = {
  origin: "Tidak diketahui",
  destination: "Tidak diketahui",
  distanceKm: null,
  durationMin: null,
  originPoint: { x: 25, y: 55 },
  destPoint: { x: 75, y: 45 },
  waypoint: { x: 50, y: 30 },
};

export function getVehicleLabel(scenarioId: string | null): string {
  if (scenarioId && VEHICLE_LABEL[scenarioId]) return VEHICLE_LABEL[scenarioId];
  return "CUSTOM-01";
}

export function getRouteInfo(scenarioId: string | null): RouteInfo {
  if (scenarioId && ROUTE_INFO[scenarioId]) return ROUTE_INFO[scenarioId];
  return CUSTOM_ROUTE;
}
