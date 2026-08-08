// Fleet-wide illustrative data — mirrors the numbers/rows shown in the
// reference PDF as closely as possible. This is presentation-only mock
// data (no fleet backend exists), kept separate from lib/types.ts (the
// real API contract) and from the live single-shipment analysis engine
// in lib/scenario-data.ts / lib/mock.ts.

export interface FleetShipment {
  id: string;
  route: string;
  vehicleId: string;
  status: "In Transit" | "Delivered" | "In Warehouse" | "Delayed";
  product: string;
  quantity: string;
  tempRange: string;
  eta: string;
}

export const SHIPMENT_STATS = {
  total: { value: 128, delta: "+12%" },
  inTransit: { value: 72, delta: "+8%" },
  delivered: { value: 42, delta: "+15%" },
  inWarehouse: { value: 10, delta: "-5%" },
  delayed: { value: 4, delta: "-20%" },
};

export const SHIPMENTS: FleetShipment[] = [
  { id: "SHP-20260722-001", route: "Bandung → Malang", vehicleId: "B 1234 CCH", status: "In Transit", product: "Meat", quantity: "500 kg", tempRange: "-2°C to 2°C", eta: "22 Jul, 14:30" },
  { id: "SHP-20260722-002", route: "Surabaya → Denpasar", vehicleId: "L 5678 CCH", status: "In Transit", product: "Seafood", quantity: "200 kg", tempRange: "-2°C to 2°C", eta: "22 Jul, 16:20" },
  { id: "SHP-20260722-003", route: "Jakarta → Semarang", vehicleId: "B 9876 XY", status: "Delivered", product: "Dairy", quantity: "200 kg", tempRange: "2°C to 8°C", eta: "22 Jul, 09:15" },
  { id: "SHP-20260722-004", route: "Medan → Pekanbaru", vehicleId: "BK 1122 CC", status: "In Warehouse", product: "Meat", quantity: "150 kg", tempRange: "-2°C to 2°C", eta: "\u2014" },
  { id: "SHP-20260722-005", route: "Makassar → Kendari", vehicleId: "DD 3344 ZZ", status: "Delayed", product: "Seafood", quantity: "250 kg", tempRange: "-2°C to 2°C", eta: "22 Jul, 18:45" },
  { id: "SHP-20260722-006", route: "Bandung → Jakarta", vehicleId: "B 5666 CCH", status: "In Transit", product: "Dairy", quantity: "100 kg", tempRange: "2°C to 8°C", eta: "22 Jul, 12:00" },
  { id: "SHP-20260722-007", route: "Yogyakarta → Solo", vehicleId: "AB 7788 YY", status: "Delivered", product: "Meat", quantity: "80 kg", tempRange: "-2°C to 2°C", eta: "22 Jul, 08:30" },
  { id: "SHP-20260722-008", route: "Balikpapan → Samarinda", vehicleId: "KT 8899 HH", status: "In Transit", product: "Seafood", quantity: "120 kg", tempRange: "-2°C to 2°C", eta: "22 Jul, 15:10" },
];

export const MONITORING_STATS = {
  monitoredVehicles: 32,
  activeShipments: 128,
  withinRange: { value: 28, pct: 87.5 },
  deviations: { value: 3, pct: 9.4 },
  criticalAlerts: { value: 1, pct: 3.1 },
  sensorHealthy: 96,
};

export interface LiveVehicle {
  vehicleId: string;
  route: string;
  shipmentId: string;
  temp: string;
  setPoint: string;
  status: "In Transit" | "Warning" | "Critical" | "In Warehouse";
}

export const LIVE_VEHICLES: LiveVehicle[] = [
  { vehicleId: "B 1234 CCH", route: "Bandung → Malang", shipmentId: "SHP-20260722-001", temp: "2.4°C", setPoint: "2°C", status: "In Transit" },
  { vehicleId: "L 5678 CCH", route: "Surabaya → Denpasar", shipmentId: "SHP-20260722-002", temp: "9.1°C ↑", setPoint: "2°C", status: "Warning" },
  { vehicleId: "BK 1122 CC", route: "Medan → Pekanbaru", shipmentId: "SHP-20260722-004", temp: "11.3°C ↑", setPoint: "2°C", status: "Critical" },
  { vehicleId: "B 9876 XY", route: "Jakarta → Semarang", shipmentId: "SHP-20260722-003", temp: "3.2°C", setPoint: "2°C", status: "In Transit" },
  { vehicleId: "DD 3344 ZZ", route: "Makassar → Kendari", shipmentId: "SHP-20260722-005", temp: "-1.8°C", setPoint: "-2°C", status: "In Warehouse" },
];

