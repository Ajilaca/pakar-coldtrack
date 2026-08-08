import Image from "next/image";
import { cn } from "@/lib/utils";

interface IconProps {
  size?: number;
  className?: string;
  tone?: "white" | "gray";
}

/**
 * Every symbolic glyph in this dashboard renders through this component —
 * always the same generic placeholder image (never a custom illustration,
 * never an icon-font component) so it's unmistakable which spots are
 * meant to be swapped with real artwork later. Same file everywhere;
 * `tone` just picks the white or gray version to match the background.
 */
export function Icon({ size = 20, className, tone = "gray" }: IconProps) {
  return (
    <Image
      src={tone === "white" ? "/icons/placeholder-white.png" : "/icons/placeholder-gray.png"}
      alt=""
      width={size}
      height={size}
      className={cn("shrink-0 select-none", className)}
      unoptimized
    />
  );
}
