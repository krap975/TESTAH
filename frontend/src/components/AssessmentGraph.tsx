import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from '@xyflow/react';
import type { GraphEdge, GraphNode, Outcome } from '../services/assessmentGraph';

const colors: Record<Outcome, string> = { recorded: '#64748b', active: '#a99af8', success: '#67c7a0', rejected: '#e8b76d', failed: '#f0808f', interrupted: '#94a3b8' };
export function AssessmentGraph({ nodes, edges, select, selection }: { nodes: GraphNode[]; edges: GraphEdge[]; select: (kind: 'node' | 'edge', id: string) => void; selection: { kind: 'node' | 'edge'; id: string } | null }) {
  const flowNodes: Node[] = nodes.map(node => ({ ...node, selected: selection?.kind === 'node' && selection.id === node.id, style: { borderColor: colors[node.data.outcome] } }));
  const flowEdges: Edge[] = edges.map(edge => ({ ...edge, selected: selection?.kind === 'edge' && selection.id === edge.id, label: edge.label + ' · ' + edge.data.outcome, type: 'smoothstep', animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color: colors[edge.data.outcome] }, style: { stroke: colors[edge.data.outcome], strokeWidth: edge.data.outcome === 'active' ? 3 : 1.5 },
    labelStyle: { fill: '#e2e8f0', fontSize: 10 }, labelBgStyle: { fill: '#111621' },
    ariaLabel: edge.label + ' — ' + edge.data.outcome,
  }));
  return <section className="panel monitor-graph-panel" aria-label="Recorded execution graph"><div className="section-header"><h2>Execution graph</h2><span className="muted text-xs">Select a node or interaction</span></div>
    <div className="monitor-graph"><ReactFlow nodes={flowNodes} edges={flowEdges} fitView minZoom={.35} maxZoom={1.5} colorMode="dark"
      nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} onNodeClick={(_event, node) => select('node', node.id)}
      onEdgeClick={(_event, edge) => select('edge', edge.id)}><Background gap={24} color="#242b39" /><Controls showInteractive={false} /></ReactFlow></div>
    <div className="graph-legend">{Object.entries(colors).map(([outcome, color]) => <span key={outcome}><i style={{ background: color }} />{outcome}</span>)}</div>
    <p className="form-help p-4">Fixed service roles with interactions derived from evidence. Active means a recorded request awaits a recorded result. Labels count supporting events; no internal thoughts or real payments are shown.</p>
  </section>;
}
