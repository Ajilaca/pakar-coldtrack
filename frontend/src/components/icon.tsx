import {
  Activity,
  BrainCircuit,
  Clock,
  DoorOpen,
  Flag,
  Gauge,
  Inbox,
  LayoutDashboard,
  ListChecks,
  MapPin,
  Package,
  Route,
  Search,
  ShieldCheck,
  Snowflake,
  Sparkles,
  Sun,
  Thermometer,
  TrendingUp,
  TriangleAlert,
  Truck,
  Upload,
  Wrench,
  OctagonAlert,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Satu-satunya tempat ikon dipilih. Sebelumnya semua slot merender PNG
 * placeholder yang sama; sekarang tiap slot menyebut `name` sendiri dan
 * dirender lewat lucide-react (sudah ada di package.json sejak awal).
 *
 * `tone` tetap dipertahankan supaya call site lama tidak perlu diubah —
 * bedanya sekarang dia mengatur warna teks SVG, bukan memilih berkas gambar.
 */
const ICONS = {
  // navigasi
  dashboard: LayoutDashboard,
  shipment: Package,
  monitoring: Activity,
  route: Route,
  analytics: Thermometer,
  prediction: BrainCircuit,
  // merek & aksi
  logo: Snowflake,
  upload: Upload,
  search: Search,
  ai: Sparkles,
  // peta
  origin: MapPin,
  destination: Flag,
  truck: Truck,
  // status
  safe: ShieldCheck,
  warning: TriangleAlert,
  critical: OctagonAlert,
  // data & penjelasan model
  rate: TrendingUp,        // laju kenaikan suhu
  ambient: Sun,            // selisih suhu ambien
  reefer: Snowflake,       // durasi unit pendingin aktif
  door: DoorOpen,          // status pintu kargo
  sensor: Gauge,           // pembacaan sensor
  duration: Clock,         // durasi / estimasi waktu
  repair: Wrench,          // kerusakan mekanis
  steps: ListChecks,       // daftar tindakan
  // keadaan kosong
  empty: Inbox,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

interface IconProps {
  name?: IconName;
  size?: number;
  className?: string;
  tone?: "white" | "gray";
}

export function Icon({ name = "truck", size = 20, className, tone = "gray" }: IconProps) {
  const Glyph = ICONS[name];
  return (
    <Glyph
      size={size}
      strokeWidth={2}
      aria-hidden
      className={cn("shrink-0 select-none", tone === "white" ? "text-white" : "text-muted-foreground", className)}
    />
  );
}
