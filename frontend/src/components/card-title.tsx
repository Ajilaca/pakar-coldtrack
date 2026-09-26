import { ReactNode } from "react";
import type { Icon } from "@phosphor-icons/react";

export function CardTitle({ icon: I, children, aside }: { icon: Icon; children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="flex items-center gap-3 text-[18px] font-bold tracking-[-0.02em] text-brand-strong">
        <span className="flex size-9 items-center justify-center rounded-xl bg-tint text-accent">
          <I size={20} weight="bold" aria-hidden />
        </span>
        {children}
      </h2>
      {aside}
    </div>
  );
}
