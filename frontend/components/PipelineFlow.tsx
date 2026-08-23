"use client";

import type { PipelineStage } from "@/lib/types";
import { cn } from "@/lib/utils";

const STAGES: { id: PipelineStage; label: string }[] = [
  { id: "discover", label: "Discover" },
  { id: "extract", label: "Extract" },
  { id: "validate", label: "Validate" },
  { id: "events", label: "Events" },
  { id: "causal", label: "Causal graph" },
];

export function PipelineFlow({
  stage,
  statusLine,
}: {
  stage: PipelineStage;
  statusLine: string;
}) {
  const activeIndex = STAGES.findIndex((item) => item.id === stage);
  return (
    <div className="border-b border-line px-4 py-2.5">
      <div className="flex items-center gap-2 overflow-x-auto">
        {STAGES.map((item, index) => {
          const active = item.id === stage;
          const done = activeIndex > index && stage !== "idle";
          return (
            <div key={item.id} className="flex items-center gap-2">
              <div
                className={cn(
                  "rounded-sm border px-2 py-1 text-[10px] uppercase tracking-[0.16em]",
                  active && "border-gold text-gold",
                  done && "border-ok/40 text-ok",
                  !active && !done && "border-line text-mist",
                )}
              >
                {item.label}
              </div>
              {index < STAGES.length - 1 && <span className="text-mist">↓</span>}
            </div>
          );
        })}
      </div>
      {stage !== "idle" && (
        <div className="mt-1.5 font-mono text-[11px] text-cyan">{statusLine}</div>
      )}
    </div>
  );
}
