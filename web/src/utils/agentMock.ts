import { Proposal, Message } from '../types/graph';

export const mockProposals: Proposal[] = [
  {
    id: 'p1',
    iteration: 1,
    status: 'approved',
    summary: 'Initial CDR Analysis - 555-0199',
    timestamp: '8 min ago',
    changes: [
      {
        id: 'c1',
        type: 'add_node',
        entity: 'Person',
        label: 'John Doe',
        properties: {
          phone: '555-0199',
          carrier: 'Verizon',
          location: 'Arlington, VA'
        },
        confidence: 92,
      },
    ],
  },
  {
    id: 'p2',
    iteration: 2,
    status: 'pending',
    summary: 'CDR Expansion - High Frequency Contacts',
    timestamp: 'Just now',
    changes: [
      {
        id: 'c2',
        type: 'add_node',
        entity: 'Phone',
        label: '555-1024',
        properties: {
          calls: 47,
          avgDuration: '4m 12s',
          pattern: 'Daily morning'
        },
        confidence: 88,
        evidence: 'Identified from CDR frequency analysis. 47 calls over 90 days.',
      },
      {
        id: 'c3',
        type: 'add_edge',
        from: 'John Doe',
        to: '555-1024',
        relationship: 'CONTACTED',
        properties: {
          frequency: 'High',
          firstCall: '2024-01-15'
        },
      },
      {
        id: 'c4',
        type: 'modify_node',
        entity: 'Phone',
        label: '555-1024',
        before: { owner: null },
        after: {
          owner: 'Sarah Chen',
          address: '1842 Oak St'
        },
        confidence: 76,
        evidence: 'Matched via carrier lookup + social media correlation',
      },
    ],
  },
];

export const mockMessages: Message[] = [
  {
    id: 'm1',
    role: 'system',
    content: 'Agent initialized. Ready to investigate CDR data.',
    timestamp: '10 min ago',
  },
  {
    id: 'm2',
    role: 'user',
    content: 'Analyze the call patterns for 555-0199',
    timestamp: '8 min ago',
  },
  {
    id: 'm3',
    role: 'agent',
    content: 'I found the primary account holder for 555-0199 is John Doe, located in Arlington, VA on the Verizon network. I\'ve created a proposal with this information.',
    timestamp: '8 min ago',
  },
  {
    id: 'm4',
    role: 'user',
    content: 'Dig deeper on the high frequency contacts',
    timestamp: 'Just now',
  },
];

// Simulate agent response with delay
export async function simulateAgentResponse(
  userMessage: string,
  existingProposals: Proposal[]
): Promise<{ message: Message; proposal?: Proposal }> {
  await new Promise((resolve) => setTimeout(resolve, 2000));

  const messageId = `m${Date.now()}`;
  const proposalId = `p${Date.now()}`;
  const iteration = existingProposals.length + 1;

  // Simple pattern matching for demo purposes
  if (userMessage.toLowerCase().includes('dig deeper') ||
      userMessage.toLowerCase().includes('expand') ||
      userMessage.toLowerCase().includes('investigate')) {
    return {
      message: {
        id: messageId,
        role: 'agent',
        content: `I've analyzed additional data and found ${Math.floor(Math.random() * 5) + 2} new connections. Review the proposed changes.`,
        timestamp: 'Just now',
      },
      proposal: {
        id: proposalId,
        iteration,
        status: 'pending',
        summary: `Expanded investigation - Iteration ${iteration}`,
        timestamp: 'Just now',
        changes: [
          {
            id: `c${Date.now()}-1`,
            type: 'add_node',
            entity: 'Phone',
            label: `555-${Math.floor(1000 + Math.random() * 9000)}`,
            properties: {
              calls: Math.floor(10 + Math.random() * 50),
              avgDuration: `${Math.floor(1 + Math.random() * 10)}m ${Math.floor(Math.random() * 60)}s`,
            },
            confidence: Math.floor(70 + Math.random() * 25),
            evidence: 'Found in CDR frequency analysis',
          },
        ],
      },
    };
  }

  if (userMessage.toLowerCase().includes('evidence')) {
    return {
      message: {
        id: messageId,
        role: 'agent',
        content: 'The evidence for pending changes includes CDR frequency patterns, carrier lookup data, and cross-referenced social media profiles. Each change includes detailed reasoning in the evidence panel.',
        timestamp: 'Just now',
      },
    };
  }

  if (userMessage.toLowerCase().includes('summary')) {
    return {
      message: {
        id: messageId,
        role: 'agent',
        content: `Current case status: ${existingProposals.length} proposals generated, ${existingProposals.filter(p => p.status === 'approved').length} approved, ${existingProposals.filter(p => p.status === 'pending').length} pending review.`,
        timestamp: 'Just now',
      },
    };
  }

  // Default response
  return {
    message: {
      id: messageId,
      role: 'agent',
      content: 'I understand. Let me analyze that information and get back to you.',
      timestamp: 'Just now',
    },
  };
}
