"use client";

import { useEffect, useId, useState } from "react";
import { cn } from "@/lib/utils";

interface ProgressRingProps {
  /** 0..1 */
  value: number;
  size?: number;
  stroke?: number;
  /** teks di tengah cincin; default persentase */
  label?: string;
  className?: string;
}

/**
 * Cincin persentase. Digambar dengan SVG stroke-dasharray, bukan
 * conic-gradient, supaya ujung garisnya bisa dibulatkan dan nilainya bisa
 * dianimasikan.
 *
 * Cincin diisi dari 0 ke nilai aslinya saat pertama muncul — itu yang
 * membuat kartu hasil terasa "dihitung", bukan sekadar tercetak.
 */
export function ProgressRing({ value, size = 76, stroke = 7, label, className }: ProgressRingProps) {
  const gradientId = useId();
  const pct = Math.max(0, Math.min(1, value));
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;

  // Mulai dari 0 lalu naik ke nilai sebenarnya setelah terpasang.
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const t = requestAnimationFrame(() => setShown(pct));
    return () => cancelAnimationFrame(t);
  }, [pct]);

  return (
    <div className={cn("relative shrink-0", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="hsl(var(--ocean-deep))" />
            <stop offset="100%" stopColor="hsl(var(--ocean-light))" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="hsl(var(--secondary))"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - shown)}
          style={{ transition: "stroke-dashoffset 900ms cubic-bezier(0.22, 1, 0.36, 1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="t-metric tabular" style={{ fontSize: Math.round(size * 0.26) }}>
          {label ?? `${Math.round(pct * 100)}%`}
        </span>
      </div>
    </div>
  );
}