export const ROUTE_STATS = {
  activeRoutes: 12,
  totalDistanceKm: 1248,
  onTimePct: 83.3,
  onTimeRatio: "10 of 12",
  delayed: 2,
  completed: 5,
};

export interface FleetRoute {
  route: string;
  shipmentId: string;
  vehicleId: string;
  status: "In Transit" | "Delayed" | "In Warehouse";
  distanceRemaining: string;
  eta: string;
  progressPct: number;
  temp: string;
  tempTone: "normal" | "high";
}

export const ROUTES: FleetRoute[] = [
  { route: "Bandung → Malang", shipmentId: "SHP-20260722-001", vehicleId: "B 1234 CCH", status: "In Transit", distanceRemaining: "124 km remaining", eta: "14:30 WIB", progressPct: 75, temp: "2.4°C", tempTone: "normal" },
  { route: "Surabaya → Denpasar", shipmentId: "SHP-20260722-002", vehicleId: "L 5678 CCH", status: "In Transit", distanceRemaining: "358 km remaining", eta: "16:20 WIB", progressPct: 60, temp: "2.1°C", tempTone: "normal" },
  { route: "Jakarta → Semarang", shipmentId: "SHP-20260722-003", vehicleId: "B 9876 XY", status: "In Transit", distanceRemaining: "62 km remaining", eta: "09:15 WIB", progressPct: 90, temp: "3.2°C", tempTone: "normal" },
  { route: "Makassar → Kendari", shipmentId: "SHP-20260722-005", vehicleId: "DD 3344 ZZ", status: "Delayed", distanceRemaining: "210 km remaining", eta: "18:45 WIB", progressPct: 45, temp: "6.1°C", tempTone: "high" },
  { route: "Balikpapan → Samarinda", shipmentId: "SHP-20260722-008", vehicleId: "KT 8899 HH", status: "In Warehouse", distanceRemaining: "0 km remaining", eta: "\u2014", progressPct: 0, temp: "1.8°C", tempTone: "normal" },
];

export const SELECTED_ROUTE_DETAIL = {
  route: "Bandung → Malang",
  origin: "Bandung",
  destination: "Malang",
  shipmentId: "SHP-20260722-001",
  vehicleId: "B 1234 CCH",
  driver: "Andi Setiawan",
  distanceKm: 248,
  eta: "22 Jul 2026, 14:30 WIB",
  progressPct: 75,
  temp: "2.4°C",
  originPoint: { x: 22, y: 30 },
  waypoint: { x: 55, y: 42 },
  destPoint: { x: 68, y: 78 },
  stops: [
    { name: "Bandung", time: "22 Jul, 06:30 WIB", state: "Departed" as const },
    { name: "Cirebon", time: "22 Jul, 08:05 WIB", state: "Departed" as const },
    { name: "Semarang", time: "22 Jul, 10:45 WIB", state: "In Progress" as const },
    { name: "Malang", time: "22 Jul, 14:30 WIB", state: "ETA" as const },
  ],
};

export const TEMP_ANALYTICS_STATS = {
  compliance: { compliant: 90.2, minor: 7.2, major: 2.6 },
  totalShipments: 128,
  monitoredVehicles: 32,
  avgTemp: 2.4,
  tempAlerts: 6,
};

export interface RouteTempRow {
  route: string;
  avgTemp: string;
  compliance: string;
  trend: "up" | "down" | "flat";
}

export const TEMP_BY_ROUTE: RouteTempRow[] = [
  { route: "Bandung → Malang", avgTemp: "2.3°C", compliance: "96%", trend: "up" },
  { route: "Surabaya → Denpasar", avgTemp: "2.1°C", compliance: "92%", trend: "up" },
  { route: "Jakarta → Semarang", avgTemp: "2.6°C", compliance: "90%", trend: "flat" },
  { route: "Medan → Pekanbaru", avgTemp: "1.8°C", compliance: "88%", trend: "down" },
  { route: "Makassar → Kendari", avgTemp: "2.7°C", compliance: "86%", trend: "down" },
  { route: "Balikpapan → Samarinda", avgTemp: "1.5°C", compliance: "80%", trend: "down" },
];

