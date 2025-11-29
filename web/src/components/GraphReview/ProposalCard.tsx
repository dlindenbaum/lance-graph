import React from 'react';
import { Proposal } from '../../types/graph';
import { ChangeItem } from './ChangeItem';

interface ProposalCardProps {
  proposal: Proposal;
  isExpanded: boolean;
  selectedChanges: Record<string, boolean>;
  editingChange: string | null;
  showEvidenceFor: string | null;
  onToggleExpanded: () => void;
  onToggleChangeSelection: (key: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onStartEdit: (changeId: string, initialValues: Record<string, any>) => void;
  onSaveEdit: (changeId: string, newValues: Record<string, any>) => void;
  onCancelEdit: () => void;
  onToggleEvidence: (changeId: string) => void;
  onApprove: (selectedOnly: boolean) => void;
  onReject: () => void;
  onAskWhy: () => void;
  onAskAgent: (question: string) => void;
}

export function ProposalCard({
  proposal,
  isExpanded,
  selectedChanges,
  editingChange,
  showEvidenceFor,
  onToggleExpanded,
  onToggleChangeSelection,
  onSelectAll,
  onDeselectAll,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onToggleEvidence,
  onApprove,
  onReject,
  onAskWhy,
  onAskAgent,
}: ProposalCardProps) {
  const selectedCount = proposal.changes.filter((_, idx) =>
    selectedChanges[`${proposal.id}-${idx}`]
  ).length;

  const allSelected = selectedCount === proposal.changes.length && proposal.changes.length > 0;

  const getStatusBadge = () => {
    if (proposal.status === 'approved') {
      return (
        <span className="px-2 py-0.5 bg-green-950/30 border border-green-900/50 text-green-400 text-xs rounded">
          ✓ Approved
        </span>
      );
    }
    if (proposal.status === 'rejected') {
      return (
        <span className="px-2 py-0.5 bg-red-950/30 border border-red-900/50 text-red-400 text-xs rounded">
          ✗ Rejected
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 bg-amber-950/30 border border-amber-900/50 text-amber-400 text-xs rounded">
        Review Required
      </span>
    );
  };

  const getIterationBadge = () => {
    let symbol = '';
    let color = 'text-text-muted';

    if (proposal.status === 'approved') {
      symbol = '✓';
      color = 'text-green-400';
    } else if (proposal.status === 'rejected') {
      symbol = '✗';
      color = 'text-red-400';
    }

    return (
      <div className={`w-8 h-8 rounded-full bg-dark-border flex items-center justify-center font-bold ${color}`}>
        {symbol || proposal.iteration}
      </div>
    );
  };

  return (
    <div
      className={`rounded-lg border overflow-hidden ${
        proposal.status === 'approved'
          ? 'bg-dark-panel/50 border-green-900/30'
          : proposal.status === 'rejected'
          ? 'bg-dark-panel/30 border-red-900/30 opacity-60'
          : 'bg-dark-panel border-dark-border'
      }`}
    >
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-dark-panel/80 transition-colors"
        onClick={onToggleExpanded}
      >
        <div className="flex items-center gap-3">
          {getIterationBadge()}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-medium text-text-main">{proposal.summary}</h3>
              {getStatusBadge()}
            </div>
            <div className="flex items-center gap-3 text-sm text-text-muted">
              <span>{proposal.changes.length} changes</span>
              <span>•</span>
              <span>{proposal.timestamp}</span>
            </div>
          </div>
          <div className="text-text-muted">
            {isExpanded ? '▼' : '▶'}
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-dark-border">
          <div className="p-4 space-y-2">
            {proposal.changes.map((change, idx) => {
              const key = `${proposal.id}-${idx}`;
              return (
                <ChangeItem
                  key={key}
                  change={change}
                  proposalStatus={proposal.status}
                  isSelected={selectedChanges[key] || false}
                  isEditing={editingChange === change.id}
                  showEvidence={showEvidenceFor === change.id}
                  onToggleSelection={() => onToggleChangeSelection(key)}
                  onStartEdit={(initialValues) => onStartEdit(change.id, initialValues)}
                  onSaveEdit={(newValues) => onSaveEdit(change.id, newValues)}
                  onCancelEdit={onCancelEdit}
                  onToggleEvidence={() => onToggleEvidence(change.id)}
                  onAskAgent={onAskAgent}
                />
              );
            })}
          </div>

          {/* Action Bar */}
          {proposal.status === 'pending' && (
            <div className="p-4 border-t border-dark-border bg-dark-panel/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  onClick={allSelected ? onDeselectAll : onSelectAll}
                  className="px-3 py-1.5 text-sm text-text-muted hover:text-text-main hover:bg-dark-border rounded"
                >
                  {allSelected ? 'Deselect All' : 'Select All'}
                </button>
                <button
                  onClick={onAskWhy}
                  className="px-3 py-1.5 text-sm text-text-muted hover:text-text-main hover:bg-dark-border rounded"
                >
                  Ask Why
                </button>
                {selectedCount > 0 && (
                  <span className="text-sm text-text-muted">
                    {selectedCount} selected
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={onReject}
                  className="px-4 py-1.5 text-sm border border-dark-border text-text-muted hover:text-text-main hover:border-text-muted rounded"
                >
                  Reject
                </button>
                <button
                  onClick={() => onApprove(selectedCount > 0 && selectedCount < proposal.changes.length)}
                  className="px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded font-medium"
                >
                  {selectedCount > 0 && selectedCount < proposal.changes.length
                    ? `Approve (${selectedCount})`
                    : 'Approve'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
