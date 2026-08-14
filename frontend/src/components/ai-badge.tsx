import { Icon } from "@/components/icon";

export function AiRecommendedBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-coral-soft px-2.5 py-1 text-xs font-semibold text-coral">
      <Icon size={13} tone="gray" />
      Direkomendasikan AI
    </span>
  );
}
