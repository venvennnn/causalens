"use client";

import type { PipelineSource } from "@/lib/types";
import { cn } from "@/lib/utils";

function Dot({ health }: { health: string }) {
  const color =
    health === "FAILED" ? "bg-fail" : health === "DEGRADED" ? "bg-gold" : health === "HEALED" ? "bg-cyan" : "bg-ok";
  return <span className={cn("inline-block h-1.5 w-1.5 rounded-full", color)} />;
}

export function PipelineStrip({
  sources,
  gdeltHealth,
}: {
  sources: PipelineSource[];
  gdeltHealth: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line px-4 py-2">
      <div className="text-[10px] uppercase tracking-[0.22em] text-mist">Live web pipeline</div>
      {sources.map((source) => (
        <div key={source.source} className="flex items-center gap-2 font-mono text-[11px] text-fog">
          <span className="uppercase tracking-[0.12em] text-paper">{source.display_name}</span>
          <Dot health={source.health} />
          <span className="text-mist">{source.health}</span>
        </div>
      ))}
      <div className="flex items-center gap-2 font-mono text-[11px] text-fog">
        <span className="uppercase tracking-[0.12em] text-paper">GDELT</span>
        <Dot health={gdeltHealth} />
        <span className="text-mist">LIVE</span>
      </div>
    </div>
  );
}
