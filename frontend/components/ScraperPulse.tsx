"use client";

import type { PipelineEvent, PipelineSource } from "@/lib/types";

function labelFor(kind: string): string {
  if (kind.includes("fail")) return "Validation degraded";
  if (kind.includes("repair") || kind.includes("heal")) return "Collector repaired";
  if (kind.includes("recover") || kind.includes("extraction_ok")) return "Extraction recovered";
  if (kind.includes("ok") || kind.includes("success") || kind.includes("seed")) return "Scrape succeeded";
  return kind.replaceAll("_", " ");
}

export function ScraperPulse({
  sources,
  events,
}: {
  sources: PipelineSource[];
  events: PipelineEvent[];
}) {
  return (
    <section className="px-3 py-3">
      <div className="text-[10px] uppercase tracking-[0.2em] text-gold">Scraper pulse</div>
      <div className="mt-3 space-y-1.5">
        {sources.map((source) => (
          <div key={source.source} className="flex items-center justify-between font-mono text-[11px]">
            <span className="text-fog">{source.display_name}</span>
            <span className="text-ok">{source.health}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-1.5 border-t border-line pt-3">
        {events.slice(0, 8).map((event) => {
          const hh = new Date(event.created_at).toLocaleTimeString("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
          });
          return (
            <div key={event.id} className="flex gap-2 font-mono text-[10px] text-mist">
              <span className="w-10 shrink-0 text-fog">{hh}</span>
              <span>{labelFor(event.kind)}</span>
            </div>
          );
        })}
        {events.length === 0 && (
          <div className="font-mono text-[10px] text-mist">No pipeline events recorded yet.</div>
        )}
      </div>
    </section>
  );
}
