import Image from "next/image";
import { AnalyzeResponse, ConditionInput } from "@/lib/types";
import { isSensorFault, truckImage } from "@/lib/labels";

export function TruckVisual({ result, input }: { result: AnalyzeResponse; input: ConditionInput }) {
  const tags: string[] = [];
  if (input.doorOpen) tags.push(`Pintu terbuka · ${input.doorMinutes} mnt`);
  if (!input.moving) tags.push(`Berhenti · ${input.stoppedMinutes} mnt`);
  if (isSensorFault(result.failure_mode.label)) tags.push("Sensor bermasalah");

  return (
    <div className="relative">
      <div className="relative aspect-[4/3] w-full">
        <Image
          src={truckImage(result.status, result.failure_mode.label)}
          alt=""
          fill
          sizes="(min-width: 1280px) 560px, 100vw"
          className="object-contain mix-blend-multiply"
          priority
        />
      </div>
      {tags.length > 0 && (
        <ul className="absolute bottom-2 left-1/2 flex -translate-x-1/2 flex-wrap justify-center gap-1.5">
          {tags.map((t) => (
            <li key={t} className="rounded-full border bg-surface px-3 py-1 text-[12px] font-medium text-ink shadow-sm">
              {t}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
