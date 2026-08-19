import { Icon } from "@/components/icon";

export function AiRecommendedBadge() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-coral-soft px-2 py-0.5 t-pill text-coral">
      <Icon name="ai" size={11} className="text-coral" />
      AI
    </span>
  );
}
