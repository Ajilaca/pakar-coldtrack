"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChartLineUp, ListChecks, MapPin, Money, Play, SquaresFour, Thermometer, Truck,
} from "@phosphor-icons/react/dist/ssr";
import { useFleetCtx } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

export const NAV = [
  { href: "/", label: "Ringkasan", Icon: SquaresFour },
  { href: "/kondisi", label: "Kondisi", Icon: Thermometer },
  { href: "/lokasi", label: "Lokasi", Icon: MapPin },
  { href: "/sensor", label: "Sensor", Icon: ChartLineUp },
  { href: "/kerugian", label: "Kerugian", Icon: Money },
  { href: "/tindakan", label: "Tindakan", Icon: ListChecks },
  { href: "/simulasi", label: "Simulasi", Icon: Play },
];

function aktif(path: string, href: string) {
  if (href === "/") return path === "/";
  return path === href || path.startsWith(`${href}/`) || (href === "/kondisi" && path.startsWith("/truk/"));
}

export function Sidebar() {
  const path = usePathname() ?? "/";
  const { live } = useFleetCtx();
  return (
    <>
      {/* desktop */}
      <aside
        className="sticky top-0 hidden h-dvh w-[232px] shrink-0 flex-col gap-6 px-4 py-6 text-white lg:flex"
        style={{ background: "linear-gradient(180deg, var(--nav-from), var(--nav-to))" }}
      >
        <Link href="/" className="flex items-center gap-2.5 px-2">
          <Truck size={26} weight="fill" aria-hidden />
          <span className="text-[18px] font-bold tracking-[-0.02em]">ColdTrack AI</span>
        </Link>
        <nav aria-label="Navigasi utama" className="flex flex-col gap-1">
          {NAV.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={aktif(path, href) ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[14px] font-medium text-white/85 transition-colors hover:bg-white/10 hover:text-white",
                aktif(path, href) && "bg-[var(--nav-active)] text-white"
              )}
            >
              <Icon size={18} weight={aktif(path, href) ? "fill" : "regular"} aria-hidden />
              {label}
            </Link>
          ))}
        </nav>
        <p className="mt-auto flex items-center gap-2 px-2 text-[12px] text-white/75" role="status">
          <span className={cn("size-2 rounded-full", live ? "bg-emerald-300" : "bg-amber-300")} aria-hidden />
          {live ? "Terhubung langsung" : "Memuat ulang tiap 30 detik"}
        </p>
      </aside>

      {/* ponsel/tablet: bar atas + navigasi geser */}
      <div
        className="sticky top-0 z-30 flex flex-col gap-2 px-4 pb-2 pt-3 text-white lg:hidden"
        style={{ background: "linear-gradient(90deg, var(--nav-from), var(--nav-to))" }}
      >
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Truck size={20} weight="fill" aria-hidden />
            <span className="text-[16px] font-bold">ColdTrack AI</span>
          </Link>
          <span className={cn("size-2 rounded-full", live ? "bg-emerald-300" : "bg-amber-300")} aria-label={live ? "Terhubung langsung" : "Polling"} />
        </div>
        <nav aria-label="Navigasi utama" className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1">
          {NAV.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={aktif(path, href) ? "page" : undefined}
              className={cn(
                "flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] text-white/85",
                aktif(path, href) && "bg-[var(--nav-active)] text-white"
              )}
            >
              <Icon size={15} aria-hidden />
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </>
  );
}
