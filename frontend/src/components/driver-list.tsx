import { Lightbulb } from "@phosphor-icons/react/dist/ssr";
import { Driver } from "@/lib/types";
import { driverText, visibleDrivers } from "@/lib/labels";
import { CardTitle } from "./card-title";

export function DriverList({ drivers }: { drivers: Driver[] }) {
  const shown = visibleDrivers(drivers);
  return (
    <section className="card flex flex-col gap-4 p-5">
      <CardTitle icon={Lightbulb}>Mengapa AI berpikir begini</CardTitle>
      <ul className="flex flex-col gap-2.5">
        {shown.map((d) => {
          const pct = Math.round(d.contribution * 100);
          return (
            <li key={d.feature} className="tile flex flex-col gap-2">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-semibold text-brand-strong">{driverText(d.feature)}</span>
                <span className="num text-[15px] font-bold text-accent">{pct}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-tint" aria-hidden>
                <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-[12px] text-muted">{d.value}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
