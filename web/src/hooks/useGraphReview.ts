import { useState, useCallback } from 'react';
import { Proposal, Message, Change } from '../types/graph';
import { simulateAgentResponse } from '../utils/agentMock';

export interface GraphReviewState {
  proposals: Proposal[];
  messages: Message[];
  expandedId: string | null;
  selectedChanges: Record<string, boolean>;
  editingChange: string | null;
  editValues: Record<string, any>;
  showEvidenceFor: string | null;
  agentThinking: boolean;
  inputValue: string;
}

export function useGraphReview(
  initialProposals: Proposal[] = [],
  initialMessages: Message[] = []
) {
  const [proposals, setProposals] = useState<Proposal[]>(initialProposals);
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedChanges, setSelectedChanges] = useState<Record<string, boolean>>({});
  const [editingChange, setEditingChange] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, any>>({});
  const [showEvidenceFor, setShowEvidenceFor] = useState<string | null>(null);
  const [agentThinking, setAgentThinking] = useState<boolean>(false);
  const [inputValue, setInputValue] = useState<string>('');

  const toggleExpanded = useCallback((proposalId: string) => {
    setExpandedId((prev) => (prev === proposalId ? null : proposalId));
  }, []);

  const toggleChangeSelection = useCallback((key: string) => {
    setSelectedChanges((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  }, []);

  const selectAllChanges = useCallback((proposalId: string) => {
    const proposal = proposals.find((p) => p.id === proposalId);
    if (!proposal) return;

    const updates: Record<string, boolean> = {};
    proposal.changes.forEach((change, idx) => {
      const key = `${proposalId}-${idx}`;
      updates[key] = true;
    });

    setSelectedChanges((prev) => ({ ...prev, ...updates }));
  }, [proposals]);

  const deselectAllChanges = useCallback((proposalId: string) => {
    const proposal = proposals.find((p) => p.id === proposalId);
    if (!proposal) return;

    const updates: Record<string, boolean> = {};
    proposal.changes.forEach((_, idx) => {
      const key = `${proposalId}-${idx}`;
      updates[key] = false;
    });

    setSelectedChanges((prev) => ({ ...prev, ...updates }));
  }, [proposals]);

  const startEditing = useCallback((changeId: string, initialValues: Record<string, any>) => {
    setEditingChange(changeId);
    setEditValues(initialValues);
  }, []);

  const cancelEditing = useCallback(() => {
    setEditingChange(null);
    setEditValues({});
  }, []);

  const saveEdit = useCallback((changeId: string, newValues: Record<string, any>) => {
    setProposals((prev) =>
      prev.map((proposal) => ({
        ...proposal,
        changes: proposal.changes.map((change) =>
          change.id === changeId
            ? { ...change, ...newValues, userModified: true }
            : change
        ),
      }))
    );
    setEditingChange(null);
    setEditValues({});
  }, []);

  const toggleEvidence = useCallback((changeId: string) => {
    setShowEvidenceFor((prev) => (prev === changeId ? null : changeId));
  }, []);

  const approveProposal = useCallback((proposalId: string, selectedOnly: boolean = false) => {
    setProposals((prev) =>
      prev.map((proposal) =>
        proposal.id === proposalId
          ? { ...proposal, status: 'approved' as const }
          : proposal
      )
    );

    // Add system message
    const systemMsg: Message = {
      id: `sys-${Date.now()}`,
      role: 'system',
      content: `Proposal #${proposals.find(p => p.id === proposalId)?.iteration} approved and committed to graph`,
      timestamp: 'Just now',
    };
    setMessages((prev) => [...prev, systemMsg]);

    // Clear selections
    if (selectedOnly) {
      deselectAllChanges(proposalId);
    }
  }, [proposals, deselectAllChanges]);

  const rejectProposal = useCallback((proposalId: string) => {
    setProposals((prev) =>
      prev.map((proposal) =>
        proposal.id === proposalId
          ? { ...proposal, status: 'rejected' as const }
          : proposal
      )
    );

    // Add system message
    const systemMsg: Message = {
      id: `sys-${Date.now()}`,
      role: 'system',
      content: `Proposal #${proposals.find(p => p.id === proposalId)?.iteration} rejected`,
      timestamp: 'Just now',
    };
    setMessages((prev) => [...prev, systemMsg]);

    // Clear selections
    deselectAllChanges(proposalId);
  }, [proposals, deselectAllChanges]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || agentThinking) return;

    // Add user message
    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: 'Just now',
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setAgentThinking(true);

    try {
      // Simulate agent response
      const response = await simulateAgentResponse(content, proposals);

      setMessages((prev) => [...prev, response.message]);

      if (response.proposal) {
        setProposals((prev) => [...prev, response.proposal!]);
      }
    } catch (error) {
      console.error('Error getting agent response:', error);
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        role: 'system',
        content: 'Error communicating with agent',
        timestamp: 'Just now',
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setAgentThinking(false);
    }
  }, [agentThinking, proposals]);

  const prefillInput = useCallback((text: string) => {
    setInputValue(text);
  }, []);

  return {
    // State
    proposals,
    messages,
    expandedId,
    selectedChanges,
    editingChange,
    editValues,
    showEvidenceFor,
    agentThinking,
    inputValue,

    // Actions
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
  };
}
