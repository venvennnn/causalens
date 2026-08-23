"use client";

import { countryMeta } from "@/lib/countries";
import type {
  ArticleCard,
  CausalEdgeData,
  EventNodeData,
  GraphMode,
  NextPayload,
  RipplePayload,
  WhyPayload,
} from "@/lib/types";
import { evidencePct, formatDate } from "@/lib/utils";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

function EvidenceBar({ score }: { score: number }) {
  const pct = evidencePct(score);
  const filled = Math.round(pct / 10);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-[0.16em] text-mist">
        <span>Evidence</span>
        <span className="font-mono text-gold">{pct}%</span>
      </div>
      <div className="font-mono text-[13px] tracking-[0.12em] text-gold">
        {"█".repeat(filled)}
        <span className="text-line">{"░".repeat(10 - filled)}</span>
      </div>
    </div>
  );
}

export function EventDrawer({
  event,
  edges,
  articles,
  mode,
  why,
  next,
  ripple,
  onClose,
  onMode,
}: {
  event: EventNodeData;
  edges: CausalEdgeData[];
  articles: ArticleCard[];
  mode: GraphMode;
  why: WhyPayload | null;
  next: NextPayload | null;
  ripple: RipplePayload | null;
  onClose: () => void;
  onMode: (mode: GraphMode) => void;
}) {
  const related = edges.filter(
    (edge) => edge.source_event_id === event.id || edge.target_event_id === event.id,
  );
  const evidence =
    related.reduce((sum, edge) => sum + edge.evidence_score, 0) / Math.max(related.length, 1) ||
    event.confidence;
  const supportingIds = new Set(event.source_article_ids);
  related.forEach((edge) => edge.supporting_article_ids.forEach((id) => supportingIds.add(id)));
  const cards = articles.filter((article) => supportingIds.has(article.id));

  return (
    <aside className="flex h-full w-[380px] shrink-0 flex-col border-l border-line bg-panel">
      <div className="flex items-start justify-between border-b border-line px-4 py-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-gold">Event</div>
          <h2 className="mt-1 text-[15px] font-medium leading-snug text-paper">{event.title}</h2>
          <div className="mt-1 font-mono text-[11px] text-fog">{formatDate(event.event_date)}</div>
        </div>
        <button onClick={onClose} className="text-mist hover:text-paper" aria-label="Close">
          <X size={16} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <p className="text-[13px] leading-relaxed text-fog">{event.summary}</p>

        <Section label="Countries">
          <div className="flex flex-wrap gap-1.5">
            {event.countries.map((country) => (
              <span key={country} className="rounded-sm border border-line px-1.5 py-0.5 text-[11px] text-paper">
                {countryMeta(country).flag} {country}
              </span>
            ))}
          </div>
        </Section>
        <Section label="Industries">
          <div className="text-[12px] text-paper">{event.industries.join("  ·  ") || "—"}</div>
        </Section>
        {event.companies.length > 0 && (
          <Section label="Companies">
            <div className="text-[12px] text-paper">{event.companies.join("  ·  ")}</div>
          </Section>
        )}

        <div className="mt-4">
          <EvidenceBar score={evidence} />
        </div>

        <div className="mt-5 grid grid-cols-3 gap-1.5">
          <Button variant={mode === "why" ? "default" : "outline"} onClick={() => onMode("why")}>
            Why?
          </Button>
          <Button variant={mode === "next" ? "default" : "outline"} onClick={() => onMode("next")}>
            What next?
          </Button>
          <Button variant={mode === "ripple" ? "live" : "outline"} onClick={() => onMode("ripple")}>
            Ripple
          </Button>
        </div>

        {mode === "why" && why && (
          <Section label="Why this happened">
            <ol className="space-y-2">
              {why.narrative.map((step) => (
                <li key={step.step} className="border-l border-gold/40 pl-3">
                  <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-gold">
                    {step.step}. {step.relation || "FACT"}
                  </div>
                  <div className="mt-0.5 text-[12px] leading-relaxed text-fog">{step.text}</div>
                </li>
              ))}
            </ol>
          </Section>
        )}

        {mode === "next" && next && (
          <Section label="Likely downstream effects">
            <div className="space-y-2">
              {next.observed.map((item) => (
                <div key={item.id} className="border border-line px-2 py-1.5">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-ok">Observed</div>
                  <div className="text-[12px] text-paper">{item.title}</div>
                </div>
              ))}
              {next.predicted.map((item) => (
                <div key={item.id} className="border border-dashed border-mist/40 px-2 py-1.5">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-mist">Predicted — not established fact</div>
                  <div className="text-[12px] text-fog">{item.title}</div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {mode === "ripple" && ripple && (
          <Section label="Regional ripple">
            <div className="mb-2 font-mono text-[11px] text-cyan">
              {ripple.markets_connected} markets connected
            </div>
            <div className="space-y-2">
              {ripple.markets.map((market) => (
                <div key={market.country} className="border border-line px-2 py-1.5">
                  <div className="text-[12px] text-paper">
                    {countryMeta(market.country).flag} {market.country}
                  </div>
                  <div className="text-[11px] text-mist">{market.events.length} event{market.events.length === 1 ? "" : "s"}</div>
                </div>
              ))}
            </div>
          </Section>
        )}

        <Section label="Sources">
          <div className="space-y-2">
            {cards.map((article) => {
              const linkEdges = related.filter((edge) => edge.supporting_article_ids.includes(article.id));
              return (
                <a
                  key={article.id}
                  href={article.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block border border-line px-2.5 py-2 hover:border-gold/50"
                >
                  <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.14em] text-mist">
                    <span>{article.source}</span>
                    <span className="font-mono">{formatDate(article.published_at)}</span>
                  </div>
                  <div className="mt-1 text-[12px] leading-snug text-paper">{article.title}</div>
                  {linkEdges[0] && (
                    <div className="mt-1 font-mono text-[10px] text-gold">
                      {linkEdges[0].relation} · Evidence {evidencePct(linkEdges[0].evidence_score)}%
                    </div>
                  )}
                </a>
              );
            })}
          </div>
        </Section>
      </div>
    </aside>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <div className="mb-1.5 text-[10px] uppercase tracking-[0.18em] text-mist">{label}</div>
      {children}
    </section>
  );
}
