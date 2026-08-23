export type DataMode = "LIVE" | "CACHED" | "PARTIAL";
export type GraphMode = "explore" | "why" | "next" | "ripple";
export type PipelineStage =
  | "idle"
  | "discover"
  | "extract"
  | "validate"
  | "events"
  | "causal";

export interface Entity {
  id: string;
  name: string;
  type: string;
  country?: string | null;
}

export interface EventNodeData {
  id: string;
  title: string;
  summary: string;
  event_date?: string | null;
  countries: string[];
  companies: string[];
  industries: string[];
  entities: Entity[];
  source_article_ids: string[];
  confidence: number;
  event_type: string;
}

export interface CausalEdgeData {
  id: string;
  source_event_id: string;
  target_event_id: string;
  relation: string;
  confidence: number;
  evidence_score: number;
  reason: string;
  supporting_article_ids: string[];
  status: "observed" | "inferred" | "predicted";
  cross_border: boolean;
  source_countries: string[];
  target_countries: string[];
}

export interface ArticleCard {
  id: string;
  title: string;
  url: string;
  source: string;
  country: string;
  published_at?: string | null;
  author?: string | null;
  category: string[];
  summary?: string | null;
}

export interface GraphPayload {
  analysis_id: string;
  query: string;
  data_mode: DataMode;
  cached_from?: string | null;
  generated_at: string;
  degraded_reasons: string[];
  stats: Record<string, number>;
  events: EventNodeData[];
  edges: CausalEdgeData[];
  articles: ArticleCard[];
}

export interface PipelineSource {
  source: string;
  display_name: string;
  country: string;
  discovery_status: string;
  article_status: string;
  last_success?: string | null;
  last_failure?: string | null;
  articles_discovered: number;
  articles_extracted: number;
  validation_failures: number;
  collector_id: string;
  article_collector_id: string;
  health: "HEALTHY" | "DEGRADED" | "FAILED" | "HEALED";
}

export interface PipelineEvent {
  id: string;
  source: string;
  collector_id?: string | null;
  kind: string;
  message: string;
  created_at: string;
}

export interface WhyPayload {
  event_id: string;
  title: string;
  highlight_node_ids: string[];
  highlight_edge_ids?: string[];
  paths: string[][];
  narrative: {
    step: number;
    from_event_id: string;
    to_event_id: string;
    from_title?: string;
    to_title?: string;
    relation: string | null;
    text: string;
    status: string;
  }[];
}

export interface NextPayload {
  event_id: string;
  title: string;
  highlight_node_ids: string[];
  highlight_edge_ids?: string[];
  observed: EventNodeData[];
  predicted: EventNodeData[];
}

export interface RipplePayload {
  event_id: string;
  title: string;
  markets_connected: number;
  markets: { country: string; event_ids: string[]; events: EventNodeData[] }[];
  highlight_node_ids: string[];
  highlight_edge_ids?: string[];
  cross_border_edge_ids?: string[];
}
