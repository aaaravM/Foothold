/**
 * Pure reducer that turns CONTRACTS section 6 TraceEvents into TracePanel state.
 * React wrapper: components/foothold/use-trace.ts (useTrace).
 */
import type { LlmSource, TraceEvent, TraceNode } from "./types";

export type TraceNodeStatus = "pending" | "active" | "done" | "waiting" | "error";
export type TraceRunStatus = "idle" | "connecting" | "running" | "interrupted" | "done" | "error";

export interface TraceNodeState {
  id: string;
  status: TraceNodeStatus;
  /** duration of the latest completed run of this node */
  ms?: number;
  summary?: string;
  llm?: LlmSource;
  /** completed executions of this node in this thread */
  runs: number;
}

export interface TraceInterrupt {
  node: string;
  payload: unknown;
}

export interface TraceState {
  graph: string | null;
  threadId: string | null;
  /** node list from the latest `meta` event (plus any unknown nodes seen later) */
  nodes: TraceNode[];
  nodeState: Record<string, TraceNodeState>;
  status: TraceRunStatus;
  interrupt: TraceInterrupt | null;
  result: unknown;
  error: string | null;
  /** merged `state` events (UI-relevant partial state) */
  data: Record<string, unknown>;
  /** streams seen for this thread (each run starts with `meta`) */
  runs: number;
  lastSummary: string | null;
  eventCount: number;
}

/** Client-side actions on top of the server events. `stream-end`: the HTTP stream closed. */
export type TraceAction = TraceEvent | { type: "reset" } | { type: "connecting" } | { type: "stream-end" };

export function createTraceState(): TraceState {
  return {
    graph: null,
    threadId: null,
    nodes: [],
    nodeState: {},
    status: "idle",
    interrupt: null,
    result: null,
    error: null,
    data: {},
    runs: 0,
    lastSummary: null,
    eventCount: 0,
  };
}

function ensureNode(state: TraceState, id: string): { nodes: TraceNode[]; nodeState: Record<string, TraceNodeState> } {
  if (state.nodeState[id]) return { nodes: state.nodes, nodeState: state.nodeState };
  const known = state.nodes.some((n) => n.id === id);
  return {
    nodes: known ? state.nodes : [...state.nodes, { id, label: id, kind: "logic" }],
    nodeState: { ...state.nodeState, [id]: { id, status: "pending", runs: 0 } },
  };
}

function markActive(nodeState: Record<string, TraceNodeState>, status: TraceNodeStatus): Record<string, TraceNodeState> {
  let changed = false;
  const next: Record<string, TraceNodeState> = {};
  for (const [id, ns] of Object.entries(nodeState)) {
    if (ns.status === "active") {
      next[id] = { ...ns, status };
      changed = true;
    } else {
      next[id] = ns;
    }
  }
  return changed ? next : nodeState;
}

export function traceReducer(state: TraceState, action: TraceAction): TraceState {
  switch (action.type) {
    case "reset":
      return createTraceState();

    case "connecting":
      return { ...state, status: "connecting", error: null, interrupt: null };

    case "stream-end":
      // After `interrupt` or `done` the stream closing is normal; mid-run it is not.
      if (state.status === "connecting" || state.status === "running") {
        return {
          ...state,
          nodeState: markActive(state.nodeState, "error"),
          status: "error",
          error: "The stream ended before the graph finished.",
        };
      }
      return state;

    case "meta": {
      const sameThread = state.threadId === action.thread_id && state.graph === action.graph;
      const nodes = action.nodes.length > 0 ? action.nodes : sameThread ? state.nodes : [];
      const nodeState: Record<string, TraceNodeState> = {};
      for (const n of nodes) {
        nodeState[n.id] = { id: n.id, status: "pending", runs: sameThread ? (state.nodeState[n.id]?.runs ?? 0) : 0 };
      }
      return {
        ...state,
        graph: action.graph,
        threadId: action.thread_id,
        nodes,
        nodeState,
        status: "running",
        interrupt: null,
        result: null,
        error: null,
        data: sameThread ? state.data : {},
        runs: sameThread ? state.runs + 1 : 1,
        lastSummary: sameThread ? state.lastSummary : null,
        eventCount: state.eventCount + 1,
      };
    }

    case "node": {
      const base = ensureNode(state, action.node);
      const prev = base.nodeState[action.node];
      if (action.status === "start") {
        return {
          ...state,
          ...base,
          graph: state.graph ?? action.graph,
          nodeState: { ...base.nodeState, [action.node]: { ...prev, status: "active", ms: undefined, summary: undefined, llm: undefined } },
          status: "running",
          interrupt: null,
          eventCount: state.eventCount + 1,
        };
      }
      return {
        ...state,
        ...base,
        graph: state.graph ?? action.graph,
        nodeState: {
          ...base.nodeState,
          [action.node]: {
            ...prev,
            status: "done",
            ms: action.ms ?? prev.ms,
            summary: action.summary ?? prev.summary,
            llm: action.llm ?? prev.llm,
            runs: prev.runs + 1,
          },
        },
        status: state.status === "idle" || state.status === "connecting" ? "running" : state.status,
        lastSummary: action.summary ?? state.lastSummary,
        eventCount: state.eventCount + 1,
      };
    }

    case "state":
      return { ...state, data: { ...state.data, ...action.data }, eventCount: state.eventCount + 1 };

    case "interrupt": {
      const base = ensureNode(state, action.node);
      return {
        ...state,
        ...base,
        nodeState: { ...base.nodeState, [action.node]: { ...base.nodeState[action.node], status: "waiting" } },
        status: "interrupted",
        interrupt: { node: action.node, payload: action.payload },
        eventCount: state.eventCount + 1,
      };
    }

    case "done":
      return {
        ...state,
        nodeState: markActive(state.nodeState, "done"),
        status: "done",
        result: action.result,
        interrupt: null,
        eventCount: state.eventCount + 1,
      };

    case "error":
      return {
        ...state,
        nodeState: markActive(state.nodeState, "error"),
        status: "error",
        error: action.message || "Something went wrong",
        eventCount: state.eventCount + 1,
      };

    default:
      return state;
  }
}

/** Rows for display: nodes in order, nodes sharing a `group` merged into one row (side by side). */
export function traceRows(nodes: readonly TraceNode[]): TraceNode[][] {
  const rows: TraceNode[][] = [];
  const groupRow = new Map<string, TraceNode[]>();
  for (const n of nodes) {
    if (n.group) {
      const existing = groupRow.get(n.group);
      if (existing) {
        existing.push(n);
        continue;
      }
      const row = [n];
      groupRow.set(n.group, row);
      rows.push(row);
    } else {
      rows.push([n]);
    }
  }
  return rows;
}

export function traceProgress(state: TraceState): { done: number; total: number } {
  const total = state.nodes.length;
  let done = 0;
  for (const n of state.nodes) if (state.nodeState[n.id]?.status === "done") done += 1;
  return { done, total };
}
