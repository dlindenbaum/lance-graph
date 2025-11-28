import React from 'react';
import { useGraphReview } from '../../hooks/useGraphReview';
import { mockProposals, mockMessages } from '../../utils/agentMock';
import { ProposalCard } from './ProposalCard';
import { ChatPanel } from './ChatPanel';

interface GraphReviewProps {
  caseId?: string;
}

export function GraphReview({ caseId = 'CDR-2024-001' }: GraphReviewProps) {
  const {
    proposals,
    messages,
    expandedId,
    selectedChanges,
    editingChange,
    showEvidenceFor,
    agentThinking,
    inputValue,
    setInputValue,
    toggleExpanded,
    toggleChangeSelection,
    selectAllChanges,
    deselectAllChanges,
    startEditing,
    cancelEditing,
    saveEdit,
    toggleEvidence,
    approveProposal,
    rejectProposal,
    sendMessage,
    prefillInput,
  } = useGraphReview(mockProposals, mockMessages);

  const handleAskWhy = (proposalId: string) => {
    const proposal = proposals.find((p) => p.id === proposalId);
    if (proposal) {
      prefillInput(`Why did you propose these changes in iteration ${proposal.iteration}?`);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-dark">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 bg-dark-panel border-b border-dark-border">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-text-main">Graph Review UI</h1>
          <span className="px-3 py-1 bg-dark-border/50 text-text-main text-sm rounded">
            Case: {caseId}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {agentThinking ? (
            <>
              <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-text-muted">Agent Thinking...</span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span className="text-sm text-text-muted">Agent Ready</span>
            </>
          )}
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Modification Review */}
        <div className="w-[55%] border-r border-dark-border overflow-y-auto p-6">
          <div className="space-y-4">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-text-main mb-1">
                Modification Review
              </h2>
              <p className="text-sm text-text-muted">
                Review and approve agent-proposed changes
              </p>
            </div>

            {proposals.length === 0 ? (
              <div className="text-center py-12 text-text-muted">
                <p>No proposals yet</p>
                <p className="text-sm mt-2">
                  Start a conversation with the agent to generate proposals
                </p>
              </div>
            ) : (
              proposals.map((proposal) => (
                <ProposalCard
                  key={proposal.id}
                  proposal={proposal}
                  isExpanded={expandedId === proposal.id}
                  selectedChanges={selectedChanges}
                  editingChange={editingChange}
                  showEvidenceFor={showEvidenceFor}
                  onToggleExpanded={() => toggleExpanded(proposal.id)}
                  onToggleChangeSelection={toggleChangeSelection}
                  onSelectAll={() => selectAllChanges(proposal.id)}
                  onDeselectAll={() => deselectAllChanges(proposal.id)}
                  onStartEdit={startEditing}
                  onSaveEdit={saveEdit}
                  onCancelEdit={cancelEditing}
                  onToggleEvidence={toggleEvidence}
                  onApprove={(selectedOnly) => approveProposal(proposal.id, selectedOnly)}
                  onReject={() => rejectProposal(proposal.id)}
                  onAskWhy={() => handleAskWhy(proposal.id)}
                  onAskAgent={prefillInput}
                />
              ))
            )}
          </div>
        </div>

        {/* Right Panel - Agent Chat */}
        <div className="w-[45%]">
          <ChatPanel
            messages={messages}
            inputValue={inputValue}
            agentThinking={agentThinking}
            onInputChange={setInputValue}
            onSendMessage={sendMessage}
            onQuickAction={prefillInput}
          />
        </div>
      </div>
    </div>
  );
}

export default GraphReview;
