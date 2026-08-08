interface DonutSegment {
  value: number;
  color: string;
}

interface DonutStatProps {
  segments: DonutSegment[];
  size?: number;
  centerValue?: string;
  centerLabel?: string;
  className?: string;
}

export function DonutStat({ segments, size = 112, centerValue, centerLabel, className }: DonutStatProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  let acc = 0;
  const stops = segments
    .map((s) => {
      const from = (acc / total) * 100;
      acc += s.value;
      const to = (acc / total) * 100;
      return `${s.color} ${from}% ${to}%`;
    })
    .join(", ");

  return (
    <div className={`relative shrink-0 ${className ?? ""}`} style={{ width: size, height: size }}>
      <div className="h-full w-full rounded-full" style={{ background: `conic-gradient(${stops})` }} />
      <div
        className="absolute rounded-full bg-card flex flex-col items-center justify-center"
        style={{ inset: size * 0.16 }}
      >
        {centerValue && <span className="font-display font-bold text-ink leading-tight" style={{ fontSize: size * 0.16 }}>{centerValue}</span>}
        {centerLabel && <span className="text-muted-foreground leading-tight" style={{ fontSize: size * 0.09 }}>{centerLabel}</span>}
      </div>
    </div>
  );
}
