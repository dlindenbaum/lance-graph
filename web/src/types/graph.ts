// Type definitions for Graph Review UI

export interface Proposal {
  id: string;
  iteration: number;
  status: 'pending' | 'approved' | 'rejected';
  summary: string;
  timestamp: string;
  changes: Change[];
}

export type Change = AddNode | AddEdge | ModifyNode | DeleteNode | DeleteEdge | MergeNodes;

export interface BaseChange {
  id: string;
  userModified?: boolean;
}

export interface AddNode extends BaseChange {
  type: 'add_node';
  entity: string;
  label: string;
  properties: Record<string, any>;
  confidence: number;
  evidence?: string;
}

export interface AddEdge extends BaseChange {
  type: 'add_edge';
  from: string;
  to: string;
  relationship: string;
  properties?: Record<string, any>;
  evidence?: string;
}

export interface ModifyNode extends BaseChange {
  type: 'modify_node';
  entity: string;
  label: string;
  before: Record<string, any>;
  after: Record<string, any>;
  confidence: number;
  evidence?: string;
}

export interface DeleteNode extends BaseChange {
  type: 'delete_node';
  entity: string;
  label: string;
  reason?: string;
}

export interface DeleteEdge extends BaseChange {
  type: 'delete_edge';
  from: string;
  to: string;
  relationship: string;
  reason?: string;
}

export interface MergeNodes extends BaseChange {
  type: 'merge_nodes';
  entity: string;
  primaryLabel: string;
  secondaryLabel: string;
  primaryProperties: Record<string, any>;
  secondaryProperties: Record<string, any>;
  mergedProperties: Record<string, any>;
  matchConfidence: number;
  matchedRules: string[];
  evidence?: string;
  requiresReview: boolean;
  // Optional artifact ID for large property sets
  artifactId?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  timestamp?: string;
}

export interface ChangeTypeConfig {
  icon: string;
  color: string;
  label: string;
}

export const CHANGE_TYPE_CONFIG: Record<string, ChangeTypeConfig> = {
  add_node: { icon: '◉', color: '#10b981', label: 'New Node' },
  add_edge: { icon: '⟷', color: '#3b82f6', label: 'New Link' },
  modify_node: { icon: '◐', color: '#f59e0b', label: 'Update' },
  delete_node: { icon: '○', color: '#ef4444', label: 'Remove' },
  delete_edge: { icon: '╳', color: '#ef4444', label: 'Unlink' },
  merge_nodes: { icon: '⊕', color: '#8b5cf6', label: 'Merge' },
};

export function getConfidenceColor(confidence: number): string {
  if (confidence > 80) return '#10b981'; // green
  if (confidence >= 60) return '#f59e0b'; // amber
  return '#ef4444'; // red
}
