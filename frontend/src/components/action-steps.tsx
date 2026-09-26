import { ListChecks } from "@phosphor-icons/react/dist/ssr";
import { ActionStep } from "@/lib/types";
import { CardTitle } from "./card-title";

export function ActionSteps({ actions }: { actions: ActionStep[] }) {
  const sorted = [...actions].sort((a, b) => a.priority - b.priority);
  return (
    <section id="tindakan" className="card flex scroll-mt-6 flex-col gap-4 p-5">
      <CardTitle icon={ListChecks}>Langkah tindakan</CardTitle>
      <ol className="flex flex-col gap-2.5">
        {sorted.map((a) => (
          <li key={a.priority} className="tile flex items-start gap-3">
            <span className="icon-dot num size-9 text-[14px] font-bold">{a.priority}</span>
            <div className="min-w-0 pt-1">
              <p className="font-medium text-brand-strong">{a.text}</p>
              {a.eta_min != null && a.eta_min > 0 && (
                <p className="text-[12px] text-muted">
                  Perkiraan <span className="num">± {a.eta_min}</span> menit
                </p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
