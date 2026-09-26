export function Ring({ value, label, color = "var(--accent)" }: { value: number; label: string; color?: string }) {
  const r = 38;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className="relative size-[96px]">
      <svg viewBox="0 0 96 96" className="size-full -rotate-90" aria-hidden>
        <circle cx="48" cy="48" r={r} fill="none" stroke="var(--tint)" strokeWidth="9" />
        <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${c * v} ${c}`} />
      </svg>
      <span className="num absolute inset-0 flex items-center justify-center text-[20px] font-extrabold tracking-[-0.03em] text-brand-strong">
        {label}
      </span>
    </div>
  );
}
