"use client";

import { Icon } from "@/components/icon";
import { cn } from "@/lib/utils";
import { Section } from "@/lib/section";

interface SidebarProps {
  activeSection: Section;
  onSectionChange: (section: Section) => void;
}

const NAV_ITEMS: { id: Section; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "shipment", label: "Shipments" },
  { id: "monitoring", label: "Real-time Monitoring" },
  { id: "route", label: "Route Tracking" },
  { id: "analytics", label: "Temperature Analytics" },
  { id: "prediction", label: "AI Prediction" },
];

export function Sidebar({ activeSection, onSectionChange }: SidebarProps) {
  return (
    <div className="frost-pattern flex h-full flex-col gap-1 rounded-3xl p-4 text-white" style={{ background: "linear-gradient(160deg, hsl(213 55% 18%) 0%, hsl(210 48% 11%) 100%)" }}>
      <div className="flex items-center gap-2.5 px-1 pb-5 pt-1">
        <div className="flex size-9 items-center justify-center rounded-xl bg-white/10">
          <Icon size={20} tone="white" />
        </div>
        <div>
          <p className="font-display text-[15px] font-bold leading-tight">ColdTrack</p>
          <p className="text-[10px] text-white/60 leading-tight">AI Logistics</p>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const active = activeSection === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSectionChange(item.id)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
                active ? "bg-brand text-white font-semibold shadow-frost" : "text-white/70 hover:bg-white/10 hover:text-white"
              )}
            >
              <Icon size={18} tone="white" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
