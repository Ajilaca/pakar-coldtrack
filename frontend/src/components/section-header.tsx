interface SectionHeaderProps {
  title: string;
  subtitle: string;
  right?: React.ReactNode;
}

export function SectionHeader({ title, subtitle, right }: SectionHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-5">
      <div>
        <h2 className="font-display text-[26px] font-bold text-ink leading-tight">{title}</h2>
        <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
      </div>
      {right}
    </div>
  );
}
