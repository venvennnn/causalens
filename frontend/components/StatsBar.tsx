"use client";

import type { GraphPayload } from "@/lib/types";

export function StatsBar({ payload }: { payload: GraphPayload | null }) {
  const stats = [
    [payload?.stats.articles ?? 0, "Articles"],
    [payload?.stats.events ?? 0, "Events"],
    [payload?.stats.connections ?? 0, "Connections"],
    [payload?.stats.cross_border ?? 0, "Cross-Border Ripples"],
  ] as const;
  return (
    <div className="grid grid-cols-4 border-b border-line">
      {stats.map(([value, label]) => (
        <div key={label} className="border-r border-line px-4 py-2 last:border-r-0">
          <div className="font-mono text-[18px] leading-none text-paper">{value}</div>
          <div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-mist">{label}</div>
        </div>
      ))}
    </div>
  );
}
