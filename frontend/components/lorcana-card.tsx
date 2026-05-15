"use client";

import Image from "next/image";

export type LorcanaCardData = {
  id: string;
  name: string;
  subtitle?: string | null;
  set_id?: string | null;
  collector_number?: string | null;
  rarity?: string | null;
  image_url?: string | null;
  image_thumbnail_url?: string | null;
};

type LorcanaCardProps = {
  card: LorcanaCardData;
  size?: "sm" | "md" | "lg";
  showMeta?: boolean;
  priority?: boolean;
};

const sizeClasses = {
  sm: "w-[140px]",
  md: "w-[200px]",
  lg: "w-[260px]",
};

export function LorcanaCard({ card, size = "md", showMeta = true, priority = false }: LorcanaCardProps) {
  const imageSrc = card.image_url || card.image_thumbnail_url;

  return (
    <article className={`lorcana-card group ${sizeClasses[size]}`}>
      <div className="lorcana-card-frame">
        {imageSrc ? (
          <Image
            src={imageSrc}
            alt={card.name}
            fill
            sizes={size === "lg" ? "260px" : size === "md" ? "200px" : "140px"}
            className="lorcana-card-image"
            priority={priority}
            unoptimized
          />
        ) : (
          <div className="lorcana-card-placeholder">
            <span className="text-xs font-semibold uppercase tracking-wide text-[#9eb0e8]">Sin imagen</span>
            <span className="mt-2 text-center text-sm font-semibold text-[#e8ecff]">{card.name}</span>
          </div>
        )}
      </div>
      {showMeta ? (
        <div className="mt-2 space-y-0.5 px-0.5">
          <p className="truncate text-sm font-semibold text-[#eef2ff]" title={card.name}>
            {card.name}
          </p>
          <p className="truncate text-xs text-[#9eb0e8]">
            #{card.collector_number ?? "?"} · Set {card.set_id ?? "?"} · {card.rarity ?? "—"}
          </p>
        </div>
      ) : null}
    </article>
  );
}
