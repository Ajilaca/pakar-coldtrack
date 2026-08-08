import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Icon } from "@/components/icon";

export function PanelLoading({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-2xl" />
      ))}
    </div>
  );
}

export function ChartLoading() {
  return <Skeleton className="h-full w-full rounded-xl" />;
}

export function PanelError({ message }: { message: string }) {
  return (
    <Alert variant="destructive" className="rounded-2xl">
      <AlertTitle>Analisis gagal</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

export function PanelEmpty({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border py-16 text-center">
      <Icon size={40} tone="gray" className="opacity-40" />
      <p className="text-sm text-muted-foreground max-w-xs">{message}</p>
    </div>
  );
}
