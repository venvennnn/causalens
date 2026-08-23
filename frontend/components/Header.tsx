"use client";

import { Badge } from "@/components/ui/badge";
import type { DataMode } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

export function Header({
  dataMode,
  cachedFrom,
}: {
  dataMode: DataMode | null;
  cachedFrom?: string | null;
}) {
  return (
    <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
      <div className="flex items-baseline gap-4">
        <div>
          <div className="text-[15px] font-semibold tracking-[0.28em] text-paper">CAUSALENS</div>
          <div className="text-[10px] tracking-[0.34em] text-gold">SOUTHEAST ASIA</div>
        </div>
        <div className="hidden text-[12px] text-mist md:block">Understand why the region moves.</div>
      </div>
      <div className="flex items-center gap-2">
        {dataMode === "LIVE" && <Badge tone="live">Live</Badge>}
        {dataMode === "PARTIAL" && <Badge tone="warn">Partial</Badge>}
        {dataMode === "CACHED" && (
          <Badge tone="cached">Cached — last refreshed {timeAgo(cachedFrom)}</Badge>
        )}
      </div>
    </header>
  );
}
