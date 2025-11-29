import React from 'react';

interface QuickAction {
  label: string;
  prompt: string;
  icon: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    label: 'Dig Deeper',
    icon: '🔍',
    prompt: 'Expand investigation on the latest finding',
  },
  {
    label: 'Show Evidence',
    icon: '📋',
    prompt: 'Show me the evidence for the pending changes',
  },
  {
    label: 'Find Links',
    icon: '🔗',
    prompt: 'Find connections between the phone numbers',
  },
  {
    label: 'Summary',
    icon: '📊',
    prompt: 'Summarize the current case status',
  },
];

interface QuickActionsProps {
  onSelectAction: (prompt: string) => void;
  disabled?: boolean;
}

export function QuickActions({ onSelectAction, disabled }: QuickActionsProps) {
  return (
    <div className="flex flex-wrap gap-2 p-3 bg-dark-panel border-b border-dark-border">
      {QUICK_ACTIONS.map((action) => (
        <button
          key={action.label}
          onClick={() => onSelectAction(action.prompt)}
          disabled={disabled}
          className="px-3 py-1.5 text-sm bg-dark hover:bg-dark-border text-text-main rounded border border-dark-border disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span className="mr-1">{action.icon}</span>
          {action.label}
        </button>
      ))}
    </div>
  );
}
