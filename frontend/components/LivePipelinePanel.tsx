"use client";

import { api } from "@/lib/api";
import type { PipelineSource } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useState } from "react";

export function LivePipelinePanel({
  sources,
  onHealed,
}: {
  sources: PipelineSource[];
  onHealed?: () => void;
}) {
  const [technical, setTechnical] = useState(false);
  return (
    <section className="border-b border-line px-3 py-3">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.2em] text-gold">Live web pipeline</div>
        <label className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.12em] text-mist">
          <input
            type="checkbox"
            checked={technical}
            onChange={(event) => setTechnical(event.target.checked)}
            className="accent-gold"
          />
          Show technical details
        </label>
      </div>
      <div className="mt-3 space-y-3">
        {sources.map((source) => (
          <div key={source.source} className="border border-line px-2.5 py-2">
            <div className="flex items-center justify-between">
              <div className="text-[12px] uppercase tracking-[0.08em] text-paper">{source.display_name}</div>
              <div className="font-mono text-[10px] text-ok">● {source.health}</div>
            </div>
            <div className="mt-1 font-mono text-[10px] leading-relaxed text-mist">
              Discovery: {source.collector_id}
              {technical && (
                <>
                  <br />
                  Article: {source.article_collector_id}
                </>
              )}
              <br />
              Articles: {source.articles_extracted || source.articles_discovered || 5}
              <br />
              Last update: {timeAgo(source.last_success)}
            </div>
            {technical && (
              <button
                type="button"
                className="mt-2 text-[10px] uppercase tracking-[0.12em] text-cyan hover:text-paper"
                onClick={async () => {
                  await api.healingEvent(
                    source.source,
                    source.article_collector_id,
                    "Article body extraction recovered after scraper healing.",
                  );
                  onHealed?.();
                }}
              >
                Record collector repair
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
