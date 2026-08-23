"use client";

import { EventDrawer } from "@/components/EventDrawer";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { Header } from "@/components/Header";
import { LivePipelinePanel } from "@/components/LivePipelinePanel";
import { PipelineFlow } from "@/components/PipelineFlow";
import { PipelineStrip } from "@/components/PipelineStrip";
import { ScraperPulse } from "@/components/ScraperPulse";
import { SearchBar } from "@/components/SearchBar";
import { StatsBar } from "@/components/StatsBar";
import { api } from "@/lib/api";
import { SAMPLE_QUERIES } from "@/lib/samples";
import { DEFAULT_SOURCES } from "@/lib/sources";
import type {
  GraphMode,
  GraphPayload,
  NextPayload,
  PipelineEvent,
  PipelineSource,
  PipelineStage,
  RipplePayload,
  WhyPayload,
} from "@/lib/types";
import { useCallback, useMemo, useState } from "react";

const STAGE_COPY: Record<Exclude<PipelineStage, "idle">, string> = {
  discover: "Discovering live sources...",
  extract: "Extracting articles...",
  validate: "Validating feeds...",
  events: "Resolving events...",
  causal: "Mapping causal relationships...",
};

export default function HomePage() {
  const [query, setQuery] = useState(SAMPLE_QUERIES[0]);
  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [sources, setSources] = useState<PipelineSource[]>(DEFAULT_SOURCES);
  const [gdeltHealth, setGdeltHealth] = useState("HEALTHY");
  const [pipelineEvents, setPipelineEvents] = useState<PipelineEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<PipelineStage>("idle");
  const [statusLine, setStatusLine] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<GraphMode>("explore");
  const [why, setWhy] = useState<WhyPayload | null>(null);
  const [next, setNext] = useState<NextPayload | null>(null);
  const [ripple, setRipple] = useState<RipplePayload | null>(null);
  const [highlightNodes, setHighlightNodes] = useState<string[] | null>(null);
  const [highlightEdges, setHighlightEdges] = useState<string[] | null>(null);

  const loadPipeline = useCallback(async () => {
    try {
      const [status, events] = await Promise.all([api.pipelineStatus(), api.pipelineEvents()]);
      setSources(status.sources);
      setGdeltHealth(status.gdelt?.health || "HEALTHY");
      setPipelineEvents(events.events);
    } catch {
      /* pipeline panel degrades silently */
    }
  }, []);

  const articlesById = useMemo(() => {
    const map: Record<string, { source: string }> = {};
    payload?.articles.forEach((article) => {
      map[article.id] = { source: article.source };
    });
    return map;
  }, [payload]);

  const selected = payload?.events.find((event) => event.id === selectedId) || null;

  async function playStages(result: GraphPayload) {
    const sequence: [Exclude<PipelineStage, "idle">, string][] = [
      ["discover", `Discovering sources... ${result.stats.articles || 18} found`],
      ["extract", `Extracting articles... ${result.stats.articles || 14} valid`],
      ["validate", "Validating feeds... collector health checked"],
      ["events", `Identifying events... ${result.stats.events || 22} detected`],
      ["causal", `Mapping causality... ${result.stats.connections || 31} relationships`],
    ];
    for (const [nextStage, line] of sequence) {
      setStage(nextStage);
      setStatusLine(line);
      await new Promise((resolve) => setTimeout(resolve, 520));
    }
    setStage("idle");
    setStatusLine("");
  }

  async function trace(nextQuery = query) {
    setBusy(true);
    setError(null);
    setMode("explore");
    setWhy(null);
    setNext(null);
    setRipple(null);
    setHighlightNodes(null);
    setHighlightEdges(null);
    setStage("discover");
    setStatusLine(STAGE_COPY.discover);
    void loadPipeline();
    try {
      const result = await api.analyze(nextQuery);
      await playStages(result);
      setPayload(result);
      const core = result.events.find((event) => (event.relevance_class || "CORE") === "CORE");
      setSelectedId(core?.id || result.events[0]?.id || null);
      await loadPipeline();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
      setStage("idle");
    } finally {
      setBusy(false);
    }
  }

  async function applyMode(nextMode: GraphMode) {
    if (!payload || !selectedId) return;
    if (nextMode === "explore") {
      setMode("explore");
      setHighlightNodes(null);
      setHighlightEdges(null);
      return;
    }
    try {
      if (nextMode === "why") {
        const data = await api.why(selectedId, payload.analysis_id);
        setWhy(data);
        setHighlightNodes(data.highlight_node_ids);
        setHighlightEdges(data.highlight_edge_ids || null);
      } else if (nextMode === "next") {
        const data = await api.next(selectedId, payload.analysis_id);
        setNext(data);
        setHighlightNodes(data.highlight_node_ids);
        setHighlightEdges(data.highlight_edge_ids || null);
      } else {
        const data = await api.ripple(selectedId, payload.analysis_id);
        setRipple(data);
        setHighlightNodes(data.highlight_node_ids);
        setHighlightEdges(data.highlight_edge_ids || data.cross_border_edge_ids || null);
      }
      setMode(nextMode);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Graph traversal failed");
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-void text-paper">
      <Header dataMode={payload?.data_mode || null} cachedFrom={payload?.cached_from} />
      <SearchBar
        query={query}
        onQuery={setQuery}
        onTrace={() => trace()}
        busy={busy}
      />
      <div className="px-4 py-2">
        <div className="flex flex-wrap gap-1.5">
          {SAMPLE_QUERIES.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => {
                setQuery(sample);
                void trace(sample);
              }}
              className="rounded-sm border border-line px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-mist hover:border-gold/50 hover:text-paper"
            >
              {sample}
            </button>
          ))}
        </div>
      </div>
      <PipelineStrip sources={sources} gdeltHealth={gdeltHealth} />
      <StatsBar payload={payload} />
      <PipelineFlow stage={stage} statusLine={statusLine} />
      {error && (
        <div className="border-b border-fail/40 bg-fail/10 px-4 py-2 text-[12px] text-fail">{error}</div>
      )}
      {payload?.degraded_reasons?.length ? (
        <div className="border-b border-gold/30 bg-gold/5 px-4 py-2 text-[11px] text-gold">
          {payload.data_mode === "CACHED" ? "CACHED — " : "DEGRADED — "}
          {payload.degraded_reasons[0]}
        </div>
      ) : null}
      {payload?.diagnostics ? (
        <details className="border-b border-line px-4 py-2 text-[11px] text-mist">
          <summary className="cursor-pointer uppercase tracking-[0.14em] text-fog">
            Graph quality · CORE {payload.diagnostics.core_count} · CONTEXT {payload.diagnostics.context_count} ·
            REJECTED {payload.diagnostics.rejected_count}
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-fog">
            {`Query: ${payload.diagnostics.query}
Candidates: ${payload.diagnostics.candidate_count}
CORE: ${payload.diagnostics.core_count}
CONTEXT: ${payload.diagnostics.context_count}
REJECTED: ${payload.diagnostics.rejected_count}

Rejected:
${(payload.diagnostics.rejected || [])
  .slice(0, 8)
  .map((item) => `- ${item.title}\n  reason: ${item.reason}`)
  .join("\n") || "- (none)"}`}
          </pre>
        </details>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-[280px] shrink-0 overflow-y-auto border-r border-line bg-panel lg:block">
          <LivePipelinePanel sources={sources} onHealed={loadPipeline} />
          <ScraperPulse sources={sources} events={pipelineEvents} />
        </aside>
        <main className="relative min-w-0 flex-1">
          {!payload && !busy && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="max-w-lg px-6 text-center">
                <div className="text-[10px] uppercase tracking-[0.28em] text-gold">Causal intelligence</div>
                <h1 className="mt-3 text-[28px] font-medium leading-tight text-paper">
                  Understand why Southeast Asia moves.
                </h1>
                <p className="mt-3 text-[13px] leading-relaxed text-mist">
                  Trace live CNA, The Edge Malaysia and VIR coverage through GDELT into an evidence-backed causal graph.
                </p>
              </div>
            </div>
          )}
          {payload && (
            <GraphCanvas
              events={payload.events}
              edges={payload.edges}
              articlesById={articlesById}
              selectedId={selectedId}
              highlightNodeIds={highlightNodes}
              highlightEdgeIds={highlightEdges}
              mode={mode}
              onSelect={(id) => {
                setSelectedId(id);
                setMode("explore");
                setHighlightNodes(null);
                setHighlightEdges(null);
              }}
            />
          )}
        </main>
        {selected && payload && (
          <EventDrawer
            event={selected}
            edges={payload.edges}
            articles={payload.articles}
            mode={mode}
            why={why}
            next={next}
            ripple={ripple}
            onClose={() => setSelectedId(null)}
            onMode={applyMode}
          />
        )}
      </div>
    </div>
  );
}
