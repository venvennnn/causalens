import { Handle, Position, type NodeProps } from "@xyflow/react";
import { countryMeta, primaryCountry } from "@/lib/countries";
import { evidencePct, formatShortDate } from "@/lib/utils";
import { cn } from "@/lib/utils";

export type EventNodePayload = {
  id: string;
  title: string;
  summary: string;
  event_date?: string | null;
  countries: string[];
  companies: string[];
  industries: string[];
  source_article_ids: string[];
  confidence: number;
  event_type: string;
  evidence: number;
  sources: number;
  dimmed?: boolean;
  active?: boolean;
  predicted?: boolean;
};

export function EventNode({ data }: NodeProps) {
  const payload = data as unknown as EventNodePayload;
  const country = primaryCountry(payload.countries);
  const meta = countryMeta(country);
  const pct = evidencePct(payload.evidence);

  return (
    <div
      className={cn(
        "w-[248px] rounded-sm border bg-panel shadow-[0_0_0_1px_rgba(255,255,255,0.02)] transition-all",
        payload.active ? "border-gold/80 shadow-[0_0_0_1px_rgba(196,163,90,0.35)]" : "border-line",
        payload.predicted && "border-dashed border-mist/50",
        payload.dimmed && "opacity-25",
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-line !bg-gold" />
      <div className="flex items-center justify-between border-b border-line px-2.5 py-1.5">
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-mist">
          <span>{meta.flag}</span>
          <span style={{ color: meta.color }}>{country}</span>
        </div>
        <span className="font-mono text-[10px] text-fog">{formatShortDate(payload.event_date)}</span>
      </div>
      <div className="px-2.5 py-2">
        <div className="text-[12.5px] font-medium leading-snug text-paper">{payload.title}</div>
      </div>
      <div className="flex items-center justify-between border-t border-line px-2.5 py-1.5 font-mono text-[10px] text-fog">
        <span>
          Evidence <span className="text-gold">●</span> {pct}%
        </span>
        <span>
          {payload.sources} source{payload.sources === 1 ? "" : "s"}
        </span>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-line !bg-cyan" />
    </div>
  );
}
