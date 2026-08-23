import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

const NODE_W = 248;
const NODE_H = 128;

export function layoutGraph(nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[] } {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", nodesep: 36, ranksep: 92, marginx: 24, marginy: 24 });

  nodes.forEach((node) => graph.setNode(node.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((edge) => graph.setEdge(edge.source, edge.target));
  dagre.layout(graph);

  const laidOut = nodes.map((node) => {
    const pos = graph.node(node.id);
    return {
      ...node,
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
    };
  });
  return { nodes: laidOut, edges };
}
