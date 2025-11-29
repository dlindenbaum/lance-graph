import React from 'react';

interface EvidencePanelProps {
  evidence: string;
}

export function EvidencePanel({ evidence }: EvidencePanelProps) {
  return (
    <div className="mt-2 p-3 rounded bg-blue-950/30 border border-blue-900/50">
      <div className="text-xs font-semibold text-blue-400 mb-1">Evidence</div>
      <div className="text-sm text-text-main">{evidence}</div>
    </div>
  );
}