export const TEMP_DISTRIBUTION = [
  { label: "< -8°C", compliant: 0, minor: 0, major: 1 },
  { label: "-8°C to -2°C", compliant: 22, minor: 4, major: 1 },
  { label: "-2°C to 2°C", compliant: 46, minor: 6, major: 0 },
  { label: "2°C to 8°C", compliant: 10, minor: 2, major: 0 },
  { label: "8°C to 15°C", compliant: 0, minor: 1, major: 0 },
  { label: "> 15°C", compliant: 0, minor: 0, major: 1 },
];

export const TEMP_VIOLATIONS = {
  total: 23,
  minor: { value: 19, pct: 82.6 },
  major: { value: 3, pct: 13.0 },
  beyondLimit: { value: 1, pct: 4.3 },
};

export const PREDICTION_STATS = {
  totalPredictions: { value: 156, delta: "+18.4%" },
  highRiskShipments: { value: 14, delta: "+12.5%" },
  predictedTempViolations: { value: 27, delta: "-8.3%" },
  predictedDelays: { value: 19, delta: "+15.7%" },
  predictionAccuracy: { value: 92.6, delta: "+2.8%" },
};

export const RISK_DISTRIBUTION = {
  low: { value: 68, pct: 43.6 },
  medium: { value: 74, pct: 47.4 },
  high: { value: 14, pct: 9.0 },
  total: 156,
};

export const PREDICTION_TREND_DAYS = ["16 Jul", "17 Jul", "18 Jul", "19 Jul", "20 Jul", "21 Jul", "22 Jul"];
export const PREDICTION_TREND = [
  { day: "16 Jul", highRisk: 8, tempViolation: 28, delay: 16 },
  { day: "17 Jul", highRisk: 9, tempViolation: 30, delay: 18 },
  { day: "18 Jul", highRisk: 7, tempViolation: 27, delay: 20 },
  { day: "19 Jul", highRisk: 10, tempViolation: 29, delay: 19 },
  { day: "20 Jul", highRisk: 8, tempViolation: 31, delay: 21 },
  { day: "21 Jul", highRisk: 9, tempViolation: 30, delay: 23 },
  { day: "22 Jul", highRisk: 14, tempViolation: 27, delay: 19 },
];

export const TOP_RISK_FACTORS = [
  { label: "High Ambient Temperature", pct: 32 },
  { label: "Traffic Congestion", pct: 24 },
  { label: "Long Distance", pct: 18 },
  { label: "Frequent Door Opening", pct: 12 },
  { label: "Route Deviation", pct: 8 },
  { label: "Others", pct: 6 },
];

export interface RiskPrediction {
  shipmentId: string;
  route: string;
  type: "Temperature Violation" | "Delay";
  risk: "High" | "Medium";
  probabilityPct: number;
  predictedIssue: string;
  predictedTime: string;
}

export const HIGH_RISK_PREDICTIONS: RiskPrediction[] = [
  { shipmentId: "SHP-20260722-005", route: "Makassar → Kendari", type: "Temperature Violation", risk: "High", probabilityPct: 87, predictedIssue: "Temperature may exceed 8°C", predictedTime: "23 Jul 2026, 14:30 WIB" },
  { shipmentId: "SHP-20260722-002", route: "Surabaya → Denpasar", type: "Delay", risk: "High", probabilityPct: 76, predictedIssue: "ETA delay > 45 min", predictedTime: "22 Jul 2026, 17:05 WIB" },
  { shipmentId: "SHP-20260722-007", route: "Yogyakarta → Solo", type: "Temperature Violation", risk: "Medium", probabilityPct: 65, predictedIssue: "Temperature may exceed 8°C", predictedTime: "22 Jul 2026, 12:20 WIB" },
  { shipmentId: "SHP-20260722-003", route: "Jakarta → Semarang", type: "Delay", risk: "Medium", probabilityPct: 61, predictedIssue: "ETA delay > 30 min", predictedTime: "22 Jul 2026, 11:45 WIB" },
  { shipmentId: "SHP-20260722-010", route: "Bandung → Malang", type: "Temperature Violation", risk: "Medium", probabilityPct: 58, predictedIssue: "Temperature may exceed 8°C", predictedTime: "22 Jul 2026, 13:10 WIB" },
];

export const AI_RECOMMENDATIONS = [
  "Consider pre-cooling vehicles before long routes.",
  "Avoid peak traffic hours on the Surabaya \u2013 Denpasar route.",
  "Monitor shipments SHP-20260722-005 and SHP-20260722-002 closely.",
  "Optimize loading to reduce door opening frequency.",
];

export const AI_INSIGHT =
  "Based on historical data and real-time conditions, shipments are most likely to experience temperature violations between 12:00\u201316:00 WIB due to high ambient temperature.";
