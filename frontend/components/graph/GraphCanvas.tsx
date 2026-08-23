"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useMemo } from "react";
import { EventNode, type EventNodePayload } from "@/components/graph/EventNode";
import { layoutGraph } from "@/lib/layout";
import type { CausalEdgeData, EventNodeData, GraphMode } from "@/lib/types";
import { cn } from "@/lib/utils";

const nodeTypes = { event: EventNode };

function edgeStyle(status: CausalEdgeData["status"], highlighted: boolean, dimmed: boolean) {
  const color = status === "predicted" ? "#7d8a99" : status === "inferred" ? "#8fb4c8" : "#c4a35a";
  return {
    stroke: color,
    strokeWidth: highlighted ? 2.2 : 1.2,
    opacity: dimmed ? 0.12 : highlighted ? 1 : 0.7,
    strokeDasharray: status === "predicted" ? "2 4" : status === "inferred" ? "6 4" : undefined,
  };
}

export function GraphCanvas({
  events,
  edges,
  articlesById,
  selectedId,
  highlightNodeIds,
  highlightEdgeIds,
  mode,
  onSelect,
}: {
  events: EventNodeData[];
  edges: CausalEdgeData[];
  articlesById: Record<string, { source: string }>;
  selectedId: string | null;
  highlightNodeIds: string[] | null;
  highlightEdgeIds: string[] | null;
  mode: GraphMode;
  onSelect: (id: string) => void;
}) {
  const base = useMemo(() => {
    const evidenceFor = (event: EventNodeData) => {
      const related = edges.filter(
        (edge) => edge.source_event_id === event.id || edge.target_event_id === event.id,
      );
      if (!related.length) return event.confidence;
      return related.reduce((sum, edge) => sum + edge.evidence_score, 0) / related.length;
    };
    const sourceCount = (event: EventNodeData) => {
      const ids = new Set(event.source_article_ids);
      const names = new Set([...ids].map((id) => articlesById[id]?.source).filter(Boolean));
      return Math.max(names.size, ids.size);
    };
    const nodes: Node[] = events.map((event) => ({
      id: event.id,
      type: "event",
      position: { x: 0, y: 0 },
      data: {
        ...event,
        evidence: evidenceFor(event),
        sources: sourceCount(event),
      } satisfies EventNodePayload,
    }));
    const flowEdges: Edge[] = edges.map((edge) => ({
      id: edge.id,
      source: edge.source_event_id,
      target: edge.target_event_id,
      label: edge.relation,
      type: "smoothstep",
      data: { ...edge },
    }));
    return layoutGraph(nodes, flowEdges);
  }, [articlesById, edges, events]);

  const nodes = useMemo(() => {
    const highlightSet = highlightNodeIds ? new Set(highlightNodeIds) : null;
    return base.nodes.map((node) => {
      const current = node.data as unknown as EventNodePayload;
      return {
        ...node,
        data: {
          ...current,
          dimmed: Boolean(highlightSet && !highlightSet.has(node.id)),
          active: selectedId === node.id,
          predicted: mode === "next" && Boolean(highlightSet?.has(node.id) && node.id !== selectedId),
        },
      };
    });
  }, [base.nodes, highlightNodeIds, mode, selectedId]);

  const flowEdges = useMemo(() => {
    const highlightSet = highlightNodeIds ? new Set(highlightNodeIds) : null;
    const highlightEdges = highlightEdgeIds ? new Set(highlightEdgeIds) : null;
    return base.edges.map((flowEdge) => {
      const edge = flowEdge.data as unknown as CausalEdgeData;
      const highlighted = highlightEdges
        ? highlightEdges.has(edge.id)
        : !highlightSet || (highlightSet.has(edge.source_event_id) && highlightSet.has(edge.target_event_id));
      const dimmed = Boolean(highlightSet) && !highlighted;
      return {
        ...flowEdge,
        labelStyle: {
          fill: "#c9d2dc",
          fontSize: 9,
          fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
          letterSpacing: "0.08em",
        },
        labelBgStyle: { fill: "#0d1117", fillOpacity: 0.92 },
        labelBgPadding: [4, 2] as [number, number],
        style: edgeStyle(edge.status, highlighted && Boolean(highlightSet), dimmed),
        markerEnd: {
          type: "arrowclosed" as const,
          color: edge.cross_border ? "#4db8d4" : "#c4a35a",
          width: 14,
          height: 14,
        },
      };
    });
  }, [base.edges, highlightEdgeIds, highlightNodeIds]);

  return (
    <div className={cn("h-full w-full bg-void")}>
      <ReactFlow
        nodes={nodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelect(node.id)}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.35}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
      >
        <Background color="#1c2430" gap={22} size={1} />
        <MiniMap
          pannable
          zoomable
          maskColor="rgba(7,9,13,0.82)"
          nodeColor="#1c2430"
          className="!bg-panel !border !border-line"
        />
        <Controls className="!border-line !bg-panel !shadow-none [&>button]:!border-line [&>button]:!bg-panel [&>button]:!fill-fog" />
      </ReactFlow>
    </div>
  );
}
